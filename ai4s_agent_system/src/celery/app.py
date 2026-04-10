from celery import Celery
import os

celery_app = Celery(
    'agent_system',
    broker=os.getenv('CELERY_BROKER_URL', 'amqp://admin:admin@localhost:5672/'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=['src.celery.tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes timeout
    task_soft_time_limit=540,  # 9 minutes soft timeout
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
)

if __name__ == '__main__':
    celery_app.start()
