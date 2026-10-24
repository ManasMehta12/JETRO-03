"""Local retention/deletion of learner-derived Viva data; sources stay immutable."""
from datetime import timedelta
from sqlalchemy import select, delete, text, func
from .models import (VivaSession, InterviewTurn, SessionEvent, EvaluationJob, VivaReport,
                     VoiceConnection, ProviderReceipt, ProviderUsage, IdempotencyRecord, AuditEvent, now)
from . import service


DERIVED = (ProviderUsage, VivaReport, EvaluationJob, ProviderReceipt, VoiceConnection,
           SessionEvent, InterviewTurn, IdempotencyRecord)


def _delete(database, *, learner_id=None, cutoff=None, action):
    result = {'deleted_session_ids': [], 'skipped_session_ids': []}
    with service._LOCK, database.session_factory() as db:
        if database.engine.dialect.name == 'sqlite':
            db.execute(text('BEGIN IMMEDIATE'))
        else:
            db.begin()
        try:
            query = select(VivaSession).order_by(VivaSession.id).with_for_update()
            if learner_id is not None:
                query = query.where(VivaSession.learner_id == learner_id)
            if cutoff is not None:
                query = query.where(VivaSession.created_at < cutoff)
            for session in db.scalars(query):
                sid = session.id
                active_job = db.scalar(select(EvaluationJob.id).where(EvaluationJob.session_id == sid, EvaluationJob.status.in_(['queued','running'])))
                active_voice = db.scalar(select(VoiceConnection.id).where(VoiceConnection.session_id == sid, VoiceConnection.status.in_(['active','connecting'])))
                reserved_usage = db.scalar(select(ProviderUsage.id).where(ProviderUsage.session_id == sid, ProviderUsage.status == 'reserved'))
                if active_job or active_voice or reserved_usage or session.status in ('connecting','in_progress'):
                    result['skipped_session_ids'].append(sid)
                    continue
                if cutoff is not None:
                    last_turn = db.scalar(select(func.max(InterviewTurn.created_at)).where(InterviewTurn.session_id == sid))
                    last_report = db.scalar(select(func.max(VivaReport.created_at)).where(VivaReport.session_id == sid))
                    if any(value is not None and service.aware(value) >= cutoff for value in (last_turn,last_report)):
                        result['skipped_session_ids'].append(sid)
                        continue
                for model in DERIVED:
                    db.execute(delete(model).where(model.session_id == sid))
                db.delete(session)
                db.add(AuditEvent(actor_id='operator-cli',action=action,target_id=sid))
                result['deleted_session_ids'].append(sid)
            db.commit()
        except Exception:
            db.rollback()
            raise
    return result


def purge_retention(database, days=None):
    retention = days if days is not None else getattr(database.settings, 'retention_days', 30)
    if type(retention) is not int or retention <= 0:
        raise ValueError('Retention days must be a positive integer')
    return _delete(database, cutoff=now()-timedelta(days=retention), action='purge_retention')


def delete_learner_data(database, learner_id, *, confirm=False):
    if not confirm or not isinstance(learner_id,str) or not learner_id.strip():
        raise RuntimeError('Learner deletion requires an exact internal learner ID and --confirm-delete')
    return _delete(database, learner_id=learner_id, action='delete_learner_derived_data')
