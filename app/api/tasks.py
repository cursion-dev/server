from __future__ import absolute_import, unicode_literals
from typing import Any
from celery.utils.log import get_task_logger
from celery import shared_task, Task
from .utils.crawler import Crawler
from .utils.scanner import Scanner as S
from .utils.tester import Tester as T
from .v1.ops.tasks import (
    create_site_task, create_scan_task, 
    create_test_task, create_report_task, delete_report_s3,
    delete_site_s3, create_testcase_task, migrate_site_task,
    delete_testcase_s3,
)
from .utils.scanner import (
    _html_and_logs, _vrt, _lighthouse, 
    _yellowlab
)
from .models import *
from django.contrib.auth.models import User
from django.utils import timezone
from .utils.driver_p import driver_test
from .v1.auth.alerts import send_invite_link, send_remove_alert
from asgiref.sync import async_to_sync
import asyncio, boto3, time, requests, json
from datetime import datetime, timedelta, date
from scanerr import settings


logger = get_task_logger(__name__)


class BaseTaskWithRetry(Task):
    autoretry_for = (Exception, KeyError)
    retry_kwargs = {'max_retries': 2}
    retry_backoff = True





@shared_task
def test_pupeteer():
    asyncio.run(driver_test())
    logger.info('Tested pupeteer instalation')


@shared_task(bind=True, base=BaseTaskWithRetry)
def create_site_and_pages_bg(self, site_id=None, configs=None, *args, **kwargs):
    site = Site.objects.get(id=site_id)
    site.time_crawl_started = timezone.now()
    site.time_crawl_completed = None
    site.save()
    # crawl site 
    pages = Crawler(url=site.site_url, max_urls=site.account.max_pages).get_links()
    for url in pages:
        # add new page
        if not Page.objects.filter(site=site, page_url=url).exists():
            page = Page.objects.create(
                site=site,
                page_url=url,
                user=site.user,
                account=site.account,
            )
            # create initial scan
            scan = Scan.objects.create(
                site=site,
                page=page, 
                type=['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'],
                configs=configs
            )
            # run each scan component in parallel
            run_html_and_logs_bg.delay(scan_id=scan.id)
            run_lighthouse_bg.delay(scan_id=scan.id)
            run_yellowlab_bg.delay(scan_id=scan.id)
            run_vrt_bg.delay(scan_id=scan.id)
            page.info["latest_scan"]["id"] = str(scan.id)
            page.info["latest_scan"]["time_created"] = str(scan.time_created)
            page.save()
    # updating site status
    site.time_crawl_completed = timezone.now()
    site.save()

    logger.info('Added site and all pages')




@shared_task(bind=True, base=BaseTaskWithRetry)
def crawl_site_bg(self, site_id=None, configs=None, *args, **kwargs):
    site = Site.objects.get(id=site_id)
    site.time_crawl_started = timezone.now()
    site.time_crawl_completed = None
    site.save()
    old_pages = Page.objects.filter(site=site)
    old_urls = []
    for p in old_pages:
        old_urls.append(p.page_url)

    # crawl site 
    new_pages = Crawler(url=site.site_url, max_urls=site.account.max_pages).get_links()
    add_pages = []

    # checking if allowed to add new page
    for page in new_pages:
        if not page in old_urls and (len(add_pages) + len(old_urls) <= site.account.max_pages):
            add_pages.append(page)
        
    for url in add_pages:
        # add new page
        if not Page.objects.filter(site=site, page_url=url).exists():
            page = Page.objects.create(
                site=site,
                page_url=url,
                user=site.user,
                account=site.account,
            )
            # create initial scan
            scan = Scan.objects.create(
                site=site,
                page=page, 
                type=['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'],
                configs=configs
            )
            # run each scan component in parallel
            run_html_and_logs_bg.delay(scan_id=scan.id)
            run_lighthouse_bg.delay(scan_id=scan.id)
            run_yellowlab_bg.delay(scan_id=scan.id)
            run_vrt_bg.delay(scan_id=scan.id)
            page.info["latest_scan"]["id"] = str(scan.id)
            page.info["latest_scan"]["time_created"] = str(scan.time_created)
            page.save()
    # updating site status
    site.time_crawl_completed = timezone.now()
    site.save()

    logger.info('crawled site and added pages')




@shared_task(bind=True, base=BaseTaskWithRetry)
def scan_page_bg(self, scan_id=None, test_id=None, automation_id=None, configs=None, *args, **kwargs):
    scan = Scan.objects.get(id=scan_id)
    
    # run each scan component in parallel
    if 'html' in scan.type or 'logs' in scan.type or 'full' in scan.type:
        run_html_and_logs_bg.delay(scan_id=scan.id, test_id=test_id, automation_id=automation_id)
    if 'lighthouse' in scan.type or 'full' in scan.type:
        run_lighthouse_bg.delay(scan_id=scan.id, test_id=test_id, automation_id=automation_id)
    if 'yellowlab' in scan.type or 'full' in scan.type:
        run_yellowlab_bg.delay(scan_id=scan.id, test_id=test_id, automation_id=automation_id)
    if 'vrt' in scan.type or 'full' in scan.type:
        run_vrt_bg.delay(scan_id=scan.id, test_id=test_id, automation_id=automation_id)

    logger.info('created new Scan of Page')



@shared_task(bind=True, base=BaseTaskWithRetry)
def _create_scan(
        self,
        scan_id=None,
        page_id=None, 
        type=['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'],
        automation_id=None, 
        configs=None,
        tags=None,
        *args, 
        **kwargs,
    ):
    create_scan_task(
        scan_id, 
        page_id,
        type,
        automation_id, 
        configs,
        tags,
    )
    logger.info('Created new scan of site')



@shared_task(bind=True, base=BaseTaskWithRetry)
def create_scan_bg(self, *args, **kwargs):
    # get data
    site_id = kwargs.get('site_id')
    page_id = kwargs.get('page_id')
    type = kwargs.get('type')
    configs = kwargs.get('configs')
    tags = kwargs.get('tags')
    automation_id = kwargs.get('automation_id')

    if site_id is not None:
        site = Site.objects.get(id=site_id)
        pages = Page.objects.filter(site=site)
    if page_id is not None:
        pages = [Page.objects.get(id=page_id)]

    for page in pages:
        _create_scan.delay(
            page_id=page.id,
            type=type,
            configs=configs,
            tags=tags,
            automation_id=automation_id
        )
    



@shared_task(bind=True, base=BaseTaskWithRetry)
def run_html_and_logs_bg(self, scan_id=None, test_id=None, automation_id=None, *args, **kwargs):
    _html_and_logs(scan_id, test_id, automation_id)
    logger.info('ran html & logs component')

@shared_task(bind=True, base=BaseTaskWithRetry)
def run_vrt_bg(self, scan_id=None, test_id=None, automation_id=None, *args, **kwargs):
    _vrt(scan_id, test_id, automation_id)
    logger.info('ran vrt component')

@shared_task(bind=True, base=BaseTaskWithRetry)
def run_lighthouse_bg(self, scan_id=None, test_id=None, automation_id=None, *args, **kwargs):
    _lighthouse(scan_id, test_id, automation_id)
    logger.info('ran lighthouse component')

@shared_task(bind=True, base=BaseTaskWithRetry)
def run_yellowlab_bg(self, scan_id=None, test_id=None, automation_id=None, *args, **kwargs):
    _yellowlab(scan_id, test_id, automation_id)
    logger.info('ran yellowlab component')




@shared_task(bind=True, base=BaseTaskWithRetry)
def run_test(self, test_id, *args, **kwargs):
    automation_id = kwargs.get('automation_id')
    test = Test.objects.get(id=test_id)
    test = T(test=test).run_test()
    if automation_id:
        automation(automation_id, test.id)
    logger.info('Test completed')


@shared_task(bind=True, base=BaseTaskWithRetry)
def check_scan_for_test(self, test_id=None, max_wait_time=500, *args, **kwargs):
    automation_id = kwargs.get('automation_id')
    test = Test.objects.get(id=test_id)
    post_scan_id = test.post_scan.id

    current_time = 0
    while current_time < max_wait_time:
        post_scan = Scan.objects.get(id=post_scan_id)
        time.sleep(5)
        if post_scan.time_completed is not None:
           run_test.delay(test_id=test.id, automation_id=automation_id)
           current_time += 500

        current_time += 5

    logger.info('Scan complete, begining Test')


@shared_task(bind=True, base=BaseTaskWithRetry)
def _create_test(
        self,
        test_id=None,
        page_id=None, 
        automation_id=None, 
        configs=None, 
        type=['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'],
        index=None,
        pre_scan=None,
        post_scan=None,
        tags=None,
        *args, 
        **kwargs,
    ):
    if test_id is not None:
        created_test = Test.objects.get(id=test_id)
        page = created_test.page
    elif page_id is not None:
        page = Page.objects.get(id=page_id)
        created_test = Test.objects.create(
            site=page.site,
            page=page,
            type=type,
            tags=tags,
        )

    if pre_scan is not None:
        pre_scan = Scan.objects.get(id=pre_scan)
    if post_scan is not None:
        post_scan = Scan.objects.get(id=post_scan)

    if post_scan is None or pre_scan is None:
        if pre_scan is None:
            pre_scan = Scan.objects.filter(page=page).order_by('-time_completed')[0]
        post_scan = Scan.objects.create(
            site=page.site,
            page=page,
            tags=tags, 
            type=type,
            configs=configs,
        )
        scan_page_bg.delay(
            scan_id=post_scan.id, 
            test_id=created_test.id,
            automation_id=automation_id,
            configs=configs,
        )
        
    # updating parired scans
    pre_scan.paired_scan = post_scan
    post_scan.paried_scan = pre_scan
    pre_scan.save()
    post_scan.save()

    # updating test object
    created_test.type = type
    created_test.pre_scan = pre_scan
    created_test.post_scan = post_scan
    created_test.save()
    
    # monitor post_scan and run test after completion
    # check_scan_for_test.delay(test_id=created_test.id, automation_id=automation_id)

    # check if pre and post scan are complete and start test if True
    if pre_scan.time_completed is not None and post_scan.time_completed is not None:
        run_test.delay(test_id=created_test.id, automation_id=automation_id)
    
    logger.info('Began Scan/Test process')




@shared_task(bind=True, base=BaseTaskWithRetry)
def create_test_bg(self, *args, **kwargs):
    # get data
    site_id = kwargs.get('site_id')
    page_id = kwargs.get('page_id')
    test_id = kwargs.get('test_id')
    type = kwargs.get('type')
    configs = kwargs.get('configs')
    tags = kwargs.get('tags')
    automation_id = kwargs.get('automation_id')
    pre_scan = kwargs.get('pre_scan')
    post_scan = kwargs.get('post_scan')

    if test_id is None:
        if site_id is not None:
            site = Site.objects.get(id=site_id)
            pages = Page.objects.filter(site=site)
        if page_id is not None:
            p = Page.objects.get(id=page_id)
            pages = [p]

        for page in pages:
            _create_test.delay(
                page_id=page.id,
                type=type,
                configs=configs,
                tags=tags,
                pre_scan=pre_scan,
                post_scan=post_scan,
                automation_id=automation_id
            )
    
    if test_id is not None:
        test = Test.objects.get(id=test_id)
        _create_test.delay(
            test_id=test_id,
            page_id=test.page.id,
            type=type,
            configs=configs,
            tags=tags,
            pre_scan=pre_scan,
            post_scan=post_scan,
            automation_id=automation_id
        )



@shared_task
def _create_report(page_id=None, automation_id=None, *args, **kwargs):
    create_report_task(page_id, automation_id)
    logger.info('Created new report of page')


@shared_task
def create_report_bg(*args, **kwargs):
    # get data
    site_id = kwargs.get('site_id')
    page_id = kwargs.get('page_id')
    automation_id = kwargs.get('automation_id')

    if site_id is not None:
        site = Site.objects.get(id=site_id)
        pages = Page.objects.filter(site=site)
    if page_id is not None:
        pages = [Page.objects.get(id=page_id)]

    for page in pages:
        _create_report.delay(
            page_id=page.id,
            automation_id=automation_id
        )


@shared_task
def delete_site_s3_bg(site_id, *args, **kwargs):
    delete_site_s3(site_id)
    logger.info('Deleted site s3 objects')


@shared_task
def delete_page_s3_bg(page_id, site_id, *args, **kwargs):
    # setup boto3 configurations
    s3 = boto3.resource('s3', 
        aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
        aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
        region_name=str(settings.AWS_S3_REGION_NAME),
        endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
    )
    # deleting s3 objects
    try:
        bucket = s3.Bucket(settings.AWS_STORAGE_BUCKET_NAME)
        bucket.objects.filter(Prefix=str(f'static/sites/{site_id}/{page_id}/')).delete()
    except Exception as e:
        print(e)
    return

@shared_task
def delete_scan_s3_bg(scan_id, site_id, page_id):
    # setup boto3 configurations
    s3 = boto3.resource('s3', 
        aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
        aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
        region_name=str(settings.AWS_S3_REGION_NAME), 
        endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
    )
    # deleting s3 objects
    try:
        bucket = s3.Bucket(settings.AWS_STORAGE_BUCKET_NAME)
        bucket.objects.filter(Prefix=str(f'static/sites/{site_id}/{page_id}/{scan_id}/')).delete()
    except Exception as e:
        print(e)
    return
    

@shared_task
def delete_test_s3_bg(test_id, site_id, page_id):
    # setup boto3 configurations
    s3 = boto3.resource('s3', 
        aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
        aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
        region_name=str(settings.AWS_S3_REGION_NAME), 
        endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
    )
    # deleting s3 objects
    try:
        bucket = s3.Bucket(settings.AWS_STORAGE_BUCKET_NAME)
        bucket.objects.filter(Prefix=str(f'static/sites/{site_id}/{page_id}/{test_id}/')).delete()
    except Exception as e:
        print(e)
    return



@shared_task
def delete_testcase_s3_bg(testcase_id, *args, **kwargs):
    delete_testcase_s3(testcase_id)
    logger.info('Deleted testcase s3 objects')


@shared_task
def delete_report_s3_bg(report_id, *args, **kwargs):
    delete_report_s3(report_id)
    logger.info('Deleted Report pdf in s3')


@shared_task
def purge_logs(username=None, *args, **kwargs):
    if username:
        user = User.objects.get(username=username)
        Log.objects.filter(user=user).delete()
    else:
        Log.objects.all().delete()

    logger.info('Purged logs')


@shared_task(bind=True, base=BaseTaskWithRetry)
def create_testcase_bg(
        self, 
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




@shared_task
def delete_old_resources(account_id=None, days_to_live=30):
    max_date = datetime.now() - timedelta(days=days_to_live)

    if account_id is not None:
        tests = Test.objects.filter(site__account__id=account_id, time_created__lte=max_date)
        scans = Scan.objects.filter(site__account__id=account_id, time_created__lte=max_date)
        testcases = Testcase.objects.filter(account__id=account_id, time_created__lte=max_date)
    else:
        tests = Test.objects.filter(time_created__lte=max_date)
        scans = Scan.objects.filter(time_created__lte=max_date)
        testcases = Testcase.objects.filter(time_created__lte=max_date)

    for test in tests:
        delete_test_s3_bg.delay(test.id, test.site.id, test.page.id)
        test.delete()
    for scan in scans:
        delete_scan_s3_bg.delay(scan.id, scan.site.id, scan.page.id)
        scan.delete()
    for testcase in testcases:
        delete_testcase_s3_bg.delay(testcase.id)
        testcase.delete()
    
    logger.info('Cleaned up resources')





@shared_task
def data_retention():
    accounts = Account.objects.all()
    for account in accounts:
        delete_old_resources.delay(
            account_id=account.id,
            days_to_live=account.retention_days
        )
    
    logger.info('Requested resource cleanup')





@shared_task
def delete_admin_sites(days_to_live=1):
    max_date = datetime.now() - timedelta(days=days_to_live)
    sites = Site.objects.filter(time_created__lte=max_date, user__username='admin')

    for site in sites:
        delete_site_s3_bg.delay(site.id)
        site.delete()
    
    logger.info('Cleaned up admin sites')




@shared_task
def create_prospect(user_id=None):

    # get user by id
    user = User.objects.get(id=id)
    
    # setup configs
    url = f'{settings.LANDING_API_ROOT}/v1/ops/prospect'
    headers = {
        "content-type": "application/json",
        "Authorization" : f'Token {settings.LANDING_API_KEY}'
    }
    data = {
        'first_name': str(user.first_name),
        'last_name': str(user.last_name),
        'email': str(user.email),
        'status': 'warm',
        'source': 'app',
    }
    
    try:
        # send the request
        res = requests.post(
            url=url, 
            headers=headers, 
            data=json.dumps(data)
        ).json()

        success = True
        message = res

    except Exception as e:
        success = False
        message = res

    data = {
        'success': success,
        'message': message
    }
    
    logger.info(f'Sent Prospect creation request -> {data}')




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
        *args, 
        **kwargs
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



@shared_task
def send_invite_link_bg(member_id):
    member = Member.objects.get(id=member_id)
    send_invite_link(member)
    logger.info('Sent invite')

@shared_task
def send_remove_alert_bg(member_id):
    member = Member.objects.get(id=member_id)
    send_remove_alert(member)
    logger.info('Sent remove alert')