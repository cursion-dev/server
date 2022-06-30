from __future__ import absolute_import, unicode_literals
from celery.utils.log import get_task_logger
from celery import shared_task
from .v1.ops.tasks import (create_site_task, 
    create_scan_task, create_test_task, delete_site_s3,
    create_report_task, delete_report_s3, migrate_site_task,
    create_testcase_task,
)
from .models import Log
from django.contrib.auth.models import User
from .utils.driver_p import driver_test
from asgiref.sync import async_to_sync
import asyncio


logger = get_task_logger(__name__)



@shared_task
def test_pupeteer():
    asyncio.run(driver_test())
    logger.info('Tested pupeteer instalation')


@shared_task
def create_site_bg(site_id, scan_id, configs=None):
    create_site_task(site_id, scan_id, configs)
    logger.info('Created scan of new site')



@shared_task
def create_scan_bg(
        scan_id=None,
        site_id=None, 
        type=['full'],
        automation_id=None, 
        configs=None,
        tags=None,
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



@shared_task
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

@shared_task
def create_report_bg(site_id=None, automation_id=None):
    create_report_task(site_id, automation_id)
    logger.info('Created new report of site')


@shared_task
def delete_site_s3_bg(site_id):
    delete_site_s3(site_id)
    logger.info('Deleted site s3 objects')


@shared_task
def delete_report_s3_bg(report_id):
    delete_report_s3(report_id)
    logger.info('Deleted Report pdf in s3')


@shared_task
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
    ):
    create_testcase_task(testcase_id, site_id, case_id, updates, configs, automation_id)
    logger.info('Ran full testcase')




@shared_task
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