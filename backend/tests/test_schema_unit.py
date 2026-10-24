"""Actual fixture report must satisfy the same response schema as FastAPI."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    from app.schemas import VivaReportSchema, VivaSessionSchema, PublicReleaseSchema
    AVAILABLE=True
except ImportError:
    AVAILABLE=False
from app.demo_content import release_data
from app.provider import evaluate, public_document

@unittest.skipUnless(AVAILABLE,'Pydantic unavailable in this Python runtime')
class SchemaTests(unittest.TestCase):
    def test_fixture_report_matches_closed_api_schema(self):
        release=release_data()
        instant='2026-10-24T12:00:00+00:00'
        session={'id':'s','attempt_id':'a','learner_id':'learner-1','release_id':release['id'],'bundle_id':'b','bundle_hash':'h',
          'rubric_version':release['rubric_version'],'prompt_version':'examiner-v1','model_config_version':'fixture-v1',
          'status':'evaluating','input_mode':'text','revision':2,'question_count':3,'answered_count':0,'follow_up_count':0,
          'current_question':None,'last_event_sequence':1,'evaluation_job_id':'job','result_id':None,
          'active_seconds':1.0,'max_active_seconds':600,'transcript':[],'created_at':instant,'expires_at':instant}
        VivaSessionSchema.model_validate(session)
        coverage=[{'question_id':q['id'],'objective':q['objective'],'status':'unanswered','answer_turn_ids':[],'follow_up_count':0} for q in release['question_plan']]
        snapshot={'session':session,'turns':[],'coverage':coverage,'release':release,'rubric':release['rubric'],'playground':{'critical_error':True,'scores':[]},'finish_reason':'learner_finished','provider_mode':'fixture'}
        report=evaluate(snapshot);report.update(id='report',snapshot_hash='hash')
        validated=VivaReportSchema.model_validate(report)
        self.assertEqual(len(validated.source_index),len(release['documents']))
        self.assertTrue(validated.critical_error)
        public={k:release[k] for k in ('id','task_id','title','content_status','units','evidence')}
        public.update(content_hash='hash',documents=[public_document(doc) for doc in release['documents']])
        PublicReleaseSchema.model_validate(public)

if __name__=='__main__':unittest.main()
