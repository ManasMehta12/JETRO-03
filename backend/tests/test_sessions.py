"""Behavior-first contract tests for release-bound technical Viva sessions."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app

@pytest.fixture
def client(tmp_path):
    settings = Settings(database_url='sqlite:///' + str(tmp_path / 'test.db'), provider_mode='fixture', run_inline_worker=False)
    with TestClient(create_app(settings)) as value:
        yield value

def headers(token='demo-learner-token', key=None):
    return {'Authorization': 'Bearer ' + token, 'Idempotency-Key': key or str(uuid4())}

def start(client, mode='text', attempt='attempt-demo-success', key=None):
    return client.post('/api/v1/viva/sessions', json={'attempt_id': attempt, 'input_mode': mode}, headers=headers(key=key))

def test_owned_completed_attempt_starts_release_bound_session(client):
    response = start(client)
    assert response.status_code == 200
    session = response.json()
    assert session['release_id'] == 'release-demo-v1'
    assert session['status'] == 'in_progress'
    assert session['current_question']['objective'] == 'explanation'
    assert session['question_count'] == 3
    assert 'rubric' not in session and 'accepted_answers' not in str(session)
    again = start(client).json()
    assert again['id'] == session['id']

def test_ownership_and_auth(client):
    assert client.get('/api/v1/bootstrap').status_code == 401
    assert start(client, attempt='attempt-other').status_code == 404
    session = start(client).json()
    assert client.get('/api/v1/viva/sessions/' + session['id'], headers=headers('demo-other-token')).status_code == 404

def test_deduplication_precedes_stale_revision(client):
    session = start(client).json()
    payload = {'expected_revision': session['revision'], 'question_id': session['current_question']['id'], 'client_turn_id': 'answer-1', 'text': 'I inspected the housing and compared the observations before choosing a check.'}
    url = '/api/v1/viva/sessions/' + session['id'] + '/answers'
    first = client.post(url, json=payload, headers=headers(key='same'))
    assert first.status_code == 202
    assert client.post(url, json=payload, headers=headers(key='same')).json() == first.json()
    changed = dict(payload, text='different')
    assert client.post(url, json=changed, headers=headers(key='same')).status_code == 409
    assert client.post(url, json=payload, headers=headers(key='new')).status_code == 202
    assert client.post(url, json=dict(payload, client_turn_id='new'), headers=headers()).status_code == 409

def test_pause_resume_and_early_finish_are_recoverable(client):
    session = start(client).json()
    base = '/api/v1/viva/sessions/' + session['id']
    paused = client.post(base + '/pause', json={'expected_revision': session['revision']}, headers=headers()).json()
    assert paused['status'] == 'paused'
    resumed = client.post(base + '/resume', json={'expected_revision': paused['revision'], 'input_mode':'text'}, headers=headers()).json()
    assert resumed['status'] == 'in_progress'
    job = client.post(base + '/finish', json={'expected_revision': resumed['revision']}, headers=headers())
    assert job.status_code == 202
    assert client.post(base + '/finish', json={'expected_revision': 0}, headers=headers()).json()['id'] == job.json()['id']
    assert client.get(base + '/result', headers=headers()).status_code == 409
    assert client.post(base + '/answers', json={'expected_revision':0,'question_id':'x','client_turn_id':'x','text':'late'},headers=headers()).status_code == 409

def test_events_are_ordered_and_current_question_is_restorable(client):
    session = start(client).json()
    base = '/api/v1/viva/sessions/' + session['id']
    events = client.get(base+'/events?limit=1',headers=headers()).json()
    assert len(events['events']) == 1
    assert events['has_more']
    second = client.get(base+'/events?after='+str(events['next_after']),headers=headers()).json()
    assert all(e['sequence'] > events['next_after'] for e in second['events'])
    restored = client.get(base,headers=headers()).json()
    assert restored['current_question'] == session['current_question']
    assert len(restored['transcript']) == 1

def test_release_sources_require_scope(client):
    assert client.get('/api/v1/studio/releases/release-demo-v1',headers=headers()).status_code == 200
    assert client.get('/api/v1/studio/releases/release-demo-v1/documents/doc-inspection/content',headers=headers()).status_code == 200
    assert client.get('/api/v1/studio/releases/release-demo-v1/documents/unknown/content',headers=headers()).status_code == 404

def test_question_and_followup_limits_complete_automatically(client):
    session = start(client).json()
    base = '/api/v1/viva/sessions/' + session['id']
    turns = 0
    while session['status'] == 'in_progress':
        turns += 1
        assert turns <= 6
        reply = client.post(base+'/answers',headers=headers(),json={'expected_revision':session['revision'],'question_id':session['current_question']['id'],'client_turn_id':str(turns),'text':'The observed evidence informs the check. If it is insufficient or inconsistent I stop and escalate for supervision.'})
        assert reply.status_code == 202, reply.text
        session = reply.json()['session']
    assert session['status'] == 'evaluating'
    assert session['answered_count'] == 3
    assert session['follow_up_count'] <= 3

def test_voice_semantic_event_replay_creates_one_answer(client):
    from app import service
    from app.models import VivaSession
    database=client.app.state.db
    session=start(client,mode='voice').json()
    with database.session_factory.begin() as db:
        row=db.get(VivaSession,session['id']);row.status='connecting';row.connection_epoch=1
    service.voice_ready(database,session['id'],'learner-1',1,'fake-call')
    service.mark_question_delivered(database,session['id'],'learner-1',1)
    first=service.commit_voice_turn(database,session['id'],'learner-1',1,'provider-item','I gathered observations before choosing a check.')
    replay=service.commit_voice_turn(database,session['id'],'learner-1',1,'provider-item','I gathered observations before choosing a check.')
    assert replay==first
    restored=client.get('/api/v1/viva/sessions/'+session['id'],headers=headers()).json()
    assert len([t for t in restored['transcript'] if t['speaker']=='learner'])==1
    with pytest.raises(service.DomainError) as error:
        service.commit_voice_turn(database,session['id'],'learner-1',1,'provider-item','A changed transcript must not replace committed input silently.')
    assert error.value.status==409

def test_flagged_turn_keeps_original_and_links_replacement(client):
    session=start(client).json();base='/api/v1/viva/sessions/'+session['id']
    first=client.post(base+'/answers',headers=headers(),json={'expected_revision':session['revision'],'question_id':session['current_question']['id'],'client_turn_id':'first','text':'An unclear initial answer.'}).json()
    session=first['session'];original=first['turn']['id']
    flagged=client.post(base+'/transcript-flags',headers=headers(),json={'expected_revision':session['revision'],'turn_id':original,'reason':'Transcription did not match my intended answer.'})
    assert flagged.status_code==200,flagged.text
    assert flagged.json()['replacement_requested'] is True
    session=flagged.json()['session']
    answer=client.post(base+'/answers',headers=headers(),json={'expected_revision':session['revision'],'question_id':session['current_question']['id'],'client_turn_id':'replacement','text':'My observation supports the check; missing evidence requires escalation.'})
    assert answer.status_code==202,answer.text
    assert answer.json()['turn']['replacement_id']==original
    original_turn=next(t for t in answer.json()['session']['transcript'] if t['id']==original)
    assert original_turn['quality_flag']

def test_reset_reseed_reuses_start_key_without_stale_session(client):
    from app.cli import reset_demo
    from app.seed import seed
    database=client.app.state.db
    first=start(client,key='reset-key').json()
    counts=reset_demo(database,confirm=True)
    assert counts['viva_sessions']==1
    seed(database)
    second=start(client,key='reset-key')
    assert second.status_code==200,second.text
    assert second.json()['id']!=first['id']
    assert second.json()['bundle_hash']==first['bundle_hash']

def test_server_timer_freezes_timed_out_interview(client):
    from datetime import timedelta
    from app import service
    from app.models import VivaSession, now
    session=start(client).json();database=client.app.state.db
    with database.session_factory.begin() as db:
        row=db.get(VivaSession,session['id']);row.active_since=now()-timedelta(seconds=601)
    service.sweep_expired(database)
    updated=client.get('/api/v1/viva/sessions/'+session['id'],headers=headers()).json()
    assert updated['status']=='evaluating'
    assert updated['evaluation_job_id']

def setup_live_voice_session(client):
    from app import service
    from app.models import VivaSession, VoiceConnection, uid
    database=client.app.state.db
    session=start(client,mode='voice').json()
    with database.session_factory.begin() as db:
        row=db.get(VivaSession,session['id']);row.status='connecting';row.connection_epoch=1
        db.add(VoiceConnection(id=uid(),session_id=row.id,epoch=1,status='connecting'))
    service.voice_ready(database,session['id'],'learner-1',1,'fake-call')
    service.mark_question_delivered(database,session['id'],'learner-1',1)
    return database,session['id']


def test_pending_utterance_delays_timer_but_not_beyond_ten_seconds(client):
    from datetime import timedelta
    from app import service
    from app.models import VivaSession, VoiceConnection, now
    from sqlalchemy import select
    database,sid=setup_live_voice_session(client)
    service.voice_input_started(database,sid,'learner-1',1,'utterance-1')
    with database.session_factory.begin() as db:
        session=db.get(VivaSession,sid);session.active_since=now()-timedelta(seconds=601)
    service.sweep_expired(database)
    with database.session_factory() as db:
        assert db.get(VivaSession,sid).status=='in_progress'
    with database.session_factory.begin() as db:
        conn=db.scalar(select(VoiceConnection).where(VoiceConnection.session_id==sid,VoiceConnection.epoch==1))
        conn.drain_started_at=now()-timedelta(seconds=11)
    service.sweep_expired(database)
    with database.session_factory() as db:
        session=db.get(VivaSession,sid)
        assert session.status=='evaluating'
        turns=service.turns_for(db,sid)
        assert any(t['speaker']=='learner' and t['delivery']=='interrupted' for t in turns)


def test_pending_utterance_can_finish_during_time_limit_grace(client):
    from datetime import timedelta
    from app import service
    from app.models import VivaSession, now
    database,sid=setup_live_voice_session(client)
    service.voice_input_started(database,sid,'learner-1',1,'utterance-1')
    with database.session_factory.begin() as db:
        db.get(VivaSession,sid).active_since=now()-timedelta(seconds=601)
    result=service.commit_voice_turn(database,sid,'learner-1',1,'utterance-1','I use recorded observations and escalate inconsistent evidence.')
    assert result['turn']['delivery']=='completed'
    service.voice_input_finished(database,sid,'learner-1',1,'utterance-1')
    assert service.pending_voice_input(database,sid,'learner-1')['pending'] is False


def test_repeated_vad_event_does_not_extend_grace(client):
    from datetime import timedelta
    from app import service
    from app.models import VoiceConnection, now
    from sqlalchemy import select
    database,sid=setup_live_voice_session(client)
    service.voice_input_started(database,sid,'learner-1',1,'utterance-1')
    with database.session_factory.begin() as db:
        conn=db.scalar(select(VoiceConnection).where(VoiceConnection.session_id==sid,VoiceConnection.epoch==1))
        timestamp=now()-timedelta(seconds=7);conn.drain_started_at=timestamp
    service.voice_input_started(database,sid,'learner-1',1,'utterance-1')
    pending=service.pending_voice_input(database,sid,'learner-1')
    assert pending['remaining_seconds']<4


def test_finish_requires_pending_utterance_drain(client):
    from app import service
    database,sid=setup_live_voice_session(client)
    service.voice_input_started(database,sid,'learner-1',1,'utterance-1')
    with database.session_factory.begin() as db:
        row=service.owned(db,sid,'learner-1')
        with pytest.raises(service.DomainError) as error:service.finish(db,row,database.settings)
        assert error.value.code=='utterance_in_progress'


def test_late_delivery_ack_does_not_mark_new_question_delivered(client):
    from app import service
    from app.models import InterviewTurn
    from sqlalchemy import select
    database,sid=setup_live_voice_session(client)
    with database.session_factory() as db:
        original=db.scalar(select(InterviewTurn).where(InterviewTurn.session_id==sid,InterviewTurn.speaker=='interviewer'))
        original_id=original.id
    result=service.commit_voice_turn(database,sid,'learner-1',1,'answer-item','My observed evidence supports the check.')
    follow_up=result['session']['current_question']
    assert follow_up['is_follow_up']
    assert service.mark_question_delivered(database,sid,'learner-1',1,'completed',turn_id=original_id) is False
    with database.session_factory() as db:
        latest=db.scalar(select(InterviewTurn).where(InterviewTurn.session_id==sid,InterviewTurn.speaker=='interviewer').order_by(InterviewTurn.sequence.desc()))
        assert latest.delivery=='unconfirmed'


def test_long_answer_gets_drain_grace_after_finish_not_at_speech_start(client):
    from datetime import timedelta
    from app import service
    from app.models import VoiceConnection, now
    from sqlalchemy import select
    database,sid=setup_live_voice_session(client)
    service.voice_input_started(database,sid,'learner-1',1,'long-utterance')
    with database.session_factory.begin() as db:
        conn=db.scalar(select(VoiceConnection).where(VoiceConnection.session_id==sid,VoiceConnection.epoch==1))
        conn.pending_since=now()-timedelta(seconds=45)
    pending=service.pending_voice_input(database,sid,'learner-1',True)
    assert pending['pending'] is True
    assert pending['remaining_seconds']>9
    with database.session_factory.begin() as db:
        row=service.owned(db,sid,'learner-1')
        with pytest.raises(service.DomainError) as error:service.finish(db,row,database.settings)
        assert error.value.code=='utterance_in_progress'


def test_pausing_pending_speech_records_interrupted_turn(client):
    from app import service
    database,sid=setup_live_voice_session(client)
    service.voice_input_started(database,sid,'learner-1',1,'paused-utterance')
    with database.session_factory.begin() as db:
        row=service.owned(db,sid,'learner-1')
        service.pause(db,row,{'expected_revision':row.revision},database.settings)
    restored=client.get('/api/v1/viva/sessions/'+sid,headers=headers()).json()
    assert restored['status']=='paused'
    assert any(t['speaker']=='learner' and t['delivery']=='interrupted' for t in restored['transcript'])
