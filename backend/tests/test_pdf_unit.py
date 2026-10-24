"""Report rendering checks written before the optional PDF renderer."""
import unittest
from app.pdf_export import report_html


class ReportRenderingTests(unittest.TestCase):
    def report(self):
        return {'id':'report-1','session_id':'session-1','release_id':'release-1','bundle_hash':'abc',
                'rubric_version':'rubric-1','completion':'incomplete','assessment_notice':'Supervised review required.',
                'assessments':[{'dimension':'evidence_use','score':None,'status':'not_assessed','rationale':'Missing answer.'}],
                'questions':[{'question_id':'q1','feedback':'Review the source.','sources':[{'document_id':'doc-1','locator':'Page 2','excerpt':'Compare observations.'}]}],
                'strengths':[], 'misconceptions':[], 'missed_topics':['Changed condition'], 'recommendations':['Review evidence'],
                'transcript':[{'speaker':'learner','text':'<script>steal()</script>','delivery':'completed'}],
                'source_index':[{'document':{'id':'doc-1','title':'Guide <img src="https://attack/track">','version':'1','checksum':'hash'},'usage':'unused'}],
                'playground_scores':[{'name':'decision_accuracy','earned':1,'available':2}], 'critical_error':True}

    def test_escapes_user_source_and_model_content(self):
        html = report_html(self.report())
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img ', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&lt;img', html)

    def test_retains_provenance_null_scores_and_all_sources(self):
        html = report_html(self.report())
        for text in ('report-1','release-1','rubric-1','not_assessed','doc-1','Critical Playground error','Page 2'):
            self.assertIn(text, html)
        self.assertIn('Not assessed', html)
        self.assertNotIn('None/4', html)

    def test_refuses_invalid_stored_report(self):
        with self.assertRaises(ValueError):
            report_html({})
        with self.assertRaises(ValueError):
            report_html({**self.report(), 'source_index':'not-an-index'})


if __name__ == '__main__':
    unittest.main()
