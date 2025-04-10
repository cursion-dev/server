from __future__ import absolute_import, unicode_literals
from celery import Celery
from celery.signals import worker_shutdown
from django.conf import settings
import cursion, os, time






# setting DJANGO_SETTINGS_MODULE to cursion.settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cursion.settings')

# init celery
app = Celery('cursion')

# configure namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# celery and beat configs
app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_hijack_root_logger=False,
    task_always_eager=False,
    task_reject_on_worker_lost=True,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    worker_max_tasks_per_child=100
)

# setting tasks to auto-discover
app.autodiscover_tasks()

# setting debug
@app.task(bind=False)
def debug_task(self):
    print(f'Request: {self.request}')

# notify of SIGTERM
@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    print(f'- WORKER SHUTTING DOWN - \n{kwargs}')

    


