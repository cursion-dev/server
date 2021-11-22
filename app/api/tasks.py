from __future__ import absolute_import, unicode_literals
from celery.utils.log import get_task_logger
from celery import shared_task
from .v1.ops.tasks import (create_site_task, 
    create_scan_task, create_test_task
)
from .models import Log
from django.contrib.auth.models import User

logger = get_task_logger(__name__)


@shared_task
def create_site_bg(site_id):
    create_site_task(site_id)
    logger.info('Created scan of new site')


@shared_task
def create_scan_bg(site_id, automation_id=None):
    create_scan_task(site_id, automation_id)
    logger.info('Created new scan of site')


@shared_task
def create_test_bg(site_id, automation_id=None):
    create_test_task(site_id, automation_id)
    logger.info('Created new test of site')


@shared_task
def purge_logs(username=None):
    if username:
        user = User.objcets.get(username=username)
        Log.objects.filter(user=user).delete()
    else:
        Log.objects.all().delete()

    logger.info('Purged logs')