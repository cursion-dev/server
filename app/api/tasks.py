from celery.utils.log import get_task_logger
from celery import shared_task, Task
from cursion import celery
from .utils.crawler import Crawler
from .utils.scanner import Scanner as S
from .utils.tester import Tester as T
from .utils.reporter import Reporter as R
from .utils.wordpress import Wordpress as W
from .utils.alerter import Alerter
from .utils.caser import Caser
from .utils.autocaser import AutoCaser
from .utils.issuer import Issuer
from .utils.exporter import create_and_send_report_export
from .utils.scanner import (
    _html_and_logs, _vrt, _lighthouse, 
    _yellowlab
)
from .utils.alerts import *
from .utils.updater import update_flowrun
from .utils.meter import meter_account
from .utils.manager import record_task
from .models import *
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta, timezone
from redis import Redis
from contextlib import contextmanager
from cursion import settings
import asyncio, boto3, time, requests, \
json, stripe, inspect, random, secrets






class BaseTaskWithRetry(Task):
    autoretry_for = (Exception, KeyError)
    retry_kwargs = {'max_retries': int(settings.MAX_ATTEMPTS - 1)}
    retry_backoff = True




# setting logger 
logger = get_task_logger(__name__)




# setting redis client
redis_client = Redis.from_url(settings.CELERY_BROKER_URL)




# setting locking manager to prevent duplicate tasks
@contextmanager
def task_lock(lock_name, timeout=600):
    lock = redis_client.lock(lock_name, timeout=timeout)
    acquired = lock.acquire(blocking=False)
    print(f"Lock {'acquired' if acquired else 'not acquired'} for {lock_name}")
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()
            print(f"Lock released for {lock_name}")




# setting s3 instance
def s3():
    s3 = boto3.resource('s3', 
        aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
        aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
        region_name=str(settings.AWS_S3_REGION_NAME), 
        endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
    )
    return s3




def check_and_increment_resource(account_id: str, resource: str) -> bool:
    """ 
    Adds 1 to the Account.usage.{resource} if 
    {resource}_allowed has not been reached or 
    if account.type is 'cloud'.

    Expects: {
        'account_id'  : <str>,
        'resource'    : <str> 'scan', 'test', 'caserun', etc
    }

    Returns: Bool, True if resource was incremented.
    """

    # get account
    account = Account.objects.get(id=account_id)

    # define defaults
    success = False
    charge_list = ['caseruns', 'flowruns', 'scans', 'tests']

    # handle non-paid, cloud accounts
    if account.type != 'cloud':

        # check allowance
        if (int(account.usage[f'{resource}']) + 1) <= int(account.usage[f'{resource}_allowed']):
            
            # increment and update success
            account.usage[f'{resource}'] = 1 + int(account.usage[f'{resource}'])
            account.save()
            success = True
    
    # handle paid, cloud accounts
    if account.type == 'cloud':

        # increment chargable resources
        if resource in charge_list:

            # check chargablility
            if (int(account.usage[f'{resource}'])) >= int(account.usage[f'{resource}_allowed']):

                # meter resource
                meter_account(account.id, 1)
            
            # increment and update success
            account.usage[f'{resource}'] = 1 + int(account.usage[f'{resource}'])
            account.save()
            success = True

        
        # increment non-chargable resources
        if resource not in charge_list:
            
            # check allowance
            if (int(account.usage[f'{resource}']) + 1) <= int(account.usage[f'{resource}_allowed']):
                
                # increment and update success
                account.usage[f'{resource}'] = 1 + int(account.usage[f'{resource}'])
                account.save()
                success = True

    # return response
    return success




def check_location(location: str) -> bool:
    """ 
    Determines if task should be executed based on 
    passed location and current system location (settings.LOCATION). 

    Expects: {
        'location': str
    }

    Returns: bool (True if task should run)
    """

    # compare location to system
    if location == settings.LOCATION:
        return True
    if location != settings.LOCATION:
        return False




def update_schedule(task_id: str=None) -> None:
    """
    Helper function to update Schedule.time_last_run

    Expects: {
        task_id: str
    }

    Returns: None
    """
    if task_id:
        try:
            last_run = datetime.now(timezone.utc)
            Schedule.objects.filter(periodic_task_id=task_id).update(
                time_last_run=last_run
            )
        except Exception as e:
            print(e)
    return None




@shared_task()
def redeliver_failed_tasks() -> None:
    """ 
    Check each un-completed resource (Scans & Tests) 
    for any celery tasks which are no longer executing & 
    associated resource.component is null. Once found, 
    re-run those specific tasks with saved kwargs. If 
    resource appears complete but is not marked as such, 
    update `.time_completed` with `datetime.now()`

    Expects: None
    
    Returns: None
    """

    # get uncompleted Scans & Tests
    scans = Scan.objects.filter(time_completed=None)
    tests = Test.objects.filter(time_completed=None)

    # get executing_tasks
    i = celery.app.control.inspect()
    reserved = i.reserved()
    active = i.active()
    executing_tasks = []
    for replica in reserved:
        for task in reserved[replica]:
            executing_tasks.append(task['id'])
    for replica in active:
        for task in active[replica]:
            executing_tasks.append(task['id'])

    # iterate through each scan and re-run any failed jobs
    for scan in scans:

        # check for localization
        if scan.configs.get('location', 'us') != settings.LOCATION:
            continue

        # check each task in system['tasks']
        task_count  = 0
        test_id     = None
        alert_id    = None
        flowrun_id  = None
        node_index  = None
        components  = []
        for task in scan.system.get('tasks', []):

            # get scan.{component} data
            if task['component'] == 'yellowlab':
                component = scan.yellowlab.get('audits', None)
            if task['component'] == 'lighthouse':
                component = scan.lighthouse.get('audits', None)
            if task['component'] == 'vrt':
                component = scan.images
            if task['component'] == 'html':
                component = scan.html
            
            # record components
            components.append(task['component'])

            # try to get args
            test_id     = task['kwargs'].get('test_id')
            alert_id    = task['kwargs'].get('alert_id')
            flowrun_id  = task['kwargs'].get('flowrun_id')
            node_index  = task['kwargs'].get('node_index')
            
            # re-run task if not in executing_tasks &
            # scan.{component} is None
            if task['task_id'] not in executing_tasks and component is None:
                
                # check for max attempts
                if task['attempts'] < settings.MAX_ATTEMPTS:
                    print(f're-running -> {task["task_method"]}.delay(**{task["kwargs"]})')
                    eval(f'{task["task_method"]}.delay(**{task["kwargs"]})')
                    task_count += 1

        # try to get test_id
        if not test_id and Test.objects.filter(post_scan=scan, time_completed=None).exists():
            test_id = Test.objects.filter(post_scan=scan, time_completed=None)[0].id

        # check for requested, and not recorded, components:
        for comp in scan.type:
            if comp not in components and comp != 'logs':
                # building args
                task = f"run_{comp.replace('html', 'html_and_logs')}_bg"
                kwargs = {
                    "scan_id": str(scan.id),
                    "test_id": str(test_id),
                    "alert_id": alert_id,
                    "flowrun_id": flowrun_id,
                    "node_index": node_index
                }
                # run task
                print(f'running -> {task}.delay(**{kwargs})')
                eval(f'{task}.delay(**{kwargs})')
                task_count += 1
        
        # mark scan complete if no tasks were re-run
        if task_count == 0 and len(scan.system.get('tasks', [])) > 0:
            print(f'marking scan as complete')
            scan.time_completed = datetime.now()
            scan.save()

            # execute `run_test()` if test_id present
            if test_id:
                print(f'executing run_test() from `post_scan` in `retry_tasks`')
                run_test.delay(
                    test_id=str(test_id),
                    alert_id=alert_id,
                    flowrun_id=flowrun_id,
                    node_index=node_index
                )  
        
    # iterate through each test and re-run if failed
    for test in tests:

        # check for localization
        if settings.LOCATION != 'us':
            continue

        # check each task in system['tasks']
        task_count = 0
        for task in test.system.get('tasks', []):
            
            # re-run task if not in executing_tasks
            if task['task_id'] not in executing_tasks:

                # check for post_scan completion
                if not test.post_scan.time_completed:
                    print('post_scan not complete skipping test re-run...')
                    continue
                
                # check for max attempts
                if task['attempts'] < settings.MAX_ATTEMPTS:
                    print(f're-running -> {task["task_method"]}.delay(**{task["kwargs"]})')
                    eval(f'{task["task_method"]}.delay(**{task["kwargs"]})')
                    task_count += 1
        
        # mark test complete if no tasks were re-run
        if task_count == 0 and len(test.system.get('tasks', [])) > 0:
            test.time_completed = datetime.now()
            test.save()

    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def create_site_and_pages_bg(self, site_id: str=None, configs: dict=settings.CONFIGS) -> None:
    """ 
    Takes a newly created `Site`, initiates a Crawl and 
    initial `Scan` for each crawled page

    Expects: {
        site_id: str, 
        configs: dict
    }
    
    Returns -> None
    """

    # getting site and updating for time_crawl_start
    site = Site.objects.get(id=site_id)
    site.time_crawl_started = datetime.now(timezone.utc)
    site.time_crawl_completed = None
    site.save()

    # get max_urls
    max_urls = site.account.usage['pages_allowed']

    # crawl site 
    pages = Crawler(url=site.site_url, max_urls=max_urls).get_links()
    
    # create pages and scans
    for url in pages:

        # add new page
        if not Page.objects.filter(site=site, page_url=url).exists():
            page = Page.objects.create(
                site=site,
                page_url=url,
                user=site.user,
                account=site.account,
            )

            # check resouce allowance
            if check_and_increment_resource(site.account.id, 'scans'):

                # create initial scan
                scan = Scan.objects.create(
                    site=site,
                    page=page, 
                    type=settings.TYPES,
                    configs=configs
                )
                
                # run each scan component in parallel
                run_html_and_logs_bg.delay(scan_id=scan.id)
                run_lighthouse_bg.delay(scan_id=scan.id)
                run_yellowlab_bg.delay(scan_id=scan.id)
                run_vrt_bg.delay(scan_id=scan.id)
                
                # update page info 
                page.info["latest_scan"]["id"] = str(scan.id)
                page.info["latest_scan"]["time_created"] = str(scan.time_created)
                page.save()

    # updating site status
    site.time_crawl_completed = datetime.now(timezone.utc)
    site.save()

    logger.info('Added site and all pages')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def crawl_site_bg(self, site_id: str=None, configs: dict=settings.CONFIGS) -> None:
    """ 
    Takes an existing `Site`, initiates a new Crawl and 
    initial `Scan` for each newly added page

    Expects: {
        site_id: str, 
        configs: dict
    }
    
    Returns -> None
    """
    
    # getting site and updating for time_crawl_start
    site = Site.objects.get(id=site_id)
    site.time_crawl_started = datetime.now(timezone.utc)
    site.time_crawl_completed = None
    site.save()

    # get pages_allowed
    pages_allowed = site.account.usage['pages_allowed']
    
    # getting old pages for comparison
    old_pages = Page.objects.filter(site=site)
    old_urls = []
    for p in old_pages:
        old_urls.append(p.page_url)

    # crawl site 
    new_urls = Crawler(url=site.site_url, max_urls=pages_allowed).get_links()
    add_urls = []

    # checking for duplicates
    for url in new_urls:
        if not url in old_urls:
            add_urls.append(url)

    # loop thorugh crawled pages 
    # and add if not present  
    current_count = len(old_urls)
    for url in add_urls:

        # add new page if room exists
        if current_count < pages_allowed:
            page = Page.objects.create(
                site=site,
                page_url=url,
                user=site.user,
                account=site.account,
            )

            # check resouce allowance
            if check_and_increment_resource(site.account.id, 'scans'):

                # create initial scan
                scan = Scan.objects.create(
                    site=site,
                    page=page, 
                    type=settings.TYPES,
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

            # increment
            current_count += 1

    # updating site status
    site.time_crawl_completed = datetime.now(timezone.utc)
    site.save()

    logger.info('crawled site and added pages')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def update_site_and_page_info(
        self,
        resource: str='all',
        site_id: str=None, 
        page_id: str=None,
    ) -> None:
    """ 
    Updates the site and or page `latest_scan` & `latest_test` info 
    depending on scope.

    Expects: {
        "resource" : str (OPTIONAL),
        "site_id"  : str (OPTIONAL),
        "page_id"  : str (OPTIONAL)
    }

    Returns -> None
    """

    # defaults
    site = None
    page = None
    pages = []
    scans = []
    tests = []

    # get associated site
    if site_id:
        site = Site.objects.get(id=site_id)
        pages = Page.objects.filter(site=site)
    
    # get associated page
    if page_id:
        page = Page.objects.get(id=page_id)
        site = page.site
        pages = Page.objects.filter(site=site)
    
    # get latest tests & scans of pages
    for p in pages:

        # set defaults
        latest_scan = None
        latest_test = None

        if Test.objects.filter(page=p).exists() and \
            (resource == 'test' or resource == 'all'):
            _test = Test.objects.filter(page=p).exclude(
                time_completed=None
            ).order_by('-time_completed')
            if len(_test) > 0:
                if _test[0].score:
                    # add to tests[]
                    tests.append(_test[0].score)
                    # update latest_test
                    latest_test = _test[0]
        
        if Scan.objects.filter(page=p).exists() and \
            (resource == 'scan' or resource == 'all'):
            _scan = Scan.objects.filter(page=p).exclude(
                time_completed=None
            ).order_by('-time_completed')
            if len(_scan) > 0:
                if _scan[0].score:
                    # add to scans[]
                    scans.append(_scan[0].score)
                    # update latest_scan
                    latest_scan = _scan[0]
        
        # update single page if passed
        if page:

            # checking if current p is page
            if page.id == p.id:

                # latest_scan info
                if latest_scan:
                    page.info['latest_scan']['id'] = str(latest_scan.id)
                    page.info['latest_scan']['time_created'] = str(latest_scan.time_created)
                    page.info['latest_scan']['time_completed'] = str(latest_scan.time_completed)
                    page.info['latest_scan']['score'] = latest_scan.score
                    page.info['lighthouse'] = latest_scan.lighthouse.get('scores')
                    page.info['yellowlab'] = latest_scan.yellowlab.get('scores')
                    print(f'updating {page.page_url} with scan.score -> {latest_scan.score}')
                if latest_scan is None and (resource == 'scan' or resource == 'all'):
                    page.info['latest_scan']['id'] = None
                    page.info['latest_scan']['time_created'] = None
                    page.info['latest_scan']['time_completed'] = None
                    page.info['latest_scan']['score'] = None
                    page.info['lighthouse'] = None
                    page.info['yellowlab'] = None
                    print(f'updating {page.page_url} with scan.score -> {None}')

                # latest_test info
                if latest_test:
                    page.info['latest_test']['id'] = str(latest_test.id)
                    page.info['latest_test']['time_created'] = str(latest_test.time_created)
                    page.info['latest_test']['time_completed'] = str(latest_test.time_completed)
                    page.info['latest_test']['score'] = (round(latest_test.score * 100) / 100)
                    page.info['latest_test']['status'] = latest_test.status
                    print(f'updating {p.page_url} with test.score -> {latest_test.score}')
                if latest_test is None and (resource == 'test' or resource == 'all'):
                    page.info['latest_test']['id'] = None
                    page.info['latest_test']['time_created'] = None
                    page.info['latest_test']['time_completed'] = None
                    page.info['latest_test']['score'] = None
                    page.info['latest_test']['status'] = None
                    print(f'updating {p.page_url} with test.score -> {None}')

                # save page
                page.save()
    
    # update site with new scan info
    if len(scans) > 0:
        # calc site average of latest_scan.score
        site_avg_scan_score = round((sum(scans)/len(scans)) * 100) / 100
        print(f'updating site with new scan score -> {site_avg_scan_score}')

    # latest_scan info
    if latest_scan:
        site.info['latest_scan']['id'] = str(latest_scan.id)
        site.info['latest_scan']['time_created'] = str(latest_scan.time_created)
        site.info['latest_scan']['time_completed'] = str(latest_scan.time_completed)
        site.info['latest_scan']['score'] = latest_scan.score
        site.info['lighthouse'] = latest_scan.lighthouse.get('scores')
        site.info['yellowlab'] = latest_scan.yellowlab.get('scores')
    if latest_scan is None and (resource == 'scan' or resource == 'all'):
        site.info['latest_scan']['id'] = None
        site.info['latest_scan']['time_created'] = None
        site.info['latest_scan']['time_completed'] = None
        site.info['latest_scan']['score'] = None
        site.info['lighthouse'] = None
        site.info['yellowlab'] = None

    # update site with new test info
    if len(tests) > 0:
        # calc site average of latest_test.score
        site_avg_test_score = round((sum(tests)/len(tests)) * 100) / 100
        print(f'updating site with new test score -> {site_avg_test_score}')
        
    # update site info
    if latest_test:
        site.info['latest_test']['id'] = str(latest_test.id)
        site.info['latest_test']['time_created'] = str(latest_test.time_created)
        site.info['latest_test']['time_completed'] = str(latest_test.time_completed)
        site.info['latest_test']['score'] = site_avg_test_score
        site.info['latest_test']['status'] = latest_test.status
    if latest_test is None and (resource == 'test' or resource == 'all'):
        site.info['latest_test']['id'] = None
        site.info['latest_test']['time_created'] = None
        site.info['latest_test']['time_completed'] = None
        site.info['latest_test']['score'] = None
        site.info['latest_test']['status'] = None

    # save info
    site.save()
    
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def update_scan_score(self, scan_id: str) -> None:
    """ 
    Method to calculate the average health score and update 
    for the passed scan_id

    Expects: {
        'scan_id': str
    }

    Returns -> None
    """
    
    # setting defaults
    score = None
    scores = []
    scan = Scan.objects.get(id=scan_id)

    # get latest scan scores
    if scan.lighthouse['scores']['average'] is not None:
        scans.append(scan.lighthouse['scores']['average'])
    if scan.yellowlab['scores']['globalScore'] is not None:
        scans.append(scan.yellowlab['scores']['globalScore'])
    
    # calc average score
    if len(scores) > 0:
        score = sum(scores)/len(scores)

    # save to scan
    scan.score = score
    scan.save()
        
    # returning scan
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def scan_page_bg(
        self, 
        scan_id     : str=None, 
        test_id     : str=None, 
        alert_id    : str=None, 
        flowrun_id  : str=None,
        node_index  : str=None,
    ) -> None:
    """ 
    Runs all the requested `Scan` components 
    of the passed `Scan`.

    Expects: {
        scan_id    : str, 
        test_id    : str, 
        alert_id   : str, 
        configs    : dict,
        flowrun_id : str,
        node_index : str
    }

    Returns -> None
    """
    
    # get scan object
    scan = Scan.objects.get(id=scan_id)
    
    # run each scan component in parallel
    if 'html' in scan.type or 'logs' in scan.type or 'full' in scan.type:
        run_html_and_logs_bg.delay(
            scan_id=scan.id, 
            test_id=test_id, 
            alert_id=alert_id,
            flowrun_id=flowrun_id,
            node_index=node_index,
        )
    if 'lighthouse' in scan.type or 'full' in scan.type:
        run_lighthouse_bg.delay(
            scan_id=scan.id, 
            test_id=test_id, 
            alert_id=alert_id,
            flowrun_id=flowrun_id,
            node_index=node_index,
        )
    if 'yellowlab' in scan.type or 'full' in scan.type:
        run_yellowlab_bg.delay(
            scan_id=scan.id, 
            test_id=test_id, 
            alert_id=alert_id,
            flowrun_id=flowrun_id,
            node_index=node_index,
        )
    if 'vrt' in scan.type or 'full' in scan.type:
        run_vrt_bg.delay(
            scan_id=scan.id, 
            test_id=test_id, 
            alert_id=alert_id,
            flowrun_id=flowrun_id,
            node_index=node_index,
        )

    logger.info('started scan component tasks')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def create_scan(
        self,
        scan_id: str=None,
        page_id: str=None, 
        type: list=settings.TYPES,
        alert_id: str=None, 
        configs: str=None,
        tags: str=None,
    ) -> None:
    """ 
    Runs a `Scan` using Scanner.build_scan() 
    where each component is run in sequence.

    Expects: {
        scan_id         : str,
        page_id         : str, 
        type            : list,
        alert_id        : str, 
        configs         : dict,
        tags            : list,
    }
    
    Returns -> None
    """

    # get scan if scan_id present
    if scan_id is not None:
        created_scan = Scan.objects.get(id=scan_id)
    
    # create scan if page_id present
    elif page_id is not None:
        page = Page.objects.get(id=page_id)
        created_scan = Scan.objects.create(
            site=page.site,
            page=page,
            type=type,
            configs=configs,
            tags=tags, 
        )

    # run scan and alert if necessary
    scan = S(scan=created_scan).build_scan()
    if alert_id and alert_id != 'None':
        print('running alert from `task.create_scan`')
        Alerter(alert_id=alert_id, object_id=scan.id).run_alert()
    
    logger.info('Created new scan of site')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def create_scan_bg(self, *args, **kwargs) -> None:
    """ 
    Creates 1 or more `Scans` depending on 
    the scope (page, site or account). Used with `Schedules`

    Expects: {
        'scope'         : str
        'resources'     : list
        'account_id'    : strx
        'type'          : list,
        'configs'       : dict,
        'tags'          : list,
        'alert_id'      : str,
        'task_id'       : str,
        'flowrun_id'    : str,
        'node_index     : str
    }

    Returns -> None
    """

    # get data from kwargs
    scope = kwargs.get('scope')
    resources = kwargs.get('resources')
    account_id = kwargs.get('account_id')
    type = kwargs.get('type')
    configs = kwargs.get('configs')
    tags = kwargs.get('tags')
    alert_id = kwargs.get('alert_id')
    task_id = kwargs.get('task_id')
    flowrun_id = kwargs.get('flowrun_id')
    node_index = kwargs.get('node_index')

    # check for redis lock
    redis_id = task_id if task_id else secrets.token_hex(8)
    lock_name = f"lock:create_scan_bg_{redis_id}"
    with task_lock(lock_name) as lock_acquired:
        
        # checking if task is already running
        if not lock_acquired:
            logger.info('task is already running, skipping execution.')
            return None

        # checking location
        if not check_location(configs.get('location', settings.LOCATION)):
            logger.info('Not running due to location param')
            return None

        # setting defaults
        pages = []
        sites = []
        objects = []

        # get account if account_id exists
        if account_id:
            account = Account.objects.get(id=account_id)
            
        # iterating through resources 
        # and adding to sites or pages
        if len(resources) > 0:
            for item in resources:
                
                # adding to pages
                if item['type'] == 'page':
                    try:
                        pages.append(
                            Page.objects.get(id=item['id'])
                        )
                    except Exception as e:
                        print(e)
                
                # adding to sites
                if item['type'] == 'site':
                    try:
                        sites.append(
                            Site.objects.get(id=item['id'])
                        ) 
                    except Exception as e:
                        print(e)
        
        # grabbing all sites because no 
        # resources were specified and scope is "account"
        if len(resources) == 0 and scope == 'account':
            sites = Site.objects.filter(account=account)

        # get all pages from existing sites
        for site in sites:
            pages += Page.objects.filter(site=site)

        # creating scans for each page
        for page in pages:
            
            # check resource 
            if check_and_increment_resource(page.account.id, 'scans'):

                # create Scan obj
                scan = Scan.objects.create(
                    site=page.site,
                    page=page,
                    type=type,
                    tags=tags,
                    configs=configs,
                )

                # updating latest_scan info for page
                page.info['latest_scan']['id'] = str(scan.id)
                page.info['latest_scan']['time_created'] = str(datetime.now(timezone.utc))
                page.info['latest_scan']['time_completed'] = None
                page.info['latest_scan']['score'] = None
                page.info['latest_scan']['score'] = None
                page.save()

                # updating latest_scan info for site
                page.site.info['latest_scan']['id'] = str(scan.id)
                page.site.info['latest_scan']['time_created'] = str(datetime.now(timezone.utc))
                page.site.info['latest_scan']['time_completed'] = None
                page.site.save()

                # adding objects
                objects.append({
                    'parent': str(scan.page.id),
                    'id': str(scan.id),
                    'status': 'working'
                })

                # init scan page in background
                scan_page_bg.delay(
                    scan_id=str(scan.id),
                    alert_id=alert_id,
                    flowrun_id=flowrun_id,
                    node_index=node_index
                )
            
        # update flowrun
        if flowrun_id and flowrun_id != 'None':
            update_flowrun(**{
                'flowrun_id': flowrun_id,
                'node_index': node_index,
                'objects': objects,
                'node_status': 'working' if len(objects) > 0 else 'failed',
                'message': f'starting {len(objects)} scans for {page.site.site_url} | run_id: {flowrun_id}'
            })
        
        # update schedule if task_id is not None
        update_schedule(task_id=task_id)
        
        logger.info('created new Scans')
        return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def run_html_and_logs_bg(
        self, 
        scan_id: str=None, 
        test_id: str=None, 
        alert_id: str=None, 
        flowrun_id: str=None,
        node_index: str=None,
        **kwargs
    ) -> None:
    """ 
    Runs the html & logs components of the passed `Scan`

    Expects: {
        scan_id     : str, 
        test_id     : str, 
        alert_id    : str,
        flowrun_id  : str,
        node_index  : str,
        **kwargs
    }
    
    Returns -> None
    """

    # sleeping random for DB 
    time.sleep(random.uniform(2, 6))

    # get kwargs data if no scan_id
    if scan_id is None:
        scan_id = kwargs.get('scan_id')
        test_id = kwargs.get('test_id')
        alert_id = kwargs.get('alert_id')
        flowrun_id = kwargs.get('flowrun_id')
        node_index = kwargs.get('node_index')
    
    # check redis task lock
    lock_name = f"lock:html_and_logs_bg_{scan_id}"
    with task_lock(lock_name) as lock_acquired:

        # checking if task is already running
        if not lock_acquired:
            logger.info('task is already running, skipping execution.')
            return None

        # save & check sys data
        max_reached = record_task(
            resource_type='scan',
            resource_id=str(scan_id),
            task_id=str(self.request.id),
            task_method=str(inspect.stack()[0][3]),
            kwargs={
                'scan_id': str(scan_id) if scan_id is not None else None,
                'test_id': str(test_id) if test_id is not None else None, 
                'alert_id': str(alert_id) if alert_id is not None else None,
                'flowrun_id': str(flowrun_id) if flowrun_id is not None else None,
                'node_index': str(node_index) if node_index is not None else None
            }
        )

        # return early if max_attempts reached
        if max_reached:
            print('max attempts reach for html & logs component')
            return None
        
        # run html and logs component
        _html_and_logs(scan_id, test_id, alert_id, flowrun_id, node_index)

    logger.info('ran html & logs component')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def run_vrt_bg(
        self, 
        scan_id: str=None, 
        test_id: str=None, 
        alert_id: str=None, 
        flowrun_id: str=None,
        node_index: str=None,
        **kwargs
    ) -> None:
    """ 
    Runs the VRT component of the passed `Scan`

    Expects: {
        scan_id     : str, 
        test_id     : str, 
        alert_id    : str,
        flowrun_id  : str,
        node_index  : str,
        **kwargs
    }
    
    Returns -> None
    """

    # sleeping random for DB 
    time.sleep(random.uniform(2, 6))

    # get kwargs data if no scan_id
    if scan_id is None:
        scan_id = kwargs.get('scan_id')
        test_id = kwargs.get('test_id')
        alert_id = kwargs.get('alert_id')
        flowrun_id = kwargs.get('flowrun_id')
        node_index = kwargs.get('node_index')

    # check redis task lock
    lock_name = f"lock:vrt_bg_{scan_id}"
    with task_lock(lock_name) as lock_acquired:

        # checking if task is already running
        if not lock_acquired:
            logger.info('task is already running, skipping execution.')
            return None
   
        # save sys data
        max_reached = record_task(
            resource_type='scan',
            resource_id=str(scan_id),
            task_id=str(self.request.id),
            task_method=str(inspect.stack()[0][3]),
            kwargs={
                'scan_id': str(scan_id) if scan_id is not None else None,
                'test_id': str(test_id) if test_id is not None else None, 
                'alert_id': str(alert_id) if alert_id is not None else None,
                'flowrun_id': str(flowrun_id) if flowrun_id is not None else None,
                'node_index': str(node_index) if node_index is not None else None
            }
        )

        # return early if max_attempts reached
        if max_reached:
            print('max attempts reach for vrt component')
            return None

        # run VRT component
        _vrt(scan_id, test_id, alert_id, flowrun_id, node_index)

    logger.info('ran vrt component')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def run_lighthouse_bg(
        self, 
        scan_id: str=None, 
        test_id: str=None, 
        alert_id: str=None,
        flowrun_id: str=None,
        node_index: str=None, 
        **kwargs
    ) -> None:
    """ 
    Runs the lighthouse component of the passed `Scan`

    Expects: {
        scan_id     : str, 
        test_id     : str, 
        alert_id    : str,
        flowrun_id  : str,
        node_index  : str,
        **kwargs
    }
    
    Returns -> None
    """

    # sleeping random for DB 
    time.sleep(random.uniform(2, 6))

    # get kwargs data if no scan_id
    if scan_id is None:
        scan_id = kwargs.get('scan_id')
        test_id = kwargs.get('test_id')
        alert_id = kwargs.get('alert_id')
        flowrun_id = kwargs.get('flowrun_id')
        node_index = kwargs.get('node_index')
   
    # check redis task lock
    lock_name = f"lock:lighthouse_bg_{scan_id}"
    with task_lock(lock_name) as lock_acquired:

        # checking if task is already running
        if not lock_acquired:
            logger.info('task is already running, skipping execution.')
            return None

        # save sys data
        max_reached = record_task(
            resource_type='scan',
            resource_id=str(scan_id),
            task_id=str(self.request.id),
            task_method=str(inspect.stack()[0][3]),
            kwargs={
                'scan_id': str(scan_id) if scan_id is not None else None,
                'test_id': str(test_id) if test_id is not None else None, 
                'alert_id': str(alert_id) if alert_id is not None else None,
                'flowrun_id': str(flowrun_id) if flowrun_id is not None else None,
                'node_index': str(node_index) if node_index is not None else None
            }
        )

        # return early if max_attempts reached
        if max_reached:
            print('max attempts reach for lighthouse component')
            return None

        # run lighthouse component
        _lighthouse(scan_id, test_id, alert_id, flowrun_id, node_index)

    logger.info('ran lighthouse component')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def run_yellowlab_bg(
        self, 
        scan_id: str=None, 
        test_id: str=None, 
        alert_id: str=None, 
        flowrun_id: str=None,
        node_index: str=None,
        **kwargs
    ) -> None:
    """ 
    Runs the yellowlab component of the passed `Scan`

    Expects: {
        scan_id     : str, 
        test_id     : str, 
        alert_id    : str,
        flowrun_id  : str,
        node_index  : str,
        **kwargs
    }
    
    Returns -> None
    """

    # sleeping random for DB 
    time.sleep(random.uniform(2, 6))

    # get kwargs data if no scan_id
    if scan_id is None:
        scan_id = kwargs.get('scan_id')
        test_id = kwargs.get('test_id')
        alert_id = kwargs.get('alert_id')
        flowrun_id = kwargs.get('flowrun_id')
        node_index = kwargs.get('node_index')
    
    # check redis task lock
    lock_name = f"lock:yellowlab_bg_{scan_id}"
    with task_lock(lock_name) as lock_acquired:

        # checking if task is already running
        if not lock_acquired:
            logger.info('task is already running, skipping execution.')
            return None
    
        # save sys data
        max_reached = record_task(
            resource_type='scan',
            resource_id=str(scan_id),
            task_id=str(self.request.id),
            task_method=str(inspect.stack()[0][3]),
            kwargs={
                'scan_id': str(scan_id) if scan_id is not None else None,
                'test_id': str(test_id) if test_id is not None else None, 
                'alert_id': str(alert_id) if alert_id is not None else None,
                'flowrun_id': str(flowrun_id) if flowrun_id is not None else None,
                'node_index': str(node_index) if node_index is not None else None
            }
        )

        # return early if max_attempts reached
        if max_reached:
            print('max attempts reach for yellowlab component')
            return None

        # run yellowlab component
        _yellowlab(scan_id, test_id, alert_id, flowrun_id, node_index)

    logger.info('ran yellowlab component')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def run_test(
        self, 
        test_id: str,
        alert_id: str=None,
        flowrun_id: str=None,
        node_index: str=None ,
        **kwargs
    ) -> None:
    """ 
    Primary executor for running a `Test`.
    Compatible with `FlowRuns`

    Expects: {
        test_id     : str, 
        alert_id    : str,
        flowrun_id  : str,
        node_index  : str,
        **kwargs
    }
    
    Returns -> None
    """
    # sleeping random for DB 
    time.sleep(random.uniform(2, 6))

    # get kwargs data if no test_id
    if test_id is None:
        test_id = kwargs.get('test_id')
        alert_id = kwargs.get('alert_id')
        flowrun_id = kwargs.get('flowrun_id')
        node_index = kwargs.get('node_index')
    
    # check redis task lock
    lock_name = f"lock:run_test_{test_id}"
    with task_lock(lock_name) as lock_acquired:

        # checking if task is already running
        if not lock_acquired:
            logger.info('task is already running, skipping execution.')
            return None

        # save sys data
        max_reached = record_task(
            resource_type='test',
            resource_id=str(test_id),
            task_id=str(self.request.id),
            task_method=str(inspect.stack()[0][3]),
            kwargs={
                'test_id': str(test_id), 
                'alert_id': str(alert_id) if alert_id is not None else None,
                'flowrun_id': str(flowrun_id) if flowrun_id is not None else None,
                'node_index': str(node_index) if node_index is not None else None
            }
        )

        # return early if max_attempts reached
        if max_reached:
            print('max attempts reach for Tester')
            return None

        # get test 
        test = Test.objects.get(id=test_id)

        # define objects for flowrun
        objects = [{
            'parent': str(test.page.id),
            'id': str(test_id),
            'status': 'working'
        }]

        # update flowrun
        if flowrun_id and flowrun_id != 'None':
            time.sleep(random.uniform(0.1, 5))
            update_flowrun(**{
                'flowrun_id': str(flowrun_id),
                'node_index': node_index,
                'message': f'starting test comparison algorithm for {test.page.page_url} | test_id: {str(test_id)}',
                'objects': objects
            })

        # execute test
        print('\n---------------\nStarting Test...\n---------------\n')
        test = T(test=test).run_test()

        # update FlowRun if passed
        if flowrun_id and flowrun_id != 'None':
            objects[-1]['status'] = test.status
            update_flowrun(**{
                'flowrun_id': str(flowrun_id),
                'node_index': node_index,
                'message': (
                    f'test for {test.page.page_url} completed with status: '+
                    f'{"❌ FAILED" if test.status == 'failed' else "✅ PASSED"} | test_id: {str(test_id)}'
                ),
                'objects': objects
            })

        # execute Alert if passed
        if alert_id and alert_id != 'None':
            print('running alert from `task.run_test`')
            Alerter(alert_id=alert_id, object_id=str(test.id)).run_alert()

    logger.info('Test completed')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def create_test(
        self,
        test_id: str=None,
        page_id: str=None, 
        alert_id: str=None, 
        configs: dict=settings.CONFIGS, 
        type: list=settings.TYPES,
        pre_scan: str=None,
        post_scan: str=None,
        tags: list=None,
        threshold: float=settings.TEST_THRESHOLD,
        flowrun_id: str=None,
        node_index: str=None
    ) -> None:
    """ 
    Creates a `post_scan` if necessary, waits for completion,
    and runs a `Test`

    Expects: {
        test_id     : str,
        page_id     : str, 
        alert_id    : str, 
        configs     : dict, 
        type        : list,
        pre_scan    : str,
        post_scan   : str,
        tags        : list,
        threshold   : float,
        flowrun_id  : str,
        node_index  : str
    }
    
    Returns -> None
    """

    # setting defaults
    created_test = None
    objects = []

    # get or create a Test
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
            threshold=float(threshold),
            status='working'
        )

    # adding objects
    objects.append({
        'parent': str(page.id),
        'id': str(created_test.id),
        'status': 'working'
    })

    # get pre_ & post_ scans
    if pre_scan is not None:
        pre_scan = Scan.objects.get(id=pre_scan)
    if post_scan is not None:
        post_scan = Scan.objects.get(id=post_scan)
    if post_scan is None or pre_scan is None:
        if pre_scan is None:
            # check for pre_scan existance 
            if not Scan.objects.filter(page=page).exclude(time_completed=None).exists():
                
                # create new scan if none exists
                new_scan = Scan.objects.create(
                    site=page.site,
                    page=page,
                    tags=tags, 
                    type=type,
                    configs=configs,
                )
                scan_page_bg.delay(
                    scan_id=new_scan.id,
                )

                # update flowrun
                if flowrun_id and flowrun_id != 'None':
                    update_flowrun(**{
                        'flowrun_id': flowrun_id,
                        'node_index': node_index,
                        'objects': objects,
                        'message': (
                            f'❌ test for {page.page_url} could not start because there was '+
                            f'no pre_scan available - starting new scan instead'
                        )
                    })

                # remove created_test
                created_test.delete()

                # return None
                logger.info('no pre_scan available to create Test with')
                return None
                
            # get pre_scan if exists
            pre_scan = Scan.objects.filter(
                page=page
            ).exclude(
                time_completed=None
            ).order_by('-time_completed')[0]

        # check and increment resources
        if not check_and_increment_resource(page.account.id, 'scans'):
            
            # update obects
            objects[-1]['status'] = 'failed'

            # update flowrun
            if flowrun_id and flowrun_id != 'None':
                update_flowrun(**{
                    'flowrun_id': flowrun_id,
                    'node_index': node_index,
                    'objects': objects,
                    'message': (
                        f'❌ test for {page.page_url} could not start because this account has reached '+
                        f'max_allowed_scans for this billing cycle'
                    )
                })

            # remove created_test
            created_test.delete()

            # return None
            logger.info('no more scans usage available')
            return None
        
        # create new post_scan
        post_scan = Scan.objects.create(
            site=page.site,
            page=page,
            tags=tags, 
            type=type,
            configs=configs,
        )

        # run Scan & Test tasks 
        scan_page_bg.delay(
            scan_id=post_scan.id, 
            test_id=created_test.id,
            alert_id=alert_id,
            flowrun_id=flowrun_id,
            node_index=node_index
        )

        # update flowrun
        if flowrun_id and flowrun_id != 'None':
            update_flowrun(**{
                'flowrun_id': flowrun_id,
                'node_index': node_index,
                'objects': objects,
                'message': (
                    f'test starting for {page.page_url} | '+
                    f'run_id: {flowrun_id}'
                )
            })
        
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

    # check if pre and post scan are complete and start test if True
    if pre_scan.time_completed is not None and post_scan.time_completed is not None:
        run_test.delay(
            test_id=created_test.id, 
            alert_id=alert_id,
            flowrun_id=flowrun_id,
            node_index=node_index
        )
    
    logger.info('Began Scan/Test process')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def create_test_bg(self, *args, **kwargs) -> None:
    """ 
    Depending on the scope, run create_test() for 
    all requested pages.

    Expects: {
        scope         : str
        resources     : list
        account_id    : str
        test_id       : str
        type          : list
        configs       : dict
        tags          : list
        alert_id      : str
        pre_scan      : str
        post_scan     : str
        threshold     : float
        task_id       : str
        flowrun_id    : str
        node_index    : str
    }
    
    Returns -> None
    """
    
    # get data
    scope = kwargs.get('scope')
    resources = kwargs.get('resources', [])
    account_id = kwargs.get('account_id')
    test_id = kwargs.get('test_id')
    type = kwargs.get('type')
    configs = kwargs.get('configs')
    tags = kwargs.get('tags')
    threshold = kwargs.get('threshold')
    alert_id = kwargs.get('alert_id')
    pre_scan = kwargs.get('pre_scan')
    post_scan = kwargs.get('post_scan')
    task_id = kwargs.get('task_id')
    flowrun_id = kwargs.get('flowrun_id')
    node_index = kwargs.get('node_index')

    # check for redis lock
    redis_id = task_id if task_id else secrets.token_hex(8)
    lock_name = f"lock:create_test_bg_{redis_id}"
    with task_lock(lock_name) as lock_acquired:
        
        # checking if task is already running
        if not lock_acquired:
            logger.info('task is already running, skipping execution.')
            return None

        # checking location
        if not check_location(configs.get('location', settings.LOCATION)):
            logger.info('Not running due to location param')
            return None

        # create test if none was passed
        if test_id is None:
            
            # setting defaults
            pages = []
            sites = []
            objects = []
            failed = 0

            # get account if account_id exists
            if account_id:
                account = Account.objects.get(id=account_id)
                
            # iterating through resources 
            # and adding to sites or pages
            if len(resources) > 0:
                for item in resources:
                    
                    # adding to pages
                    if item['type'] == 'page':
                        try:
                            pages.append(
                                Page.objects.get(id=item['id'])
                            ) 
                        except Exception as e:
                            print(e)
                    
                    # adding to sites
                    if item['type'] == 'site':
                        try:
                            sites.append(
                                Site.objects.get(id=item['id'])
                            ) 
                        except Exception as e:
                            print(e)
            
            # grabbing all sites because no 
            # resources were specified and scope is "account"
            if len(resources) == 0 and scope == 'account':
                sites = Site.objects.filter(account=account)

            # get all pages from existing sites
            for site in sites:
                pages += Page.objects.filter(site=site)
            
            # create a test for each page
            for page in pages:
                
                objects.append({
                    'parent': str(page.id),
                    'id': None,
                    'status': 'working'
                })

                # check resource 
                if check_and_increment_resource(page.account.id, 'tests'):

                    # updating latest_test info for page
                    page.info['latest_test']['id'] = 'placeholder'
                    page.info['latest_test']['time_created'] = str(datetime.now(timezone.utc))
                    page.info['latest_test']['time_completed'] = None
                    page.info['latest_test']['score'] = None
                    page.info['latest_test']['status'] = 'working'
                    page.save()

                    # updating latest_test info for site
                    page.site.info['latest_test']['id'] = 'placeholder'
                    page.site.info['latest_test']['time_created'] = str(datetime.now(timezone.utc))
                    page.site.info['latest_test']['time_completed'] = None
                    page.site.info['latest_test']['score'] = None
                    page.site.info['latest_test']['status'] = 'working'
                    page.site.save()

                    # create test
                    create_test.delay(
                        page_id=str(page.id),
                        type=type,
                        configs=configs,
                        tags=tags,
                        threshold=float(threshold),
                        pre_scan=pre_scan,
                        post_scan=post_scan,
                        alert_id=str(alert_id),
                        flowrun_id=str(flowrun_id),
                        node_index=node_index
                    )
                
                else:
                    # update flowrun
                    if flowrun_id and flowrun_id != 'None':
                        update_flowrun(**{
                            'flowrun_id': flowrun_id,
                            'node_index': node_index,
                            'message': (
                                f'❌ test for {page.page_url} could not start because this account has reached '+
                                f'max_allowed_tests for this billing cycle'
                            )
                        })
                    
                    # update last object
                    failed += 1
                    objects[-1]['status'] = 'failed'
                    logger.info('maxed tests reached')
                    update_schedule(task_id=task_id)
                    return None

            # update flowrun
            if flowrun_id and flowrun_id != 'None':
                update_flowrun(**{
                    'flowrun_id': flowrun_id,
                    'node_index': node_index,
                    'objects': objects,
                    'node_status': 'working',
                    'message': f'created {str(len(objects) - failed)} tests for {page.site.site_url} | run_id: {flowrun_id}'
                })
        
        # get test and run 
        if test_id:
            test = Test.objects.get(id=test_id)
            create_test.delay(
                test_id=str(test_id),
                page_id=str(test.page.id),
                type=type,
                configs=configs,
                tags=tags,
                threshold=float(threshold),
                pre_scan=pre_scan,
                post_scan=post_scan,
                alert_id=str(alert_id),
                flowrun_id=str(flowrun_id),
                node_index=node_index
            )

        # update schedule if task_id is not None
        update_schedule(task_id=task_id)

        logger.info('Created new Tests')
        return None




@shared_task
def create_report(
        page_id: str=None, 
        alert_id: str=None,
        flowrun_id: str=None,
        node_index: str=None
    ) -> None:
    """ 
    Generates a new PDF `Report` of the requested `Page`
    and runs the associated `Alert` if requested

    Expects: {
        page_id       : str, 
        alert_id      : str,
        flowrun_id    : str
        node_index    : str
    }
    
    Returns -> None
    """
    
    # get page
    page = Page.objects.get(id=page_id)
    
    # create report obj
    info = {
        "text_color": '#24262d',
        "background_color": '#e1effd',
        "highlight_color": '#ffffff',
    }
    report = Report.objects.create(
        user=page.user,
        site=page.site,
        account=page.account,
        page=page,
        info=info,
        type=['lighthouse', 'yellowlab']
    )
    
    # generate report PDF
    resp = R(report=report).generate_report()
    
    # run alert
    if alert_id and alert_id != 'None':
        Alerter(alert_id, str(report.id)).run_alert()

    # update flowrun 
    if flowrun_id and flowrun_id != 'None':
        update_flowrun(**{
            'flowrun_id': flowrun_id,
            'node_index': node_index,
            'message': f'report {'created' if  resp['success'] else 'not created'} for {page.page_url} | report_id: {str(report.id)}',
            'objects': [{
                'parent': str(page.id),
                'id': str(report.id),
                'status': 'passed' if resp['success'] else 'failed'
            }]
        })
    
    logger.info('Created new report of page')
    return None




@shared_task
def create_report_bg(*args, **kwargs) -> None:
    """
    Creates new `Reports` for the requested `Pages`

    Expects: {
        'scope'         : str,
        'resources'     : str
        'account_id'    : str
        'alert_id'      : str
        'task_id'       : str
        'flowrun_id'    : str
        'node_index'    : str
    }
     
    Returns -> None
    """

    # get data
    scope = kwargs.get('scope')
    resources = kwargs.get('resources', [])
    account_id = kwargs.get('account_id')
    alert_id = kwargs.get('alert_id')
    task_id = kwargs.get('task_id')
    flowrun_id = kwargs.get('flowrun_id')
    node_index = kwargs.get('node_index')

    # check for redis lock
    redis_id = task_id if task_id else secrets.token_hex(8)
    lock_name = f"lock:create_report_bg_{redis_id}"
    with task_lock(lock_name) as lock_acquired:
        
        # checking if task is already running
        if not lock_acquired:
            logger.info('task is already running, skipping execution.')
            return None

        # setting defaults
        pages = []
        sites = []
        objects = []

        # get account if account_id exists
        if account_id:
            account = Account.objects.get(id=account_id)

        print(f'passed resources => {resources}')
            
        # iterating through resources 
        # and adding to sites or pages
        if len(resources) > 0:
            for item in resources:
                
                # adding to pages
                if item['type'] == 'page':
                    try:
                        pages.append(
                            Page.objects.get(id=item['id'])
                        ) 
                    except Exception as e:
                        print(e)
                
                # adding to sites
                if item['type'] == 'site':
                    try:
                        sites.append(
                            Site.objects.get(id=item['id'])
                        ) 
                    except Exception as e:
                        print(e)
        
        # grabbing all sites because no 
        # resources were specified and scope is "account"
        if len(resources) == 0 and scope == 'account':
            sites = Site.objects.filter(account=account)

        # get all pages from existing sites
        for site in sites:
            pages += Page.objects.filter(site=site)

        # record objects for each report
        for page in pages:

            objects.append({
                'parent': str(page.id),
                'id': None,
                'status': 'working'
            })

        # update flowrun
        if flowrun_id and flowrun_id != 'None':
            update_flowrun(**{
                'flowrun_id': flowrun_id,
                'node_index': node_index,
                'objects': objects,
                'node_status': 'working',
                'message': f'starting {str(len(objects))} reports for {page.site.site_url} | run_id: {flowrun_id}'
            })

        # create reports for each page
        for page in pages:

            # sleeping random for DB 
            time.sleep(random.uniform(2, 6))

            create_report.delay(
                page_id=page.id,
                alert_id=alert_id,
                flowrun_id=flowrun_id,
                node_index=node_index
            )
        
        # update schedule if task_id is not None
        update_schedule(task_id=task_id)
        
        logger.info('Created new Reports')
        return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def create_auto_cases_bg(
        self, 
        site_id: str=None,
        process_id: str=None,
        start_url: str=None,
        max_cases: int=4,
        max_layers: int=5,
        configs: dict=settings.CONFIGS
    ) -> None:
    """ 
    Generates new `Cases` for the passed site.

    Expects: {
        site_id    : str,
        process_id : str,
        start_url  : str,
        max_cases  : int,
        max_layers : int,
        configs    : dict
    }
    
    Returns -> None
    """

    # checking location
    if not check_location(configs.get('location', settings.LOCATION)):
        logger.info('Not running due to location param')
        return None

    # get objects
    site = Site.objects.get(id=site_id)
    process = Process.objects.get(id=process_id)

    # get current task and save to process
    task_id = str(self.request.id)
    process.info = {'task_id': task_id}
    process.save()

    # init AutoCaser
    AC = AutoCaser(
        site=site,
        process=process,
        start_url=start_url,
        configs=configs,
        max_cases=max_cases,
        max_layers=max_layers,
    )

    # build cases
    AC.build_cases()

    logger.info('Built new auto Cases')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def case_pre_run_bg(
        self, 
        case_id: str=None,
        process_id: str=None,
    ) -> None:
    """ 
    Runs Caser.pre_run() for the passed case_id

    Expects: {
        case_id    : str,
        process_id : str,
    }
    
    Returns -> None
    """

    # get objects
    case = Case.objects.get(id=case_id)
    process = Process.objects.get(id=process_id)

    # init Caser
    C = Caser(
        case=case,
        process=process,
    )

    # build cases
    C.pre_run()

    logger.info('Completed Case pre_run')
    return None




@shared_task
def run_case(
        caserun_id: str=None, 
        alert_id: str=None,
        flowrun_id: str=None,
        node_index: str=None
    ) -> None:
    """
    Runs a CaseRun.

    Expects: {
        caserun_id  : str, 
        alert_id    : str,
        flowrun_id  : str,
        node_index  : str
    }
    
    Returns -> None
    """
    
    # get caserun
    caserun = CaseRun.objects.get(id=caserun_id)

    # running caserun
    Caser(
        caserun=caserun,
        flowrun_id=flowrun_id,
        node_index=node_index
    ).run()

    # run alert if requested
    if alert_id and alert_id != 'None':
        Alerter(alert_id=alert_id, object_id=str(caserun.id)).run_alert()

    logger.info('Ran CaseRun')
    return None




@shared_task
def create_caserun_bg(*args, **kwargs) -> None:
    """ 
    Creates and or runs a CaseRun.

    Expects: {
        caserun_id    : str, 
        resources     : list, 
        scope         : str, 
        account_id    : str, 
        case_id       : str, 
        updates       : list, 
        alert_id      : str,
        configs       : dict,
        task_id       : str,
        flowrun_id    : str,
        node_index    : str
    }
    
    Returns -> None
    """

    # get data
    caserun_id = kwargs.get('caserun_id')
    case_id = kwargs.get('case_id')
    account_id = kwargs.get('account_id')
    resources = kwargs.get('resources', [])
    scope = kwargs.get('scope')
    updates = kwargs.get('updates')
    alert_id = kwargs.get('alert_id')
    task_id = kwargs.get('task_id')
    configs = kwargs.get('configs', settings.CONFIGS)
    flowrun_id = kwargs.get('flowrun_id')
    node_index = kwargs.get('node_index')

    # check for redis lock
    redis_id = task_id if task_id else secrets.token_hex(8)
    lock_name = f"lock:create_caserun_bg_{redis_id}"
    with task_lock(lock_name) as lock_acquired:
        
        # checking if task is already running
        if not lock_acquired:
            logger.info('task is already running, skipping execution.')
            return None

        # checking location
        if not check_location(configs.get('location', settings.LOCATION)):
            logger.info('Not running due to location param')
            return None

        # settign defaults 
        case = None
        steps = None
        caseruns = []
        sites = []
        objects = []

        # get case
        if case_id:
            case = Case.objects.get(id=case_id)

        # update steps
        if case:
            steps = requests.get(case.steps['url']).json()
            for step in steps:
                if step['action']['type'] != None:
                    step['action']['time_created'] = None
                    step['action']['time_completed'] = None
                    step['action']['exception'] = None
                    step['action']['status'] = None

                if step['assertion']['type'] != None:
                    step['assertion']['time_created'] = None
                    step['assertion']['time_completed'] = None
                    step['assertion']['exception'] = None
                    step['assertion']['status'] = None

        # adding updates
        if steps:
            for update in updates:
                steps[int(update['index'])]['action']['value'] = update['value']

        # getting caserun
        if caserun_id:
            caseruns = [CaseRun.objects.get(id=caserun_id),]
        
        # creating caserun from case
        if caserun_id is None:
            
            # getting all sites in resources
            for item in resources:
                if item['type'] == 'site':
                    try:
                        sites.append(
                            Site.objects.get(id=item['id'])
                        )
                    except Exception as e:
                        print(e)
            
            # add all sites in account if scope == 'account'
            if scope == 'account' and len(resources) == 0:
                sites = Site.objects.filter(account__id=account_id)

            # iterate through sites
            for site in sites:

                # check and increment resource
                if check_and_increment_resource(site.account.id, 'caseruns'):
        
                    # create new caserun
                    caserun = CaseRun.objects.create(
                        case = case,
                        title = case.title,
                        site = site,
                        user = site.user,
                        account = site.account,
                        configs = configs,
                        steps = steps
                    )

                    # add to list
                    caseruns.append(caserun)

                    # add to objects
                    objects.append({
                        'parent': str(site.id),
                        'id': str(caserun.id),
                        'status': 'working'
                    })
                
                else:
                    # update flowrun if not able to contiune
                    if flowrun_id and flowrun_id != 'None':
                        update_flowrun(**{
                            'flowrun_id': flowrun_id,
                            'node_index': node_index,
                            'node_status': 'failed',
                            'message': (
                                f'❌ case run could not start because this account has reached '+
                                f'max_allowed_caseruns for this billing cycle'
                            )
                        })

        # update flowrun
        if flowrun_id and flowrun_id != 'None':
            update_flowrun(**{
                'flowrun_id': flowrun_id,
                'node_index': node_index,
                'node_status': 'working',
                'objects': objects
            })

        # iterate through caseruns and run
        for caserun in caseruns:
            run_case.delay(
                caserun_id=str(caserun.id),
                alert_id=alert_id,
                flowrun_id=flowrun_id,
                node_index=node_index
            )

        # update schedule if task_id is not None
        update_schedule(task_id=task_id)

        logger.info('Created CaseRuns')
        return None




@shared_task
def create_flowrun_bg(*args, **kwargs) -> None:
    """ 
    Creates and runs a FlowRun.

    Expects: {
        flow_id       : str, 
        resources     : list, 
        scope         : str, 
        account_id    : str, 
        alert_id      : str,
        configs       : dict,
        task_id       : str
    }
    
    Returns -> None
    """

    # get data
    flow_id = kwargs.get('flow_id')
    account_id = kwargs.get('account_id')
    resources = kwargs.get('resources', [])
    scope = kwargs.get('scope')
    alert_id = kwargs.get('alert_id')
    task_id = kwargs.get('task_id')
    configs = kwargs.get('configs', settings.CONFIGS)

    # check for redis lock
    redis_id = task_id if task_id else secrets.token_hex(8)
    lock_name = f"lock:create_flowrun_bg_{redis_id}"
    with task_lock(lock_name) as lock_acquired:
        
        # checking if task is already running
        if not lock_acquired:
            logger.info('task is already running, skipping execution.')
            return None

        # checking location
        if not check_location(configs.get('location', settings.LOCATION)):
            logger.info('Not running due to location param')
            return None

        # settign defaults 
        flow = None
        sites = []

        # get flow
        if flow_id:
            flow = Flow.objects.get(id=flow_id)

        # getting all sites in resources
        for item in resources:
            if item['type'] == 'site':
                try:
                    sites.append(
                        Site.objects.get(id=item['id'])
                    )
                except Exception as e:
                    print(e)
        
        # add all sites in account if scope == 'account'
        if scope == 'account' and len(resources) == 0:
            sites = Site.objects.filter(account__id=account_id)

        # iterate through sites
        for site in sites:

            # check and increment resource
            if check_and_increment_resource(site.account.id, 'flowruns'):

                # set flowrun_id
                flowrun_id = uuid.uuid4()

                # update nodes
                _nodes = flow.nodes
                for i in range(len(_nodes)):
                    _nodes[i]['data']['status'] = 'queued'
                    _nodes[i]['data']['finalized'] = False
                    _nodes[i]['data']['time_started'] = None
                    _nodes[i]['data']['time_completed'] = None
                    _nodes[i]['data']['alert_id'] = alert_id
                    _nodes[i]['data']['objects'] = []

                # updates edges
                _edges = flow.edges
                for i in range(len(_edges)):
                    _edges[i]['animated'] = False
                    _edges[i]['style'] = None

                # create init log
                logs = [{
                    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f'),
                    'message': f'system starting up for run_id: {str(flowrun_id)}',
                    'step': '1'
                },]

                # create flowrun
                flowrun = FlowRun.objects.create(
                    id      = flowrun_id,
                    flow    = flow,
                    user    = flow.user,
                    account = flow.account,
                    site    = site,
                    title   = flow.title,
                    nodes   = _nodes,
                    edges   = _edges,
                    logs    = logs,
                    configs = configs
                )

                # update flow with time_last_run
                flow = Flow.objects.get(id=flow_id)
                flow.time_last_run = datetime.now(timezone.utc)
                flow.save()
            
            else:
                logger.info('max flowruns reached')

        # update schedule
        update_schedule(task_id=task_id)

        logger.info('Created FlowRuns')
        return None




def create_issue( 
        account_id  : str=None, 
        object_id   : str=None, 
        title       : str=None, 
        details     : str=None,
        generate    : bool=False
    ) -> dict:
    """ 
    Creates and `Issue` for each passed obj, using either 
    passed data or Issuer.build_issue()

    Expects: {
        'account_id'    : str, 
        'object_id'     : str,
        'title'         : str,
        'details'       : str,
        'generate'      : bool
    }

    Returns: {
        'message' : str,
        'success' : bool
    }
    """

    # set defaults
    message = ''
    success = True
    affected = {}
    trigger = {}
    issue = None

    # get object from object_id
    obj = get_obj(object_id=object_id)

    # check for success
    if not obj.get('success'):
        message = f'❌ object not found - unable to create issue for {object_id}'
        success = False
        return {'message': message, 'success': success, 'issue': issue}

    # check for 'generate'
    if generate:

        # build Issue using Issuer().build_issue()
        try:
            issue = Issuer(
                scan        = obj.get('obj') if obj.get('obj_type') == 'Scan' else None,
                test        = obj.get('obj') if obj.get('obj_type') == 'Test' else None,
                caserun     = obj.get('obj') if obj.get('obj_type') == 'CaseRun' else None,
                threshold   = obj.get('obj').threshold if obj.get('obj_type') == 'Test' else 75
            ).build_issue()

            # build messge
            message = f'created new issue for {obj.get('obj_type').lower()} | issue_id {issue.id}'
            success = True
            
        except Exception as e:
            print(e)
            # build messge
            message = f'❌ generation failed - unable to create issue for {object_id}'
            success = False

    # check for manual creation
    if not generate:
        
        # create trigger
        trigger = {
            'type'  : obj.get('obj_type').lower(), 
            'id'    : str(obj.get('obj').id)
        }

        # create affected
        affected = {
            'type'  : 'site' if obj.get('obj_type') == 'CaseRun' else 'page',
            'id'    : str(obj.get('obj').site.id) if obj.get('obj_type') == 'CaseRun' else str(obj.get('obj').page.id),
            'str'   : obj.get('obj').site.site_url if obj.get('obj_type') == 'CaseRun' else obj.get('obj').page.page_url
        }

        # get account & secrets
        account = Account.objects.get(id=account_id)
        secrets = Secret.objects.filter(account=account)

        # transpose data
        title = transpose_data(title, obj.get('obj'), secrets)
        details = transpose_data(details, obj.get('obj'), secrets)

        # build Issue
        issue = Issue.objects.create(
            account  = account,
            title    = title,
            details  = details,
            labels   = [], 
            trigger  = trigger,
            affected = affected
        )

        # build messge
        message = f'created new issue for {obj.get('obj_type').lower()} | issue_id {issue.id}'
        success = True

    # return data
    data = {
        'message'   : message,
        'success'   : success,
        'issue'     : issue
    }
    return data




@shared_task
def create_issue_bg(
        account_id: str=None, 
        objects: list=None,
        title: str=None, 
        details: str=None,
        generate: bool=True,
        flowrun_id: str=None,
        node_index: str=None
    ) -> None:
    """ 
    Runs create_issue for each passed `object`

    Expects: {
        'account_id'    : str, 
        'objects'       : list,
        'title'         : str,
        'details'       : str,
        'generate'      : bool,
        'flowrun_id'    : str,
        'node_index'    : str,
    }

    Returns: None
    """

    # create objects list for flowrun
    obj_list = []
    for o in objects:
        obj_list.append({
            'parent': o['id'],
            'id': None, 
            'status': 'working'
        })
    
    # update flowrun if requested
    if flowrun_id and flowrun_id != 'None':
        # update flowrun
        update_flowrun(**{
            'flowrun_id': flowrun_id,
            'node_index': node_index,
            'message': f'building {len(obj_list)} Issues | run_id: {flowrun_id}',
            'objects': obj_list
        })

    # interating through objects
    for obj in objects:

        # sleeping random for DB 
        time.sleep(random.uniform(2, 6))

        # run create_issue
        resp = create_issue( 
            account_id=account_id, 
            object_id=obj['id'], 
            title=title, 
            details=details,
            generate=generate
        )
        
        if flowrun_id and flowrun_id != 'None':
            # update flowrun
            update_flowrun(**{
                'flowrun_id': flowrun_id,
                'node_index': node_index,
                'message': resp.get('message'),
                'objects': [{
                    'parent': obj['id'],
                    'id': str(resp.get('issue').id) if resp.get('success') else None, 
                    'status': 'passed' if resp.get('success') else 'failed'
                }]
            })

    logger.info('created issues')
    return None




@shared_task
def delete_site_s3_bg(site_id: str) -> None:
    """
    Deletes the directory in s3 bucked associated 
    with passed site

    Expects: {
        'site_id': str
    }

    Returns -> None
    """

    # deleting s3 objects
    try:
        bucket = s3().Bucket(settings.AWS_STORAGE_BUCKET_NAME)
        bucket.objects.filter(Prefix=str(f'static/sites/{site_id}/')).delete()
    except:
        pass

    logger.info('Deleted site s3 objects')
    return None




@shared_task
def delete_page_s3_bg(page_id: str, site_id: str) -> None:
    """
    Deletes the directory in s3 bucked associated 
    with passed page

    Expects: {
        'site_id': str,
        'page_id': str
    }

    Returns -> None
    """

    # deleting s3 objects
    try:
        bucket = s3().Bucket(settings.AWS_STORAGE_BUCKET_NAME)
        bucket.objects.filter(Prefix=str(f'static/sites/{site_id}/{page_id}/')).delete()
    except:
        pass
    
    logger.info('Deleted page s3 objects')
    return None




@shared_task
def delete_scan_s3_bg(scan_id: str, site_id: str, page_id: str) -> None:
    """
    Deletes the directory in s3 bucked associated 
    with passed scan

    Expects: {
        'scan_id': str,
        'site_id': str,
        'page_id': str
    }

    Returns -> None
    """

    # deleting s3 objects
    try:
        bucket = s3().Bucket(settings.AWS_STORAGE_BUCKET_NAME)
        bucket.objects.filter(Prefix=str(f'static/sites/{site_id}/{page_id}/{scan_id}/')).delete()
    except:
        pass
    
    logger.info('Deleted scan s3 objects')
    return None




@shared_task
def delete_test_s3_bg(test_id: str, site_id: str, page_id: str) -> None:
    """
    Deletes the directory in s3 bucked associated 
    with passed test

    Expects: {
        'test_id': str,
        'site_id': str,
        'page_id': str
    }

    Returns -> None
    """

    # deleting s3 objects
    try:
        bucket = s3().Bucket(settings.AWS_STORAGE_BUCKET_NAME)
        bucket.objects.filter(Prefix=str(f'static/sites/{site_id}/{page_id}/{test_id}/')).delete()
    except:
        pass
    
    logger.info('Deleted test s3 objects')
    return None




@shared_task
def delete_caserun_s3_bg(caserun_id: str) -> None:
    """
    Deletes the directory in s3 bucked associated 
    with passed test

    Expects: {
        'caserun_id': str,
    }

    Returns -> None
    """

    # deleting s3 objects
    try:
        bucket = s3().Bucket(settings.AWS_STORAGE_BUCKET_NAME)
        bucket.objects.filter(Prefix=str(f'static/caserun/{caserun_id}/')).delete()
    except:
        pass

    logger.info('Deleted caserun s3 objects')
    return None




@shared_task
def delete_report_s3_bg(report_id: str) -> None:
    """
    Deletes the file in s3 bucked associated 
    with passed report

    Expects: {
        'report_id': str,
    }

    Returns -> None
    """

    # get site
    site = Report.objects.get(id=report_id).site

    # deleting s3 objects
    try:
        bucket = s3().Bucket(settings.AWS_STORAGE_BUCKET_NAME)
        bucket.objects.filter(Prefix=str(f'static/sites/{site.id}/{report_id}.pdf')).delete()
    except:
        pass

    logger.info('Deleted Report pdf in s3')
    return None




@shared_task
def delete_case_s3_bg(case_id: str) -> None:
    """
    Deletes the file in s3 bucked associated 
    with passed case_id

    Expects: {
        'case_id': str,
    }

    Returns -> None
    """

    # deleting s3 objects
    try:
        bucket = s3().Bucket(settings.AWS_STORAGE_BUCKET_NAME)
        bucket.objects.filter(Prefix=str(f'static/cases/{case_id}/')).delete()
    except:
        pass

    logger.info('Deleted Case step data in s3')
    return None




@shared_task
def purge_logs(username: str=None) -> None:
    """ 
    Deletes all `Logs` associated with the passed "username".
    If "username" is None, deletes all `Logs`.

    Expects: {
        'username': str
    }

    Returns -> None
    """

    # delete logs
    if username:
        user = User.objects.get(username=username)
        Log.objects.filter(user=user).delete()
    else:
        Log.objects.all().delete()

    logger.info('Purged logs')
    return None




@shared_task
def reset_account_usage(account_id: str=None) -> None:
    """ 
    Loops through each active `Account`, checks to see
    if timezone.today() is the start of the 
    next billing cycle, and resets `Account.usage`

    Expects: {
        'account_id': <str> (OPTIONAL)
    }

    Returns: None
    """

    # init Stripe client
    stripe.api_key = settings.STRIPE_PRIVATE

    # check for account_id
    if account_id is not None:
        accounts = [Account.objects.get(id=account_id)]
    else:
        # get all active accounts
        accounts = Account.objects.filter(active=True)

    # get current date
    today = datetime.today()
    today_str = today.strftime('%Y-%m-%d')
    print(f'today -> {today_str}')

    # setting format for today
    f = '%Y-%m-%d %H:%M:%S.%f'

    # reset account.usage
    def reset_usage(account) -> None:
        
        # update usage
        account.usage['scans'] = 0
        account.usage['tests'] = 0
        account.usage['caseruns'] = 0
        account.usage['flowruns'] = 0

        # update meta
        meta = account.meta
        meta['last_usage_reset'] = today.strftime(f)
        account.meta = meta
        account.save()

        # log action
        print(f'reset account "{account.name}" usage')
        return None

    # loop through each
    for account in accounts:

        # check if account is active and not free
        if account.active and account.type != 'free' and account.sub_id != None:
                
            # get stripe sub
            sub = stripe.Subscription.retrieve(
                account.sub_id
            )

            # get and formate sub.current_period_end
            sub_date = datetime.fromtimestamp(
                sub.current_period_end
            ).strftime('%Y-%m-%d')
            print(f'sub_date -> {sub_date}')

            # reset accout usage if today is 
            # begining of sub payment peroid
            # OR if a specific account was requested
            if today_str == sub_date or account_id is not None:

                # reset usage
                reset_usage(account)

        # check if accout is free
        if account.type == 'free':

            # get last usage reset date from meta
            last_usage_date_str = account.meta.get('last_usage_reset') if account.meta else None
            if last_usage_date_str is not None:
                
                # clean date_str
                last_usage_date_str = last_usage_date_str.replace('T', ' ').replace('Z', '')

                # format date str as datetime obj
                last_usage_date = datetime.strptime(last_usage_date_str, f)

                print(f'days since last reset -> {abs((today - last_usage_date).days)}')

                # check if over 30 days
                if abs((today - last_usage_date).days) >= 30:
                    
                    # reset usage
                    reset_usage(account)

            
    return None




@shared_task
def temp_account_reset() -> None:


    for account in Account.objects.all():
        usage = get_usage_default()
        usage['sites'] = Site.objects.filter(account=account).count()
        account.usage = usage
        account.save()

    return None




@shared_task
def update_sub_price(account_id: str=None, sites_allowed: int=None) -> None:
    """ 
    Update price for existing stripe Subscription 
    based on new `Account.usage.sites_allowed`

    Expects: {
        'account_id'       : <str> (REQUIRED)   
        'sites_allowed'    : <int> (OPTIONAL)   
    }

    Returns: None
    """

    # init Stripe client
    stripe.api_key = settings.STRIPE_PRIVATE

    # get account
    account = Account.objects.get(id=account_id)

    # set new sites_allowed
    if sites_allowed is not None:
        account.usage['sites_allowed'] = sites_allowed
        account.save()
    
    # get sites_allowed
    if sites_allowed is None:
        sites_allowed = account.usage['sites_allowed']

    # get account coupon
    discount = 0
    if account.meta.get('coupon'):
        discount = account.meta['coupon']['discount']

    # calculate
    price = (
        (
            54.444 * (sites_allowed ** 0.4764)
        ) * 100
    )

    # apply discount
    price = price - (price * discount)

    # update for interval 
    price_amount = round(price if account.interval == 'month' else (price * 10))

    # create new Stripe Price 
    price = stripe.Price.create(
        product=account.product_id,
        unit_amount=price_amount,
        currency='usd',
        recurring={'interval': account.interval,},
    )

    # update Stripe Subscription
    sub = stripe.Subscription.retrieve(account.sub_id)
    stripe.Subscription.modify(
        account.sub_id,
        cancel_at_period_end=False,
        pause_collection='',
        proration_behavior='create_prorations',
        items=[{
            'id': sub['items']['data'][0].id,
            'price': price.id,
        }],
        expand=['latest_invoice.payment_intent'],
    )

    # updating price defaults and archiving old price
    stripe.Product.modify(account.product_id, default_price=price,)
    stripe.Price.modify(account.price_id, active=False)

    # update account with new info
    account.price_id = price.id
    account.price_amount = price_amount
    account.usage['sites'] = sites_allowed
    account.usage['scans_allowed'] = (sites_allowed * 200)
    account.usage['tests_allowed'] = (sites_allowed * 200)
    account.usage['caseruns_allowed'] = (sites_allowed * 10)
    account.usage['flowruns_allowed'] = (sites_allowed * 10)
    account.save()

    print(f'new price -> {price_amount}')
    
    # return 
    return None




@shared_task
def delete_old_resources(account_id: str=None, days_to_live: int=30) -> None:
    """ 
    Deletes all `Tests`, `Scans`, `CaseRuns`, 
    `Logs`, and `Processes` that have reached expiry

    Expects: {
        account_id   : str, 
        days_to_live : int
    }
    
    Returns -> None
    """

    # calculate max dates
    max_date = datetime.now() - timedelta(days=days_to_live)
    max_proc_date = datetime.now() - timedelta(days=1)

    # scope resources to account if requested
    if account_id is not None:
        tests = Test.objects.filter(site__account__id=account_id, time_created__lte=max_date)
        scans = Scan.objects.filter(site__account__id=account_id, time_created__lte=max_date)
        caseruns = CaseRun.objects.filter(account__id=account_id, time_created__lte=max_date)
        flowruns = FlowRun.objects.filter(account__id=account_id, time_created__lte=max_date)
        processes = Process.objects.filter(account__id=account_id, time_created__lte=max_proc_date)
        
        # get all old Logs
        members = Member.objects.filter(account__id=account_id)
        logs = []
        for member in members:
            logs += Log.objects.filter(user=member.user, time_created__lte=max_proc_date)

    # get all resoruces if no account_id
    else:
        tests = Test.objects.filter(time_created__lte=max_date)
        scans = Scan.objects.filter(time_created__lte=max_date)
        caseruns = CaseRun.objects.filter(time_created__lte=max_date)
        flowruns = FlowRun.objects.filter(time_created__lte=max_date)
        processes = Process.objects.filter(time_created__lte=max_proc_date)
        logs = Log.objects.filter(time_created__lte=max_proc_date)

    # delete each resource in each type
    for test in tests:
        delete_test_s3_bg.delay(test.id, test.site.id, test.page.id)
        test.delete()
    for scan in scans:
        delete_scan_s3_bg.delay(scan.id, scan.site.id, scan.page.id)
        scan.delete()
    for caserun in caseruns:
        delete_caserun_s3_bg.delay(caserun.id)
        caserun.delete()
    for flowrun in flowruns:
        flowrun.delete()
    for process in processes:
        process.delete()
    for log in logs:
        log.delete()
    
    logger.info('Cleaned up resources')
    return None




@shared_task
def data_retention() -> None:
    """ 
    Helper task for looping through each account and deleting old resources using 
    delete_old_resources()

    Returns -> None
    """

    # get all accounts
    accounts = Account.objects.all()

    # loop through each account
    for account in accounts:

        # delete old resources
        delete_old_resources.delay(
            account_id=account.id,
            days_to_live=account.usage['retention_days']
        )
    
    logger.info('Requested resource cleanup')
    return None




@shared_task
def delete_admin_sites(days_to_live: int=1) -> None:
    """ 
    Delete all admin sites which are older 
    than 'days_to_live'

    Expects: {
        'days_to_live': int 
    }
    
    Returns -> None
    """

    # calculate max date
    max_date = datetime.now() - timedelta(days=days_to_live)

    # filter sites by max_date and admin 
    sites = Site.objects.filter(time_created__lte=max_date, user__username='admin')

    # delete each site
    for site in sites:
        delete_site_s3_bg.delay(site.id)
        site.delete()
    
    logger.info('Cleaned up admin sites')
    return None




@shared_task
def create_prospect(user_email: str=None) -> None:
    """ 
    Sends an API request to Cursion Landing which 
    creates a new `Prospect`

    Expects: {
        'user_email': str
    }
    
    Returns -> None
    """

    if settings.MODE == 'selfhost':
        print('not running because of selfhost mode')
        return None

    # get user by id
    user = User.objects.get(email=user_email)
    phone = None
    if Member.objects.filter(user=user).exists():
        member = Member.objects.get(user=user)
        phone = member.phone

    # get account by user
    account = Account.objects.get(user=user)

    # determinig user's 'status'
    if account.type == 'free':
        if Site.objects.filter(account=account).exists():
            _status = 'warm' # account has one site onboarded
        else:
            _status = 'cold' # account is free but no site onboarded
    if account.type != 'free':
        if account.active:
            _status = 'customer' # account is active and paid
        else:
            _status = 'warm' # account is paused and paid
    if account.type == 'new':
        _status = 'cold' # account has not onboarded
    if account.type == 'selfhost':
        _status = 'customer' # account is active and paid
    
    # setup configs
    url = f'{settings.LANDING_URL_ROOT}/ops/prospect'
    headers = {
        "content-type": "application/json",
        "Authorization" : f'Token {settings.LANDING_API_KEY}'
    }
    data = {
        'first_name': str(user.first_name),
        'last_name': str(user.last_name),
        'email': str(user.email),
        'phone': phone,
        'license_key': str(account.license_key),
        'info': account.info,
        'status': _status,
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
        message = e

    # format response
    data = {
        'success': success,
        'message': message
    }
    
    logger.info(f'Sent Prospect creation request -> {data}')
    return None




@shared_task
def create_report_export_bg(report_id: str=None, email: str=None, first_name: str=None) -> None:
    """ 
    Creates and exports a Cursion landing report

    Expects: {
        report_id   : str, 
        email       : str, 
        first_name  : str
    }
    
    Returns -> None
    """

    # create and export 
    data = create_and_send_report_export(
        report_id=report_id,
        email=email,
        first_name=first_name
    )

    logger.info(f'Created and sent report export -> {data}')
    return None




@shared_task
def send_invite_link_bg(member_id: str) -> None:
    """ 
    Sends an invite link to the requested member

    Expects: {
        'member_id': str
    }

    Returns -> None
    """
    
    # get member
    member = Member.objects.get(id=member_id)

    # send invite
    send_invite_link(member)

    logger.info('Sent invite')
    return None




@shared_task
def send_remove_alert_bg(member_id: str) -> None:
    """ 
    Sends a 'removed' email to the requested member

    Expects: {
        'member_id': str
    }

    Returns -> None
    """

    # get member
    member = Member.objects.get(id=member_id)

    # send email
    send_remove_alert(member)

    logger.info('Sent remove alert')
    return None




@shared_task
def send_phone_bg( 
        account_id: str=None, 
        objects: list=None,
        phone_number: str=None, 
        body: str=None,
        flowrun_id: str=None,
        node_index: str=None
    ) -> dict:
    """ 
    Run `Alerts.send_phone` as a backgroud task

    Expects: { 
        'account_id'    : str, 
        'objects'       : list,
        'phone_number'  : str,
        'body'          : str,
        'flowrun_id'    : str,
        'node_index'    : str,
    }

    Returns: None
    """

    # interating through objects
    for obj in objects:

        # sleeping random for DB 
        time.sleep(random.uniform(2, 6))

        # run send_phone
        resp = send_phone( 
            account_id=account_id, 
            object_id=obj['id'], 
            phone_number=phone_number, 
            body=body,
        )
        
        if flowrun_id and flowrun_id != 'None':
            # update flowrun
            update_flowrun(**{
                'flowrun_id': flowrun_id,
                'node_index': node_index,
                'message': resp.get('message'),
                'objects': [{
                    'parent': obj['parent'],
                    'id': obj['id'], 
                    'status': 'passed' if resp.get('success') else 'failed'
                }]
            })

    logger.info('sent phone message')
    return None




@shared_task
def send_slack_bg( 
        account_id: str=None, 
        objects: list=None, 
        body: str=None,
        flowrun_id: str=None,
        node_index: str=None
    ) -> dict:
    """ 
    Run `Alerts.send_slack` as a backgroud task

    Expects: { 
        'account_id'    : str, 
        'objects'       : list,
        'body'          : str,
        'flowrun_id'    : str,
        'node_index'    : str,
    }

    Returns: None
    """

    # interating through objects
    for obj in objects:

        # sleeping random for DB 
        time.sleep(random.uniform(2, 6))

        # run send_slack
        resp = send_slack( 
            account_id=account_id, 
            object_id=obj['id'], 
            body=body,
        )
        
        if flowrun_id and flowrun_id != 'None':
            # update flowrun
            update_flowrun(**{
                'flowrun_id': flowrun_id,
                'node_index': node_index,
                'message': resp.get('message'),
                'objects': [{
                    'parent': obj['parent'],
                    'id': obj['id'], 
                    'status': 'passed' if resp.get('success') else 'failed'
                }]
            })

    logger.info('sent slack message')
    return None




@shared_task
def send_email_bg( 
        account_id: str=None, 
        objects: list=None, 
        message_obj: dict=None,
        flowrun_id: str=None,
        node_index: str=None
    ) -> dict:
    """ 
    Run `Alerts.sendgrid_email` as a backgroud task

    Expects: { 
        'account_id'    : str, 
        'objects'       : list,
        'message_obj'   : dict,
        'flowrun_id'    : str,
        'node_index'    : str,
    }

    Returns: None
    """

    # interating through objects
    for obj in objects:

        # sleeping random for DB 
        time.sleep(random.uniform(2, 6))

        # run sendgrid_email
        resp = sendgrid_email( 
            account_id=account_id, 
            object_id=obj['id'], 
            message_obj=message_obj,
        )
        
        if flowrun_id and flowrun_id != 'None':
            # update flowrun
            update_flowrun(**{
                'flowrun_id': flowrun_id,
                'node_index': node_index,
                'message': resp.get('message'),
                'objects': [{
                    'parent': obj['parent'],
                    'id': obj['id'], 
                    'status': 'passed' if resp.get('success') else 'failed'
                }]
            })

    logger.info('sent email message')
    return None




@shared_task
def send_webhook_bg( 
        account_id: str=None, 
        objects: list=None, 
        request_type: str=None,
        url: str=None,
        headers: str=None,
        payload: str=None,
        flowrun_id: str=None,
        node_index: str=None
    ) -> dict:
    """ 
    Run `Alerts.sendgrid_email` as a backgroud task

    Expects: { 
        'account_id'    : str, 
        'objects'       : list,
        'request_type'  : str,
        'url'           : str,
        'headers'       : str,
        'payload'       : str,
        'flowrun_id'    : str,
        'node_index'    : str,
    }

    Returns: None
    """

    # interating through objects
    for obj in objects:

        # sleeping random for DB 
        time.sleep(random.uniform(2, 6))
    
        # run sendgrid_email
        resp = send_webhook( 
            account_id=account_id, 
            object_id=obj['id'], 
            request_type=request_type,
            url=url,
            headers=headers,
            payload=payload
        )
            
        if flowrun_id and flowrun_id != 'None':
            # update flowrun
            update_flowrun(**{
                'flowrun_id': flowrun_id,
                'node_index': node_index,
                'message': resp.get('message'),
                'objects': [{
                    'parent': obj['parent'],
                    'id': obj['id'], 
                    'status': 'passed' if resp.get('success') else 'failed'
                }]
            })

    logger.info('sent webhook message')
    return None




@shared_task
def migrate_site_bg(
        login_url: str, 
        admin_url: str,
        username: str,
        password: str,
        email_address: str,
        destination_url: str,
        sftp_address: str,
        dbname: str,
        sftp_username: str,
        sftp_password: str, 
        plugin_name: str,
        wait_time: int,
        process_id: str,
        driver: str,
    ) -> None:
    """ 
    Runs the WP site migration process.

    Expects: {
        login_url: str, 
        admin_url: str,
        username: str,
        password: str,
        email_address: str,
        destination_url: str,
        sftp_address: str,
        dbname: str,
        sftp_username: str,
        sftp_password: str, 
        plugin_name: str,
        wait_time: int,
        process_id: str,
        driver: str,
    }

    Returns -> None
    """

    # init wordpress for selenium
    wp = W(
        login_url=login_url, 
        admin_url=admin_url,
        username=username,
        password=password,
        email_address=email_address,
        destination_url=destination_url,
        sftp_address=sftp_address,
        dbname=dbname,
        sftp_username=sftp_username,
        sftp_password=sftp_password, 
        wait_time=wait_time,
        process_id=process_id,

    )

    # login
    wp_status = wp.login()
    # adjust lang
    wp_status = wp.begin_lang_check()
    # install plugin
    wp_status = wp.install_plugin(plugin_name=plugin_name)
    # launch migration
    wp_status = wp.launch_migration()
    # run migration
    wp_status = wp.run_migration()
    # re adjust lang
    # wp_status = wp.end_lang_check()
    

    logger.info('Finished Migration')
    return None



