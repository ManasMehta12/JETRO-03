"""Optional Celery/Redis adapter; database leases remain authoritative.

Run worker/beat only after installing requirements-extras.txt and configuring
VIVA_REDIS_URL. Imports remain safe when Celery is not installed.
"""
import os


def evaluate_pending():
    from .db import get_database
    from .worker import process_once
    database = get_database()
    try:
        database.initialize()
        return process_once(database)
    finally:
        database.engine.dispose()


def purge_expired_derived_data():
    from .db import get_database
    from .maintenance import purge_retention
    database = get_database()
    try:
        database.initialize()
        return purge_retention(database)
    finally:
        database.engine.dispose()


def create_celery():
    try:
        from celery import Celery
    except ImportError as exc:
        raise RuntimeError('Celery adapter requires the optional celery[redis] dependency') from exc
    broker = os.getenv('VIVA_REDIS_URL','')
    if not broker.startswith(('redis://','rediss://')):
        raise RuntimeError('VIVA_REDIS_URL must be an explicitly configured Redis broker URL')
    app = Celery('technical_viva',broker=broker)
    app.conf.update(task_serializer='json',accept_content=['json'],result_serializer='json',
                    task_ignore_result=True,worker_prefetch_multiplier=1,timezone='UTC',
                    beat_schedule={'evaluate-pending':{'task':'viva.evaluate_pending','schedule':2.0},
                                   'purge-retention':{'task':'viva.purge_retention','schedule':86400.0}})
    app.task(name='viva.evaluate_pending')(evaluate_pending)
    app.task(name='viva.purge_retention')(purge_expired_derived_data)
    return app


# Importing this module without a configured broker does not import Celery.
# A configured deployment uses: celery -A app.tasks:celery_app worker
celery_app = create_celery() if os.getenv('VIVA_REDIS_URL') else None
