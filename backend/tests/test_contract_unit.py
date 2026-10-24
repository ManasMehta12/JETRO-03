"""Checks intended interface invariants without importing application frameworks."""
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'markdowns/hackathon/openapi/technical-viva.openapi.json').read_text())
    def test_voice_and_recovery_and_quality_routes_exist(self):
        for suffix in ('connection','connection/ready','answers','events','repeat','transcript-flags','pause','resume','finish','evaluation','result'):
            self.assertIn('/viva/sessions/{session_id}/'+suffix,self.spec['paths'])
    def test_no_selected_option_grading_in_live_contract(self):
        body=self.spec['paths']['/viva/sessions/{session_id}/answers']['post']['requestBody']['content']['application/json']['schema']
        self.assertIn('text',body['required']);self.assertNotIn('option_id',body['properties'])
    def test_scores_nullable_and_bounded(self):
        score=self.spec['components']['schemas']['RubricAssessment']['properties']['score']
        self.assertTrue(score['nullable']);self.assertEqual((0,4),(score['minimum'],score['maximum']))
    def test_events_are_typed_payload_variants(self):
        schemas=self.spec['components']['schemas']
        variants=schemas['SessionEvent']['oneOf']
        self.assertEqual(len(variants),5)
        for ref in variants:
            schema=schemas[ref['$ref'].split('/')[-1]]
            self.assertIn('payload',schema['required']);self.assertFalse(schema['additionalProperties'])
    def test_all_mutations_require_idempotency(self):
        for path,item in self.spec['paths'].items():
            for method,operation in item.items():
                if method=='post':
                    header=next(p for p in operation['parameters'] if p['name']=='Idempotency-Key')
                    self.assertTrue(header['required'])
    def test_references_and_parameters_resolve(self):
        schemas=self.spec['components']['schemas']
        def walk(node):
            if isinstance(node,dict):
                if '$ref' in node:self.assertIn(node['$ref'].split('/')[-1],schemas)
                for value in node.values():walk(value)
            elif isinstance(node,list):
                for value in node:walk(value)
        walk(self.spec)
        for path,item in self.spec['paths'].items():
            placeholders={p[1:-1] for p in path.split('/') if p.startswith('{')}
            self.assertEqual(placeholders,{p['name'] for p in item.get('parameters',[])})
    def test_generated_report_preserves_entire_manifest_and_provenance(self):
        fields=self.spec['components']['schemas']['VivaReport']['properties']
        for name in ('snapshot_hash','source_index','critical_error','playground_scores','transcript','coverage'):
            self.assertIn(name,fields)

if __name__=='__main__':unittest.main()
