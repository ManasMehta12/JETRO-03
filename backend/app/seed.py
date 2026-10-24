"""Versioned illustrative demo content; real instructor approval is a deployment gate."""
import hashlib
import json
from .models import Release, PlaygroundAttempt

from .demo_content import QUESTIONS, DOCUMENTS, release_data


def seed(database):
    with database.session_factory.begin() as db:
        existing=db.get(Release,'release-demo-v1')
        data=existing.data if existing else release_data()
        content_hash=existing.content_hash if existing else hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
        if not existing:
            db.add(Release(id=data['id'],task_id=data['task_id'],title=data['title'],content_hash=content_hash,data=data))
            db.flush()
        bundle_hash=hashlib.sha256(json.dumps({'release_hash':content_hash,'question_plan':data['question_plan'],'rubric':data['rubric'],'scenarios':['inspection-guided','inspection-change']},sort_keys=True).encode()).hexdigest()
        for aid,owner,critical,status in [('attempt-demo-success','learner-1',False,'completed'),('attempt-demo-critical','learner-1',True,'completed'),('attempt-other','learner-2',False,'completed'),('attempt-incomplete','learner-1',False,'in_progress')]:
            if db.get(PlaygroundAttempt,aid):continue
            db.add(PlaygroundAttempt(id=aid,learner_id=owner,task_id='task-inspection',status=status,release_id='release-demo-v1',bundle_id='demo_bundle_v1',bundle_hash=bundle_hash,scenario_id='inspection-change' if critical else 'inspection-guided',data={
                'title':'Changed-condition exercise' if critical else 'Guided inspection exercise',
                'critical_error':critical,'outcome':'early_proceed' if critical else 'escalated_with_evidence',
                'scores':[{'name':'decision_accuracy','earned':0 if critical else 2,'available':2},{'name':'evidence_gathering','earned':1 if critical else 2,'available':2},{'name':'recognition_of_limits','earned':0 if critical else 2,'available':2}],
                'decisions':['inspect_housing','request_observation','continue' if critical else 'escalate'],
                'release_id':'release-demo-v1','bundle_hash':bundle_hash,'is_demo':True}))
