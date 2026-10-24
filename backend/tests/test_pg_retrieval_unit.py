"""SQL transport tests written before the PostgreSQL retrieval adapter."""
import unittest
from app.knowledge import Scope
from app.pg_retrieval import retrieve_postgres


class Result:
    def __init__(self, rows): self.rows = rows
    def mappings(self): return self
    def all(self): return self.rows


class Connection:
    def __init__(self): self.calls = []
    def exec_driver_sql(self, sql, params):
        self.calls.append((sql, params))
        rows = [{'id':'chunk-1','source_id':'doc-1','tenant_id':'tenant','task_id':'task','release_id':'release',
                 'locator':'Page 2','text':'approved evidence','token_count':2,'embedding':'[1,0]','available':True}]
        return Result(rows)


class PostgreSQLRetrievalTests(unittest.TestCase):
    def test_authorized_cte_precedes_both_rankers_and_inputs_are_bound(self):
        connection = Connection()
        chunks = retrieve_postgres(connection, Scope('tenant','task','release'), "' OR 1=1 --", query_embedding=(1,0))
        self.assertEqual(len(connection.calls), 2)
        self.assertEqual(chunks[0].source_id, 'doc-1')
        for sql, params in connection.calls:
            self.assertIn('AS MATERIALIZED', sql)
            self.assertIn('tenant_id = %(tenant_id)s', sql)
            self.assertIn('task_id = %(task_id)s', sql)
            self.assertIn('release_id = %(release_id)s', sql)
            self.assertIn('available = true', sql)
            self.assertNotIn("' OR 1=1 --", sql)
            self.assertEqual(params['tenant_id'], 'tenant')
            self.assertEqual(params['task_id'], 'task')
            self.assertEqual(params['release_id'], 'release')
        self.assertIn('<=>', connection.calls[1][0])
        self.assertIn('vector_dims', connection.calls[1][0])

    def test_defense_in_depth_filters_bad_transport_rows(self):
        class BadConnection(Connection):
            def exec_driver_sql(self, sql, params):
                result = super().exec_driver_sql(sql, params)
                result.rows[0]['tenant_id'] = 'another-tenant'
                return result
        self.assertEqual(retrieve_postgres(BadConnection(),Scope('tenant','task','release'),'evidence'), [])

    def test_budget_and_invalid_embedding_are_checked(self):
        self.assertEqual(retrieve_postgres(Connection(),Scope('tenant','task','release'),'evidence',token_budget=1), [])
        with self.assertRaises(ValueError):
            retrieve_postgres(Connection(),Scope('tenant','task','release'),'evidence',query_embedding=(float('nan'),))
        with self.assertRaises(ValueError):
            retrieve_postgres(Connection(),Scope('tenant','task','release'),'evidence',token_budget=0)


if __name__ == '__main__': unittest.main()
