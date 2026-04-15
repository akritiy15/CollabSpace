import os
from celery import Celery
from celery.schedules import crontab
from app import create_app

def make_celery(app):
    celery = Celery(
        app.import_name,
        broker=app.config.get('REDIS_URL', 'redis://localhost:6379/0'),
        backend=app.config.get('REDIS_URL', 'redis://localhost:6379/0')
    )
    celery.conf.update(app.config)
    
    celery.conf.task_serializer = 'json'
    celery.conf.result_serializer = 'json'
    celery.conf.timezone = 'Asia/Kolkata'
    celery.conf.enable_utc = True
    celery.conf.imports = ['app.tasks.email_tasks']
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

flask_app = create_app()
celery = make_celery(flask_app)

celery.conf.beat_schedule = {
    'check-deadlines-daily': {
        'task': 'tasks.check_upcoming_deadlines',
        'schedule': crontab(hour=9, minute=0),
    },
    'weekly-reports-monday': {
        'task': 'tasks.send_weekly_reports_all_groups',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),
    },
}
