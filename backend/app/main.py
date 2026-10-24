"""Authenticated FastAPI endpoints for the Technical Viva application."""
import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request, Depends, Header, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, RedirectResponse
from sqlalchemy import select, text
from .config import Settings
from .auth import resolve_actor, AuthError
from .db import Database
from .models import Release, PlaygroundAttempt, VivaSession, SessionEvent, EvaluationJob, VivaReport, IdempotencyRecord
from .schemas import StartRequest, AnswerRequest, RevisionRequest, ResumeRequest, RepeatRequest, FlagRequest, ConnectionRequest
from . import service
from .schemas import (VivaSessionSchema, AnswerResponse, EventsResponse, EvaluationJobSchema, VivaReportSchema,
    FlagResponse, ConnectionResponse, ConnectionReadyRequest, PublicReleaseSchema, DocumentResponse, BootstrapSchema, ErrorSchema)
from .seed import seed


def create_app(settings: Optional[Settings]=None, provider=None):
    settings=settings or Settings.from_env()
    database=Database(settings.database_url,settings)

    async def timer():
        while True:
            await asyncio.sleep(5)
            await asyncio.to_thread(service.sweep_expired,database)
            if settings.run_inline_worker:
                from .worker import process_once
                await asyncio.to_thread(process_once,database)

    @asynccontextmanager
    async def lifespan(app):
        database.initialize()
        if settings.seed_demo:seed(database)
        # A restart cannot resume a previous process's live WebRTC sideband.
        from .models import VoiceConnection, ProviderUsage
        with database.session_factory.begin() as db:
            for session in db.scalars(select(VivaSession).where(VivaSession.status.in_(['connecting','in_progress']),VivaSession.input_mode=='voice')):
                service.pause(db,session,{'expected_revision':session.revision},settings)
            for connection in db.scalars(select(VoiceConnection).where(VoiceConnection.status.in_(['active','connecting']))):connection.status='closed'
            for usage in db.scalars(select(ProviderUsage).where(ProviderUsage.status=='reserved',ProviderUsage.request_kind=='audio')):
                usage.status='settled';usage.actual_microdollars=usage.reserved_microdollars;usage.usage={'outcome':'api_restart_unknown'};usage.settled_at=service.now()
        task=asyncio.create_task(timer())
        yield
        task.cancel()
        try:await task
        except asyncio.CancelledError:pass
        from .voice import shutdown
        await shutdown()
        database.engine.dispose()

    app=FastAPI(title='Takumi Technical Viva',version='2.0.0',lifespan=lifespan)
    app.state.db=database;app.state.settings=settings
    app.add_middleware(CORSMiddleware,allow_origins=[settings.allowed_origin],allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['Authorization','Content-Type','Idempotency-Key'])

    @app.exception_handler(service.DomainError)
    async def domain_error(request,exc):
        return JSONResponse(status_code=exc.status,content={'code':exc.code,'message':exc.message,'details':exc.details})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        return JSONResponse(status_code=422,content={'code':'validation_error','message':'Invalid request values','details':{'fields':[{'location':list(e['loc']),'message':e['msg']} for e in exc.errors()]}})

    @app.middleware('http')
    async def cap_request(request,call_next):
        size=request.headers.get('content-length')
        if size:
            try:
                if int(size)>150000:return JSONResponse(status_code=413,content={'code':'body_too_large','message':'Request exceeds the 150 KB limit','details':{}})
            except ValueError:
                return JSONResponse(status_code=422,content={'code':'invalid_length','message':'Invalid Content-Length','details':{}})
        if request.method in ('POST','PUT','PATCH'):
            chunks=[];total=0
            async for chunk in request.stream():
                total+=len(chunk)
                if total>150000:return JSONResponse(status_code=413,content={'code':'body_too_large','message':'Request exceeds the 150 KB limit','details':{}})
                chunks.append(chunk)
            request._body=b''.join(chunks)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response

    def actor(authorization: Optional[str]=Header(None)):
        try:
            return resolve_actor(authorization,settings)
        except AuthError as exc:
            raise service.DomainError(exc.status,exc.code,exc.message)

    def learner(identity=Depends(actor)):
        if 'learner' not in identity.roles:raise service.DomainError(403,'forbidden_role','A learner session is required')
        return identity

    def key(idempotency_key: Optional[str]=Header(None)):
        if not idempotency_key or len(idempotency_key)>128:raise service.DomainError(422,'idempotency_key_required','Provide an Idempotency-Key of 1–128 characters')
        return idempotency_key

    def queue_inline(background):
        if settings.run_inline_worker:
            from .worker import process_once
            background.add_task(process_once,database)

    def session_mutation(sid,identity,idempotency,payload,name,callback):
        return service.mutate(database,identity,f'/viva/sessions/{sid}/{name}',idempotency,payload,
            lambda db:callback(db,service.owned(db,sid,identity,True)),sid)

    @app.get('/health')
    def health():return {'status':'ok','provider_mode':settings.provider_mode,'version':'2.0.0'}

    @app.get('/ready')
    def ready():
        with database.session_factory() as db:db.execute(text('SELECT 1'))
        if settings.provider_mode=='openai' and not settings.openai_api_key:raise service.DomainError(503,'provider_not_configured','Provider API key is not configured')
        if settings.provider_mode=='openai':
            from .budget import parse_pricing
            parse_pricing(settings)
        return {'status':'ready','provider_mode':settings.provider_mode}

    @app.get('/api/v1/demo/bootstrap',include_in_schema=False)
    @app.get('/api/v1/bootstrap',response_model=BootstrapSchema)
    def bootstrap(identity=Depends(learner)):
        with database.session_factory() as db:
            attempts=list(db.scalars(select(PlaygroundAttempt).where(PlaygroundAttempt.learner_id==identity,PlaygroundAttempt.status=='completed')))
            if not settings.demo_database:
                attempts=[a for a in attempts if db.get(Release,a.release_id) and db.get(Release,a.release_id).data.get('tenant_id')==identity.tenant_id]
            release=db.get(Release,attempts[0].release_id) if attempts else None
            return {'provider_mode':settings.provider_mode,'learner_id':identity,'content_notice':'Illustrative demonstration content; instructor approval is required before operational assessment.',
                'attempts':[{'id':a.id,'title':a.data.get('title',a.scenario_id),'scenario_id':a.scenario_id,'status':a.status,'critical_error':a.data.get('critical_error',False),'release_id':a.release_id} for a in attempts],
                'release':public_release(release) if release else None}

    @app.post('/api/v1/viva/sessions',response_model=VivaSessionSchema)
    def start(payload:StartRequest,identity=Depends(learner),idempotency=Depends(key)):
        data=payload.model_dump()
        return service.mutate(database,identity,'/viva/sessions',idempotency,data,lambda db:service.start(db,identity,data,settings))

    @app.get('/api/v1/viva/sessions/{sid}',response_model=VivaSessionSchema)
    def read_session(sid:str,identity=Depends(learner)):
        with database.session_factory() as db:return service.public_session(db,service.owned(db,sid,identity),settings)

    @app.post('/api/v1/viva/sessions/{sid}/answers',status_code=202,response_model=AnswerResponse)
    def answers(sid:str,payload:AnswerRequest,background:BackgroundTasks,identity=Depends(learner),idempotency=Depends(key)):
        try:
            result=service.submit_answer(database,sid,identity,idempotency,payload.model_dump())
        except service.DomainError:raise
        except Exception as exc:
            from .provider import ProviderUnavailable, InvalidAssessment
            if isinstance(exc,(ProviderUnavailable,InvalidAssessment)):raise service.DomainError(503,'provider_unavailable','The interviewer is temporarily unavailable; retry without changing your answer')
            raise
        if result['session']['status']=='evaluating':queue_inline(background)
        return result

    @app.get('/api/v1/viva/sessions/{sid}/events',response_model=EventsResponse)
    def events(sid:str,after:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100),identity=Depends(learner)):
        with database.session_factory() as db:
            service.owned(db,sid,identity)
            values=list(db.scalars(select(SessionEvent).where(SessionEvent.session_id==sid,SessionEvent.sequence>after).order_by(SessionEvent.sequence).limit(limit+1)))
            return {'events':[{'id':e.id,'sequence':e.sequence,'session_revision':e.session_revision,'type':e.type,'payload':e.payload,'created_at':service.stamp(e.created_at)} for e in values[:limit]],
                'next_after':values[min(len(values),limit)-1].sequence if values else after,'has_more':len(values)>limit}

    @app.post('/api/v1/viva/sessions/{sid}/pause',response_model=VivaSessionSchema)
    def pause(sid:str,payload:RevisionRequest,identity=Depends(learner),idempotency=Depends(key)):
        data=payload.model_dump();return session_mutation(sid,identity,idempotency,data,'pause',lambda db,s:service.pause(db,s,data,settings))

    @app.post('/api/v1/viva/sessions/{sid}/resume',response_model=VivaSessionSchema)
    def resume(sid:str,payload:ResumeRequest,identity=Depends(learner),idempotency=Depends(key)):
        data=payload.model_dump();return session_mutation(sid,identity,idempotency,data,'resume',lambda db,s:service.resume(db,s,data,settings))

    @app.post('/api/v1/viva/sessions/{sid}/repeat',status_code=202,response_model=VivaSessionSchema)
    def repeat(sid:str,payload:RepeatRequest,identity=Depends(learner),idempotency=Depends(key)):
        data=payload.model_dump();return session_mutation(sid,identity,idempotency,data,'repeat',lambda db,s:service.repeat(db,s,data,settings))

    @app.post('/api/v1/viva/sessions/{sid}/transcript-flags',response_model=FlagResponse)
    def flag(sid:str,payload:FlagRequest,identity=Depends(learner),idempotency=Depends(key)):
        data=payload.model_dump();return session_mutation(sid,identity,idempotency,data,'transcript-flags',lambda db,s:service.flag(db,s,data,settings))

    @app.post('/api/v1/viva/sessions/{sid}/finish',status_code=202,response_model=EvaluationJobSchema)
    async def finish(sid:str,payload:RevisionRequest,background:BackgroundTasks,identity=Depends(learner),idempotency=Depends(key)):
        data=payload.model_dump()
        drained=False
        with database.session_factory() as db:
            current=service.owned(db,sid,identity)
            if not current.evaluation_job_id:
                service.revision(current,data['expected_revision'])
                voice_mode=current.input_mode=='voice'
            else:voice_mode=False
        if voice_mode:
            from .voice import drain_pending
            await drain_pending(database,sid,identity)
            drained=True
        def complete(db,s):
            if not s.evaluation_job_id and not drained:service.revision(s,data['expected_revision'])
            return service.finish(db,s,settings,'time_limit' if service.elapsed(s)>=settings.max_active_seconds else 'learner_finished')
        result=session_mutation(sid,identity,idempotency,data,'finish',complete)
        if voice_mode:
            from .voice import close_session
            await close_session(database,sid)
        queue_inline(background);return result

    @app.get('/api/v1/viva/sessions/{sid}/evaluation',response_model=EvaluationJobSchema)
    def evaluation(sid:str,identity=Depends(learner)):
        with database.session_factory() as db:
            session=service.owned(db,sid,identity)
            if not session.evaluation_job_id:raise service.DomainError(409,'evaluation_not_started','Finish the interview before requesting evaluation')
            return service.job_dict(db.get(EvaluationJob,session.evaluation_job_id))

    @app.get('/api/v1/viva/sessions/{sid}/result',response_model=VivaReportSchema)
    def result(sid:str,identity=Depends(learner)):
        with database.session_factory() as db:
            session=service.owned(db,sid,identity)
            if not session.result_id:raise service.DomainError(409,'result_not_ready','The evaluation report is not ready')
            return db.get(VivaReport,session.result_id).data

    @app.post('/api/v1/viva/sessions/{sid}/connection',response_model=ConnectionResponse)
    async def connection(sid:str,payload:ConnectionRequest,identity=Depends(learner),idempotency=Depends(key)):
        from .voice import negotiate
        try:
            return await negotiate(database,sid,identity,payload.model_dump(),settings,idempotency)
        except service.DomainError:raise
        except Exception:
            raise service.DomainError(503,'voice_unavailable','Voice connection could not be established; retry or use text')

    @app.post('/api/v1/viva/sessions/{sid}/connection/ready',response_model=VivaSessionSchema)
    async def connection_ready(sid:str,payload:ConnectionReadyRequest,identity=Depends(learner),idempotency=Depends(key)):
        from .voice import ready_connection
        return await ready_connection(database,sid,identity,payload.model_dump(),idempotency)

    def authorize_release(db,rid,identity):
        release=db.get(Release,rid)
        scope=db.scalar(select(PlaygroundAttempt.id).where(PlaygroundAttempt.release_id==rid,PlaygroundAttempt.learner_id==identity))
        same_tenant = settings.demo_database or (release is not None and release.data.get('tenant_id') == identity.tenant_id)
        if not release or not same_tenant or (not scope and 'operator' not in identity.roles):raise service.DomainError(404,'not_found','Knowledge release not found')
        return release

    from .provider import public_document
    def public_release(release):
        return {'id':release.id,'task_id':release.task_id,'title':release.title,'content_hash':release.content_hash,
            'content_status':release.data.get('content_status'),'documents':[public_document(d) for d in release.data.get('documents',[])],
            'evidence':release.data.get('evidence',[]),'units':release.data.get('units',[])}

    @app.get('/api/v1/studio/releases/{rid}',response_model=PublicReleaseSchema)
    def release(rid:str,identity=Depends(actor)):
        with database.session_factory() as db:return public_release(authorize_release(db,rid,identity))

    @app.get('/api/v1/studio/releases/{rid}/documents/{did}',response_model=DocumentResponse)
    def document(rid:str,did:str,identity=Depends(actor)):
        with database.session_factory() as db:
            rel=authorize_release(db,rid,identity)
            doc=next((d for d in rel.data['documents'] if d['id']==did),None)
            if not doc:raise service.DomainError(404,'not_found','Source document not found in this release')
            return {'document':public_document(doc),'evidence':[e for e in rel.data['evidence'] if e['id'] in doc['evidence_ids']]}

    @app.get('/api/v1/studio/releases/{rid}/documents/{did}/content')
    def document_content(rid:str,did:str,identity=Depends(actor)):
        with database.session_factory() as db:
            rel=authorize_release(db,rid,identity)
            doc=next((d for d in rel.data['documents'] if d['id']==did),None)
            if not doc or doc.get('availability')!='available':raise service.DomainError(404,'not_found','Source document is unavailable')
            headers={'Content-Disposition':'attachment; filename="source"','Content-Security-Policy':"default-src 'none'; sandbox"}
            if 'content' in doc:
                return Response(content=doc['content'],media_type=doc.get('media_type','text/plain'),headers=headers)
            from .knowledge import Scope
            from .storage import LocalStorage, S3Storage
            owner=Scope(rel.data.get('tenant_id','demo'),rel.task_id,rel.id)
            requester=Scope(identity.tenant_id,rel.task_id,rel.id)
            storage=doc.get('storage',{})
            try:
                if storage.get('type')=='local':
                    content=LocalStorage(settings.media_directory).read(storage['key'],owner_scope=owner,requester_scope=requester)
                    return Response(content=content,media_type=doc.get('media_type','application/octet-stream'),headers=headers)
                if storage.get('type')=='s3':
                    source=S3Storage(os.environ['VIVA_OBJECT_STORAGE_BUCKET'],endpoint_url=os.getenv('VIVA_OBJECT_STORAGE_ENDPOINT') or None)
                    return RedirectResponse(source.signed_url(storage['key'],owner_scope=owner,requester_scope=requester),status_code=302)
            except (PermissionError,FileNotFoundError,KeyError,ValueError):
                raise service.DomainError(404,'not_found','Source document is unavailable')
            raise service.DomainError(404,'not_found','Source document has no available original artifact')

    return app

app=create_app()
