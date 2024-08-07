from __future__ import absolute_import, unicode_literals
from celery import Celery
from django.conf import settings
import scanerr, os






# setting DJANGO_SETTINGS_MODULE to scanerr.settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scanerr.settings')

# init celery
app = Celery('scanerr')

# configure namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# celery and beat configs
app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_hijack_root_logger=False,
    task_always_eager=False,
)

# setting tasks to auto-discover
app.autodiscover_tasks()

# setting debug
@app.task(bind=False)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))

