"""Persisted evaluation jobs must survive retries without duplicate publication."""
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.config import Settings
from app.db import Database
from app.seed import seed
from app import service, provider, worker
from app.models import EvaluationJob, VivaSession, VivaReport, now


@pytest.fixture
def database(tmp_path):
    value=Database('sqlite:///'+str(tmp_path/'worker.db'),Settings(database_url='sqlite:///'+str(tmp_path/'worker.db'),provider_mode='fixture',run_inline_worker=False))
    value.initialize();seed(value)
    yield value
    value.engine.dispose()


def queued(database):
    session=service.mutate(database,'learner-1','/viva/sessions',str(uuid4()),{'attempt_id':'attempt-demo-success','input_mode':'text'},lambda db:service.start(db,'learner-1',{'attempt_id':'attempt-demo-success','input_mode':'text'},database.settings))
    with database.session_factory.begin() as db:
        row=service.owned(db,session['id'],'learner-1',True)
        result=service.finish(db,row,database.settings)
    return session['id'],result['id']


def test_one_job_publishes_one_report(database):
    sid,jid=queued(database)
    assert worker.process_once(database) is True
    assert worker.process_once(database) is False
    with database.session_factory() as db:
        job=db.get(EvaluationJob,jid);session=db.get(VivaSession,sid)
        assert job.status=='completed' and session.status=='completed'
        assert job.result_id==session.result_id
        assert db.scalar(select(func.count()).select_from(VivaReport))==1
        report=db.get(VivaReport,job.result_id)
        assert report.snapshot_hash==job.snapshot_hash
        assert report.data['completion']=='incomplete'


def test_live_lease_prevents_second_worker_claim(database):
    sid,jid=queued(database)
    with database.session_factory.begin() as db:
        job=db.get(EvaluationJob,jid);job.status='running';job.lease_until=now()+timedelta(seconds=60)
    assert worker.process_once(database) is False
    with database.session_factory() as db:assert db.get(EvaluationJob,jid).result_id is None


def test_expired_lease_can_be_reclaimed(database):
    sid,jid=queued(database)
    with database.session_factory.begin() as db:
        job=db.get(EvaluationJob,jid);job.status='running';job.lease_until=now()-timedelta(seconds=1);job.attempt_count=1
    assert worker.process_once(database) is True
    with database.session_factory() as db:
        job=db.get(EvaluationJob,jid)
        assert job.status=='completed'
        assert job.attempt_count==2


def test_transient_failure_retries_same_frozen_snapshot(database,monkeypatch):
    sid,jid=queued(database)
    original=provider.evaluate
    calls=[]
    def flaky(snapshot,settings=None,**kwargs):
        calls.append(service.digest(snapshot))
        if len(calls)==1:raise provider.ProviderUnavailable('temporary')
        return original(snapshot,settings)
    monkeypatch.setattr(provider,'evaluate',flaky)
    assert worker.process_once(database) is True
    with database.session_factory.begin() as db:
        job=db.get(EvaluationJob,jid)
        assert job.status=='queued' and job.error_code=='provider_unavailable'
        job.next_attempt_at=now()-timedelta(seconds=1)
    assert worker.process_once(database) is True
    assert len(calls)==2 and calls[0]==calls[1]
    with database.session_factory() as db:assert db.get(EvaluationJob,jid).status=='completed'


def test_changed_snapshot_hash_is_not_evaluated(database,monkeypatch):
    sid,jid=queued(database)
    with database.session_factory.begin() as db:
        job=db.get(EvaluationJob,jid);job.snapshot={**job.snapshot,'finish_reason':'tampered'}
    def should_not_call(*args,**kwargs):raise AssertionError('Changed frozen input reached provider')
    monkeypatch.setattr(provider,'evaluate',should_not_call)
    worker.process_once(database)
    with database.session_factory() as db:
        job=db.get(EvaluationJob,jid)
        assert job.error_code=='invalid_assessment'
        assert job.result_id is None
        assert db.scalar(select(func.count()).select_from(VivaReport))==0


def test_invalid_score_never_publishes_and_retry_budget_is_bounded(database,monkeypatch):
    sid,jid=queued(database)
    original=provider.evaluate
    def bad(snapshot,settings=None,**kwargs):
        report=original(snapshot,settings)
        report['assessments'][0].update(status='assessed',score=99)
        return report
    monkeypatch.setattr(provider,'evaluate',bad)
    for attempt in range(3):
        assert worker.process_once(database) is True
        with database.session_factory.begin() as db:
            job=db.get(EvaluationJob,jid)
            if attempt<2:job.next_attempt_at=now()-timedelta(seconds=1)
    with database.session_factory() as db:
        job=db.get(EvaluationJob,jid);session=db.get(VivaSession,sid)
        assert job.status=='failed' and job.attempt_count==3
        assert job.retryable is False and session.status=='failed'
        assert db.scalar(select(func.count()).select_from(VivaReport))==0
