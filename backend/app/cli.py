"""Local operator commands; never exposed as public HTTP endpoints."""
import argparse
from sqlalchemy import select, delete
from .config import Settings
from .db import Database
from .models import (PlaygroundAttempt,VivaSession,InterviewTurn,SessionEvent,EvaluationJob,VivaReport,
    VoiceConnection,ProviderReceipt,IdempotencyRecord,AuditEvent,ProviderUsage)


def reset_demo(database,confirm=False):
    if not confirm or not database.settings.demo_database or not database.settings.seed_demo:
        raise RuntimeError('Reset refused: explicitly marked seeded demo database and --confirm-demo are required')
    with database.session_factory.begin() as db:
        attempts=[a for a in db.scalars(select(PlaygroundAttempt)) if a.data.get('is_demo') is True]
        attempt_ids=[a.id for a in attempts]
        sessions=list(db.scalars(select(VivaSession).where(VivaSession.attempt_id.in_(attempt_ids)))) if attempt_ids else []
        ids=[s.id for s in sessions]
        if ids and db.scalar(select(VoiceConnection.id).where(VoiceConnection.session_id.in_(ids),VoiceConnection.status.in_(['active','connecting']))):
            raise RuntimeError('Reset refused: close live voice connections first')
        if ids and db.scalar(select(EvaluationJob.id).where(EvaluationJob.session_id.in_(ids),EvaluationJob.status.in_(['queued','running']))):
            raise RuntimeError('Reset refused: finish or stop active evaluation jobs first')
        counts={}
        for model in (ProviderUsage,VivaReport,EvaluationJob,ProviderReceipt,VoiceConnection,SessionEvent,InterviewTurn,IdempotencyRecord):
            result=db.execute(delete(model).where(model.session_id.in_(ids))) if ids else None
            counts[model.__tablename__]=result.rowcount if result else 0
        if ids:db.execute(delete(VivaSession).where(VivaSession.id.in_(ids)))
        if attempt_ids:db.execute(delete(PlaygroundAttempt).where(PlaygroundAttempt.id.in_(attempt_ids)))
        counts['viva_sessions']=len(ids);counts['playground_attempts']=len(attempt_ids)
        db.add(AuditEvent(actor_id='operator-cli',action='reset_demo',target_id='demo-learners'))
        return counts


def retry_evaluation(database,job_id):
    with database.session_factory.begin() as db:
        job=db.get(EvaluationJob,job_id)
        if not job or job.status!='failed':raise RuntimeError('Only a failed evaluation can be retried')
        session=db.get(VivaSession,job.session_id)
        if session.result_id:raise RuntimeError('Published reports cannot be overwritten')
        job.status='queued';job.attempt_count=0;job.error_code=None;job.lease_until=None;job.next_attempt_at=None;job.retryable=True
        session.status='evaluating';session.revision+=1
        db.add(AuditEvent(actor_id='operator-cli',action='retry_evaluation',target_id=job_id))


def main():
    parser=argparse.ArgumentParser(description='Technical Viva local operator tools')
    commands=parser.add_subparsers(dest='command',required=True)
    reset=commands.add_parser('reset-demo');reset.add_argument('--confirm-demo',action='store_true')
    commands.add_parser('seed-demo')
    retention=commands.add_parser('purge-retention');retention.add_argument('--days',type=int)
    deletion=commands.add_parser('delete-learner');deletion.add_argument('learner_id');deletion.add_argument('--confirm-delete',action='store_true')
    retry=commands.add_parser('retry-evaluation');retry.add_argument('job_id')
    args=parser.parse_args();settings=Settings.from_env();database=Database(settings.database_url,settings);database.initialize()
    try:
        if args.command=='purge-retention':
            from .maintenance import purge_retention
            print(purge_retention(database,args.days))
        elif args.command=='delete-learner':
            from .maintenance import delete_learner_data
            print(delete_learner_data(database,args.learner_id,confirm=args.confirm_delete))
        elif args.command=='reset-demo':print(reset_demo(database,args.confirm_demo))
        elif args.command=='seed-demo':
            if not settings.demo_database:raise RuntimeError('Seeding is restricted to demo databases')
            from .seed import seed
            seed(database);print('Demo content seeded; instructor review is required before operational use.')
        elif args.command=='retry-evaluation':retry_evaluation(database,args.job_id);print('Evaluation queued with unchanged frozen inputs.')
    except (RuntimeError,ValueError) as exc:parser.exit(2,str(exc)+'\n')

if __name__=='__main__':main()
