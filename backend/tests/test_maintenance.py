"""Retention/deletion behavior tests written before maintenance implementation."""
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.config import Settings
from app.db import Database
from app.models import (Release, PlaygroundAttempt, VivaSession, InterviewTurn, EvaluationJob,
                        IdempotencyRecord, AuditEvent, VoiceConnection, now)
from app.seed import seed
from app import service
from app.maintenance import purge_retention, delete_learner_data


@pytest.fixture
def database(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'maintenance.db'}", Settings(run_inline_worker=False))
    db.initialize()
    seed(db)
    yield db
    db.engine.dispose()


def create_session(database, learner, attempt, old=True):
    with database.session_factory.begin() as db:
        value = service.start(db, learner, {'attempt_id':attempt,'input_mode':'text'}, database.settings)
        session = db.get(VivaSession, value['id'])
        session.status = 'completed'
        session.active_since = None
        if old:
            session.created_at = now() - timedelta(days=40)
            for turn in db.scalars(select(InterviewTurn).where(InterviewTurn.session_id == session.id)):
                turn.created_at = session.created_at
        db.add(IdempotencyRecord(actor_id=learner, route='/start', key=str(uuid4()), request_hash='hash', response={'id':session.id}, session_id=session.id))
        return session.id


def test_retention_preserves_sources_attempts_and_other_recent_sessions(database):
    old = create_session(database,'learner-1','attempt-demo-success')
    recent = create_session(database,'learner-2','attempt-other',old=False)
    result = purge_retention(database, days=30)
    assert result['deleted_session_ids'] == [old]
    with database.session_factory() as db:
        assert db.get(VivaSession, old) is None
        assert db.get(VivaSession, recent) is not None
        assert db.get(Release,'release-demo-v1') is not None
        assert db.get(PlaygroundAttempt,'attempt-demo-success') is not None
        assert not list(db.scalars(select(IdempotencyRecord).where(IdempotencyRecord.session_id == old)))
        events = list(db.scalars(select(AuditEvent).where(AuditEvent.action == 'purge_retention')))
        assert events and events[0].target_id == old
    assert purge_retention(database, days=30)['deleted_session_ids'] == []


def test_live_jobs_and_connections_are_skipped(database):
    job_session = create_session(database,'learner-1','attempt-demo-success')
    voice_session = create_session(database,'learner-2','attempt-other')
    with database.session_factory.begin() as db:
        db.add(EvaluationJob(id='active-job',session_id=job_session,snapshot={},snapshot_hash='hash',status='running',attempt_count=1,retryable=True,created_at=now()))
        db.add(VoiceConnection(id='active-voice',session_id=voice_session,epoch=1,status='active',created_at=now()))
    result = purge_retention(database, days=30)
    assert result['deleted_session_ids'] == []
    assert set(result['skipped_session_ids']) == {job_session, voice_session}


def test_delete_learner_is_explicit_and_owner_scoped(database):
    first = create_session(database,'learner-1','attempt-demo-success')
    other = create_session(database,'learner-2','attempt-other')
    with pytest.raises(RuntimeError):
        delete_learner_data(database,'learner-1')
    result = delete_learner_data(database,'learner-1',confirm=True)
    assert result['deleted_session_ids'] == [first]
    with database.session_factory() as db:
        assert db.get(VivaSession,other) is not None
        assert db.get(PlaygroundAttempt,'attempt-demo-success') is not None
        assert db.get(Release,'release-demo-v1') is not None


def test_recent_derived_activity_delays_retention(database):
    sid = create_session(database,'learner-1','attempt-demo-success')
    with database.session_factory.begin() as db:
        turn = db.scalar(select(InterviewTurn).where(InterviewTurn.session_id == sid))
        turn.created_at = now()
    assert purge_retention(database,days=30)['deleted_session_ids'] == []
    with pytest.raises(ValueError):
        purge_retention(database, days=0)
