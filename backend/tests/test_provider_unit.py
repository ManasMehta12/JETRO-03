"""Provider and provenance tests, written before the adapter implementation.
Run without third-party dependencies: python -m unittest discover -s backend/tests -p test_provider_unit.py.
"""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import provider


def snapshot():
    return {'session': {'id':'session','attempt_id':'attempt','release_id':'release','bundle_id':'bundle','bundle_hash':'hash','rubric_version':'rubric','prompt_version':'prompt','model_config_version':'model'},
      'turns':[{'id':'q','speaker':'interviewer','text':'Explain','question_id':'question'}, {'id':'a','speaker':'learner','text':'I need evidence','question_id':'question','delivery':'completed','quality_flag':None}],
      'coverage':[{'question_id':'question','status':'answered','answer_turn_ids':['a']}],
      'release': {'id':'release','documents':[{'id':'doc','title':'Guide','version':'1','checksum':'hash','availability':'available','evidence_ids':['ev'],'content':'Stop and ask a supervisor.'}],
       'evidence':[{'id':'ev','document_id':'doc','text':'Stop and ask a supervisor.','locator':'Section 1'}]},
      'rubric':{'version':'rubric'},'playground':{'scores':[],'critical_error':True},'finish_reason':'learner_finished','provider_mode':'fixture'}

class ProviderTests(unittest.TestCase):
    def test_fixture_never_claims_model_grades(self):
        result = provider.evaluate(snapshot())
        self.assertEqual({a['status'] for a in result['assessments']}, {'not_assessed'})
        self.assertTrue(all(a['score'] is None for a in result['assessments']))
        self.assertIn('fixture', result['assessment_notice'].lower())
        self.assertTrue(result['critical_error'])
        self.assertEqual(['doc'], [s['document']['id'] for s in result['source_index']])
        provider.validate_report(result, snapshot())

    def test_invented_citation_rejected(self):
        data = snapshot(); result = provider.evaluate(data)
        result['questions']=[{'question_id':'question','answer_turn_ids':['a'],'feedback':'Review','sources':[{'release_id':'release','document_id':'invented','evidence_id':'ev','locator':'Section 1','excerpt':'Stop'}]}]
        with self.assertRaises(provider.InvalidAssessment): provider.validate_report(result, data)

    def test_invented_excerpt_rejected(self):
        data=snapshot(); result=provider.evaluate(data)
        result['assessments'][0]['sources']=[{'release_id':'release','document_id':'doc','evidence_id':'ev','locator':'Section 1','excerpt':'Invented specification'}]
        with self.assertRaises(provider.InvalidAssessment): provider.validate_report(result,data)

    def test_missing_source_index_member_rejected(self):
        result=provider.evaluate(snapshot()); result['source_index']=[]
        with self.assertRaises(provider.InvalidAssessment): provider.validate_report(result,snapshot())

    def test_only_learner_turn_can_support_grade(self):
        result=provider.evaluate(snapshot()); result['assessments'][0].update(status='assessed',score=3,answer_turn_ids=['q'])
        with self.assertRaises(provider.InvalidAssessment): provider.validate_report(result,snapshot())

    def test_missing_and_unclear_answers_cannot_get_zero(self):
        data=snapshot(); data['turns'][1]['quality_flag']='unclear'; result=provider.evaluate(data)
        result['assessments'][0].update(status='assessed',score=0,answer_turn_ids=['a'])
        with self.assertRaises(provider.InvalidAssessment): provider.validate_report(result,data)

    def test_model_cannot_change_provenance(self):
        result=provider.evaluate(snapshot()); result['release_id']='other'
        with self.assertRaises(provider.InvalidAssessment): provider.validate_report(result,snapshot())

    def test_model_cannot_hide_critical_error(self):
        result=provider.evaluate(snapshot()); result['critical_error']=False
        with self.assertRaises(provider.InvalidAssessment): provider.validate_report(result,snapshot())

    def test_provider_redirects_are_never_followed_with_credentials(self):
        from urllib.request import Request
        handler=provider.NoRedirect()
        result=handler.redirect_request(Request('https://provider.invalid',headers={'Authorization':'Bearer secret'}),None,302,'redirect',{},'http://untrusted.invalid')
        self.assertIsNone(result)

    def test_follow_up_fixture_is_bounded(self):
        first=provider.plan_follow_up({'provider_mode':'fixture','current_index':0,'follow_up_count':0})
        self.assertEqual(first['action'],'ask_follow_up')
        self.assertEqual(provider.plan_follow_up({'provider_mode':'fixture','current_index':0,'follow_up_count':1})['action'],'advance')

    def test_no_credentials_fail_closed(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY':''}):
            with self.assertRaises(provider.ProviderUnavailable):
                provider.plan_follow_up({'provider_mode':'openai'})

    def test_transport_is_server_only_structured_and_timeout_bounded(self):
        result={'action':'advance','prompt':None}
        with patch.dict('os.environ', {'OPENAI_API_KEY':'test-key'}), patch.object(provider,'_request_json',return_value={'output':[{'content':[{'type':'output_text','text':json.dumps(result)}]}]}) as transport:
            self.assertEqual(provider.plan_follow_up({'provider_mode':'openai','follow_up_count':0})['action'],'advance')
            body=transport.call_args.args[1]
            self.assertTrue(body['text']['format']['strict'])
            self.assertIn('server',body['instructions'].lower())

    def test_schema_types_and_unknown_fields_are_rejected(self):
        for key,value in [('rationale',{}),('extra_field','bad')]:
            data=snapshot(); result=provider.evaluate(data);result['assessments'][0][key]=value
            with self.assertRaises(provider.InvalidAssessment):provider.validate_report(result,data)
        result=provider.evaluate(snapshot());result['questions'][0]['feedback']=None
        with self.assertRaises(provider.InvalidAssessment):provider.validate_report(result,snapshot())

    def test_question_report_cannot_omit_core_coverage(self):
        result=provider.evaluate(snapshot());result['questions']=[]
        with self.assertRaises(provider.InvalidAssessment):provider.validate_report(result,snapshot())

    def test_score_out_of_range_rejected(self):
        result=provider.evaluate(snapshot()); result['assessments'][0].update(status='assessed',score=5,answer_turn_ids=['a'])
        with self.assertRaises(provider.InvalidAssessment): provider.validate_report(result,snapshot())

if __name__=='__main__': unittest.main()
