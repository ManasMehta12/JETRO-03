"""Portable release index with real PostgreSQL full-text/pgvector rank queries.

PostgreSQL requires migration 0004 and CREATE EXTENSION vector privileges during
migration. Scope filtering is materialized before either ranker. Model-specific
embeddings are supplied by the trusted indexing pipeline, never by learners.
"""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from .knowledge import Scope, Chunk, chunk_source, hybrid_retrieve, ingest_bytes


_AUTHORIZED = '''WITH authorized AS MATERIALIZED (
 SELECT id, source_id, tenant_id, task_id, release_id, locator, text, token_count, embedding, available
 FROM knowledge_chunks
 WHERE tenant_id = %(tenant_id)s AND task_id = %(task_id)s
   AND release_id = %(release_id)s AND available = true
)'''
_LEXICAL = _AUTHORIZED + '''
SELECT id, source_id, tenant_id, task_id, release_id, locator, text, token_count, embedding::text AS embedding, available,
 ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', %(query)s)) AS score
FROM authorized
WHERE to_tsvector('english', text) @@ plainto_tsquery('english', %(query)s)
ORDER BY score DESC, id LIMIT %(candidate_limit)s'''
_VECTOR = _AUTHORIZED + '''
SELECT id, source_id, tenant_id, task_id, release_id, locator, text, token_count, embedding::text AS embedding, available,
 embedding <=> CAST(%(query_embedding)s AS vector) AS distance
FROM authorized
WHERE embedding IS NOT NULL AND vector_dims(embedding) = %(dimensions)s
 AND (1 - (embedding <=> CAST(%(query_embedding)s AS vector))) > 0
ORDER BY distance ASC, id LIMIT %(candidate_limit)s'''


def _vector(value):
    if value is None:
        return None
    values = json.loads(value) if isinstance(value,str) else value
    if not isinstance(values,(list,tuple)) or not values or not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in values):
        raise ValueError('Embedding must contain finite numeric dimensions')
    return tuple(float(v) for v in values)


def _chunk(row):
    return Chunk(row['id'],row['source_id'],Scope(row['tenant_id'],row['task_id'],row['release_id']),
                 row['locator'],row['text'],row['token_count'],bool(row['available']),_vector(row.get('embedding')))


def retrieve_postgres(connection, scope, query, *, query_embedding=None, max_passages=8, token_budget=4800):
    if type(token_budget) is not int or token_budget <= 0 or type(max_passages) is not int or max_passages <= 0:
        raise ValueError('Positive token and passage budgets are required')
    vector = _vector(query_embedding)
    params = {'tenant_id':scope.tenant_id,'task_id':scope.task_id,'release_id':scope.release_id,
              'query':query,'candidate_limit':100}
    rankings = [connection.exec_driver_sql(_LEXICAL,params).mappings().all()]
    if vector is not None:
        rankings.append(connection.exec_driver_sql(_VECTOR,{**params,'query_embedding':json.dumps(vector),'dimensions':len(vector)}).mappings().all())
    scores = Counter()
    candidates = {}
    for rows in rankings:
        for rank,row in enumerate(rows,start=1):
            chunk = _chunk(row)
            if chunk.scope != scope or not chunk.available:
                continue
            candidates[chunk.id] = chunk
            scores[chunk.id] += 1.0/(60+rank)
    selected = []
    used = 0
    for chunk_id in sorted(scores,key=lambda value:(-scores[value],value)):
        chunk = candidates[chunk_id]
        if used+chunk.token_count <= token_budget:
            selected.append(chunk)
            used += chunk.token_count
        if len(selected) >= min(8,max_passages):
            break
    return selected


def retrieve(database, scope, query, *, query_embedding=None, max_passages=8, token_budget=4800):
    if database.engine.dialect.name == 'postgresql':
        with database.engine.connect() as connection:
            return retrieve_postgres(connection,scope,query,query_embedding=query_embedding,
                                     max_passages=max_passages,token_budget=token_budget)
    from sqlalchemy import select
    from .models import KnowledgeChunk
    with database.session_factory() as db:
        rows = db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.tenant_id==scope.tenant_id,
                           KnowledgeChunk.task_id==scope.task_id,KnowledgeChunk.release_id==scope.release_id,
                           KnowledgeChunk.available.is_(True)))
        chunks = [Chunk(row.id,row.source_id,scope,row.locator,row.text,row.token_count,row.available,_vector(row.embedding)) for row in rows]
    return hybrid_retrieve(query,chunks,scope,query_embedding=query_embedding,max_passages=max_passages,token_budget=token_budget)


def has_release_index(database, scope, required_document_ids=None):
    from sqlalchemy import select
    from .models import KnowledgeChunk
    with database.session_factory() as db:
        sources = set(db.scalars(select(KnowledgeChunk.source_id).where(KnowledgeChunk.tenant_id==scope.tenant_id,
                    KnowledgeChunk.task_id==scope.task_id,KnowledgeChunk.release_id==scope.release_id,KnowledgeChunk.available.is_(True))))
    return bool(sources) and (required_document_ids is None or set(required_document_ids) <= sources)


def index_chunks(database, chunks):
    from .models import KnowledgeChunk
    inserted = 0
    with database.session_factory.begin() as db:
        for chunk in chunks:
            _vector(chunk.embedding)
            existing = db.get(KnowledgeChunk,chunk.id)
            fields = {'id':chunk.id,'source_id':chunk.source_id,'tenant_id':chunk.scope.tenant_id,'task_id':chunk.scope.task_id,
                      'release_id':chunk.scope.release_id,'locator':chunk.locator,'text':chunk.text,
                      'token_count':chunk.token_count,'available':chunk.available,'embedding':list(chunk.embedding) if chunk.embedding is not None else None}
            if existing:
                if any(getattr(existing,name) != value for name,value in fields.items()):
                    raise ValueError('An immutable indexed chunk cannot be overwritten')
                continue
            db.add(KnowledgeChunk(**fields))
            inserted += 1
    return inserted


def index_file(database, release_id, document_id, tenant_id, path, embeddings=None):
    """Local operator import; original bytes must match approved manifest checksum."""
    from .models import Release
    with database.session_factory() as db:
        release = db.get(Release,release_id)
        if not release:
            raise ValueError('Approved release does not exist')
        expected_tenant = release.data.get('tenant_id','demo' if database.settings.demo_database else None)
        if expected_tenant != tenant_id:
            raise PermissionError('Release belongs to a different tenant')
        if not database.settings.demo_database and release.data.get('content_status') != 'approved':
            raise ValueError('Only approved release documents may be indexed')
        document = next((doc for doc in release.data.get('documents',[]) if doc['id']==document_id),None)
        if document is None or document.get('availability') != 'available':
            raise ValueError('Document is not an available member of this release')
        document = dict(document)
        scope = Scope(tenant_id,release.task_id,release_id)
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != document['checksum']:
        raise ValueError('Source bytes differ from the approved manifest checksum')
    source = ingest_bytes(raw,source_id=document_id,scope=scope,title=document['title'],
                          media_type=document['media_type'],version=document['version'])
    chunks = chunk_source(source)
    if embeddings:
        from dataclasses import replace
        if set(embeddings) != {chunk.id for chunk in chunks}:
            raise ValueError('Embeddings must cover exactly this document chunk set')
        chunks = [replace(chunk,embedding=_vector(embeddings[chunk.id])) for chunk in chunks]
    return {'chunks':len(chunks),'inserted':index_chunks(database,chunks),'source_checksum':source.checksum}
