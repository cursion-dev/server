from __future__ import absolute_import, unicode_literals
from typing import Any
from celery.utils.log import get_task_logger
from celery import shared_task
from celery import Task as BaseTask
from .v1.ops.tasks import *
from .bootstrap.logger import producer_log
from .models import Log
from django.contrib.auth.models import User
from .utils.driver_p import driver_test
from asgiref.sync import async_to_sync
import asyncio


logger = get_task_logger(__name__)


class ScannerApiTask(BaseTask):
    def delay(
            self,
            *args,
            **kwargs,
    ) -> Any:
        """
        Producer handler.

        :rtype Any:
        """
        result = self.apply_async(args, kwargs)

        producer_log.info("CELERY_TASK_QUEUED - ID: %s", result.id)

        return result



@shared_task(base=ScannerApiTask)
def test_pupeteer():
    asyncio.run(driver_test())
    logger.info('Tested pupeteer instalation')


@shared_task(base=ScannerApiTask)
def create_site_bg(site_id, scan_id, configs=None):
    create_site_task(site_id, scan_id, configs)
    logger.info('Created scan of new site')


@shared_task(base=ScannerApiTask)
def create_scan_bg(
        scan_id=None,
        site_id=None, 
        type=['full'],
        automation_id=None, 
        configs=None,
        tags=None,
        *args, 
        **kwargs,
    ):
    create_scan_task(
        scan_id, 
        site_id,
        type,
        automation_id, 
        configs,
        tags,
    )
    logger.info('Created new scan of site')




@shared_task(base=ScannerApiTask)
def run_html_and_logs_bg(scan=None):
    run_html_and_logs_task(scan)
    logger.info('ran html & logs component')


@shared_task(base=ScannerApiTask)
def run_vrt_bg(scan=None):
    run_vrt_task(scan)
    logger.info('ran vrt component')


@shared_task(base=ScannerApiTask)
def run_lighthouse_bg(scan=None):
    run_lighthouse_task(scan)
    logger.info('ran lighthouse component')


@shared_task(base=ScannerApiTask)
def run_yellowlab_bg(scan=None):
    run_yellowlab_task(scan)
    logger.info('ran yellowlab component')




@shared_task(base=ScannerApiTask)
def create_test_bg(
        test_id=None,
        site_id=None, 
        automation_id=None, 
        configs=None, 
        type=['full'],
        index=None,
        pre_scan=None,
        post_scan=None,
        tags=None,
        *args, 
        **kwargs,
    ):
    create_test_task(
        test_id,
        site_id, 
        automation_id, 
        configs, 
        type,
        index,
        pre_scan,
        post_scan,
        tags
    )
    logger.info('Created new test of site')

@shared_task(base=ScannerApiTask)
def create_report_bg(site_id=None, automation_id=None):
    create_report_task(site_id, automation_id)
    logger.info('Created new report of site')


@shared_task(base=ScannerApiTask)
def delete_site_s3_bg(site_id):
    delete_site_s3(site_id)
    logger.info('Deleted site s3 objects')


@shared_task(base=ScannerApiTask)
def delete_report_s3_bg(report_id):
    delete_report_s3(report_id)
    logger.info('Deleted Report pdf in s3')


@shared_task(base=ScannerApiTask)
def purge_logs(username=None):
    if username:
        user = User.objects.get(username=username)
        Log.objects.filter(user=user).delete()
    else:
        Log.objects.all().delete()

    logger.info('Purged logs')


@shared_task
def create_testcase_bg(
        testcase_id=None, 
        site_id=None, 
        case_id=None, 
        updates=None, 
        automation_id=None,
        configs=None, 
        type=None,
        *args, 
        **kwargs,
    ):
    create_testcase_task(testcase_id, site_id, case_id, updates, configs, automation_id)
    logger.info('Ran full testcase')




@shared_task(base=ScannerApiTask)
def migrate_site_bg(
        login_url, 
        admin_url,
        username,
        password,
        email_address,
        destination_url,
        sftp_address,
        dbname,
        sftp_username,
        sftp_password, 
        plugin_name,
        wait_time,
        process_id,
        driver,
    ):
    migrate_site_task(
        login_url, 
        admin_url,
        username,
        password,
        email_address,
        destination_url,
        sftp_address,
        dbname,
        sftp_username,
        sftp_password, 
        plugin_name,
        wait_time, 
        process_id,
        driver,
    )

    logger.info('Finished Migration')