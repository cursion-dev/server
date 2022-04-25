from __future__ import absolute_import, unicode_literals
from celery import Celery
from django.conf import settings
import scanerr, os


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scanerr.settings')

app = Celery('scanerr')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.task(bind=False)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))

