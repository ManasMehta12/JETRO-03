"""Source ingestion/retrieval/storage tests written before their implementations."""
import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from app.knowledge import Scope, Section, Source, chunk_source, hybrid_retrieve, ingest_bytes
from app.storage import LocalStorage, S3Storage


SCOPE = Scope('tenant-a', 'task-a', 'release-1')


class KnowledgeTests(unittest.TestCase):
    def source(self, source_id='doc-1', text='Observe evidence before deciding.', scope=SCOPE, available=True):
        return Source(source_id, scope, 'Guide', '1', 'text/plain', 'checksum', (Section(text, 'Section 1'),), available)

    def test_text_ingestion_retains_original_checksum_and_locator(self):
        raw = 'First observation.\n\nSecond observation.'.encode()
        source = ingest_bytes(raw, source_id='doc', scope=SCOPE, title='Guide', media_type='text/plain')
        self.assertEqual(source.checksum, hashlib.sha256(raw).hexdigest())
        self.assertEqual(source.sections[0].locator, 'Paragraph 1')
        self.assertEqual(source.sections[1].text, 'Second observation.')

    def test_docx_ingestion_paragraphs_never_invents_page_numbers(self):
        content = io.BytesIO()
        with zipfile.ZipFile(content, 'w') as archive:
            archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Inspect bearing</w:t></w:r></w:p></w:body></w:document>')
        doc = ingest_bytes(content.getvalue(), source_id='docx', scope=SCOPE, title='Manual', media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        self.assertEqual(doc.sections[0].text, 'Inspect bearing')
        self.assertEqual(doc.sections[0].locator, 'Paragraph 1')

    def test_unsupported_or_malformed_sources_fail_explicitly(self):
        with self.assertRaises(ValueError):
            ingest_bytes(b'bad', source_id='x', scope=SCOPE, title='x', media_type='application/executable')
        with self.assertRaises(ValueError):
            ingest_bytes(b'bad', source_id='x', scope=SCOPE, title='x', media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    def test_chunking_has_overlap_and_preserves_source_locator(self):
        source = self.source(text=' '.join('word' + str(i) for i in range(1300)))
        chunks = chunk_source(source)
        self.assertEqual([c.token_count for c in chunks], [600, 600, 300])
        self.assertEqual(chunks[0].text.split()[-100:], chunks[1].text.split()[:100])
        self.assertTrue(all(c.source_id == source.id and c.locator == 'Section 1' for c in chunks))
        self.assertEqual(chunk_source(source)[0].id, chunks[0].id)

    def test_invalid_overlap_or_budget_is_rejected(self):
        with self.assertRaises(ValueError):
            chunk_source(self.source(), max_tokens=100, overlap=100)
        with self.assertRaises(ValueError):
            hybrid_retrieve('evidence', [], SCOPE, token_budget=0)

    def test_filtering_happens_before_lexical_and_vector_ranking(self):
        eligible = chunk_source(self.source(text='evidence observation'))
        foreign = chunk_source(self.source('foreign', 'evidence evidence evidence', Scope('tenant-b', 'task-a', 'release-1')))
        foreign += chunk_source(self.source('old', 'evidence', Scope('tenant-a', 'task-a', 'release-old')))
        foreign += chunk_source(self.source('other-task', 'evidence', Scope('tenant-a', 'other', 'release-1')))
        unavailable = chunk_source(self.source('unavailable', 'evidence', available=False))
        result = hybrid_retrieve('evidence', eligible + foreign + unavailable, SCOPE)
        self.assertEqual([c.source_id for c in result], ['doc-1'])

    def test_hybrid_ranking_combines_positive_vector_and_lexical_matches(self):
        from dataclasses import replace
        a = replace(chunk_source(self.source('a', 'inspection evidence'))[0], embedding=(1.0, 0.0))
        b = replace(chunk_source(self.source('b', 'different passage'))[0], embedding=(0.9, 0.1))
        result = hybrid_retrieve('evidence', [b, a], SCOPE, query_embedding=(1.0, 0.0))
        self.assertEqual(result[0].source_id, 'a')
        self.assertEqual(len(result), 2)
        self.assertEqual(hybrid_retrieve('no match', [b], SCOPE), [])

    def test_retrieval_enforces_eight_passages_and_token_budget(self):
        chunks = []
        for index in range(12):
            chunks += chunk_source(self.source(str(index), 'evidence observation reasoning'))
        result = hybrid_retrieve('evidence', chunks, SCOPE, max_passages=99, token_budget=7)
        self.assertLessEqual(len(result), 8)
        self.assertLessEqual(sum(c.token_count for c in result), 7)


class StorageTests(unittest.TestCase):
    def test_local_storage_requires_scope_and_refuses_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalStorage(Path(directory))
            storage.put('sources/manual.txt', b'approved source', owner_scope=SCOPE, requester_scope=SCOPE)
            self.assertEqual(storage.read('sources/manual.txt', owner_scope=SCOPE, requester_scope=SCOPE), b'approved source')
            with self.assertRaises(PermissionError):
                storage.read('sources/manual.txt', owner_scope=SCOPE, requester_scope=Scope('other', 'task-a', 'release-1'))
            for key in ('../secret', '/etc/passwd', 'sources/../../secret', 'sources\\..\\secret'):
                with self.assertRaises(ValueError):
                    storage.read(key, owner_scope=SCOPE, requester_scope=SCOPE)

    def test_local_storage_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            (root / 'escape').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                LocalStorage(root).read('escape/secret', owner_scope=SCOPE, requester_scope=SCOPE)

    def test_s3_authorizes_before_signing_and_bounds_expiry(self):
        class Client:
            calls = []
            def generate_presigned_url(self, operation, **kwargs):
                self.calls.append((operation, kwargs))
                return 'https://storage.example/temporary'
        client = Client()
        storage = S3Storage('private-bucket', client=client)
        with self.assertRaises(PermissionError):
            storage.signed_url('source.txt', owner_scope=SCOPE, requester_scope=Scope('other','task-a','release-1'))
        self.assertEqual(client.calls, [])
        url = storage.signed_url('source.txt', owner_scope=SCOPE, requester_scope=SCOPE, expires_in=60)
        self.assertTrue(url.startswith('https://'))
        self.assertEqual(client.calls[0][1]['ExpiresIn'], 60)
        with self.assertRaises(ValueError):
            storage.signed_url('source.txt', owner_scope=SCOPE, requester_scope=SCOPE, expires_in=86400)


if __name__ == '__main__':
    unittest.main()
