"""Human review preserves the original report and verifies evidence and scope."""
import copy
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.auth import Actor
from app.config import Settings
from app.db import Database
from app.seed import seed
from app import service, worker, reviews
from app.models import VivaSession, VivaReport, ReportReview, Release


@pytest.fixture
def reviewed(tmp_path):
    database=Database('sqlite:///'+str(tmp_path/'reviews.db'),Settings(database_url='sqlite:///'+str(tmp_path/'reviews.db'),provider_mode='fixture',run_inline_worker=False))
    database.initialize();seed(database)
    session=service.mutate(database,'learner-1','/viva/sessions',str(uuid4()),{'attempt_id':'attempt-demo-success','input_mode':'text'},lambda db:service.start(db,'learner-1',{'attempt_id':'attempt-demo-success','input_mode':'text'},database.settings))
    session=service.submit_answer(database,session['id'],'learner-1',str(uuid4()),{'expected_revision':session['revision'],'question_id':session['current_question']['id'],'client_turn_id':'review-answer','text':'I record the observation and select a check based on sufficient evidence.'})['session']
    with database.session_factory.begin() as db:
        row=service.owned(db,session['id'],'learner-1');service.finish(db,row,database.settings)
    worker.process_once(database)
    with database.session_factory() as db:
        row=db.get(VivaSession,session['id']);report=copy.deepcopy(db.get(VivaReport,row.result_id).data)
    reviewer=Actor('reviewer-1',tenant_id='demo',roles={'reviewer'})
    learner=Actor('learner-1',tenant_id='demo',roles={'learner'})
    yield database,session['id'],report,reviewer,learner
    database.engine.dispose()


def override(report,score=3):
    turn=next(t for t in report['transcript'] if t['speaker']=='learner')
    return {'dimension':'technical_correctness','status':'assessed','score':score,
        'rationale':'The learner ties the check to recorded observations.', 'answer_turn_ids':[turn['id']],
        'sources':[{'release_id':'release-demo-v1','document_id':'doc-inspection','evidence_id':'evidence-inspection','locator':'Section 1',
            'excerpt':'Inspection decisions must connect the selected check to the observed condition.'}]}


def test_assigned_reviewer_can_append_without_mutating_original(reviewed):
    database,sid,report,reviewer,learner=reviewed
    before=service.digest(report)
    result=reviews.create_review(database,sid,reviewer,{'expected_review_version':0,'reason':'Instructor verification of the recorded explanation.','overrides':[override(report)]},'review-key')
    assert result['version']==1
    listing=reviews.list_reviews(database,sid,learner)
    assert listing['version']==1 and len(listing['reviews'])==1
    assert listing['report']['id']==report['id']
    with database.session_factory() as db:
        assert service.digest(db.get(VivaReport,report['id']).data)==before
        assert db.scalar(select(func.count()).select_from(ReportReview))==1


def test_owner_can_read_but_cannot_write_review(reviewed):
    database,sid,report,reviewer,learner=reviewed
    assert reviews.list_reviews(database,sid,learner)['report_id']==report['id']
    with pytest.raises(service.DomainError) as error:
        reviews.create_review(database,sid,learner,{'expected_review_version':0,'reason':'Self score','overrides':[override(report)]},'self')
    assert error.value.status==403


def test_reviewer_requires_assignment_and_release_tenant(reviewed):
    database,sid,report,reviewer,learner=reviewed
    for actor in [Actor('unassigned',tenant_id='demo',roles={'reviewer'}),Actor('reviewer-1',tenant_id='another-tenant',roles={'reviewer'}),Actor('learner-2',tenant_id='demo',roles={'learner'})]:
        with pytest.raises(service.DomainError) as error:reviews.list_reviews(database,sid,actor)
        assert error.value.status==404


def test_review_versions_and_request_deduplication(reviewed):
    database,sid,report,reviewer,learner=reviewed
    body={'expected_review_version':0,'reason':'Evidence verified','overrides':[override(report)]}
    first=reviews.create_review(database,sid,reviewer,body,'same-key')
    assert reviews.create_review(database,sid,reviewer,body,'same-key')==first
    with pytest.raises(service.DomainError) as error:reviews.create_review(database,sid,reviewer,body,'another-key')
    assert error.value.status==409
    second=reviews.create_review(database,sid,reviewer,{**body,'expected_review_version':1,'reason':'Revised after a second look','overrides':[override(report,4)]},'second-key')
    assert second['version']==2


def test_review_rejects_invented_or_changed_source_evidence(reviewed):
    database,sid,report,reviewer,learner=reviewed
    for patch in [{'evidence_id':'invented'},{'excerpt':'Unsupported invented claim'},{'locator':'Page 900'}]:
        bad=override(report);bad['sources'][0].update(patch)
        with pytest.raises(service.DomainError) as error:reviews.create_review(database,sid,reviewer,{'expected_review_version':0,'reason':'Bad reference','overrides':[bad]},str(uuid4()))
        assert error.value.status==422
    bad=override(report);bad['answer_turn_ids']=['unknown-turn']
    with pytest.raises(service.DomainError):reviews.create_review(database,sid,reviewer,{'expected_review_version':0,'reason':'Bad learner reference','overrides':[bad]},'bad-turn')


def test_review_rejects_duplicate_dimensions_and_missing_reason(reviewed):
    database,sid,report,reviewer,learner=reviewed
    for body in [{'expected_review_version':0,'reason':'','overrides':[override(report)]},
                 {'expected_review_version':0,'reason':'Duplicate dimension','overrides':[override(report),override(report)]}]:
        with pytest.raises(service.DomainError) as error:reviews.create_review(database,sid,reviewer,body,str(uuid4()))
        assert error.value.status==422


def test_reviewer_assignment_is_explicit_and_idempotent(reviewed):
    database,sid,report,reviewer,learner=reviewed
    other=Actor('reviewer-2',tenant_id='demo',roles={'reviewer'})
    reviews.assign_reviewer(database,str(other),'task-inspection','demo')
    reviews.assign_reviewer(database,str(other),'task-inspection','demo')
    assert reviews.list_reviews(database,sid,other)['report_id']==report['id']
