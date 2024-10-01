from celery.utils.log import get_task_logger
from celery import shared_task, Task
from .utils.crawler import Crawler
from .utils.scanner import Scanner as S
from .utils.tester import Tester as T
from .utils.reporter import Reporter as R
from .utils.wordpress import Wordpress as W
from .utils.automater import Automater
from .utils.caser import Caser
from .utils.autocaser import AutoCaser
from .utils.exporter import create_and_send_report_export
from .utils.scanner import (
    _html_and_logs, _vrt, _lighthouse, 
    _yellowlab
)
from .utils.alerts import send_invite_link, send_remove_alert
from .models import *
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
from cursion import settings
import asyncio, boto3, time, requests, json, stripe









class BaseTaskWithRetry(Task):
    autoretry_for = (Exception, KeyError)
    retry_kwargs = {'max_retries': 2}
    retry_backoff = True




# setting logger 
logger = get_task_logger(__name__)




# setting s3 instance
def s3():
    s3 = boto3.resource('s3', 
        aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
        aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
        region_name=str(settings.AWS_S3_REGION_NAME), 
        endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
    )
    return s3




def check_and_increment_resource(account: object, resource: str) -> bool:
    """ 
    Adds 1 to the Account.usage.{resource} if 
    {resource}_allowed has not been reached.

    Expcets: {
        'account'  : <object>,
        'resource' : <str> 'scan', 'test', or 'testcase
    }

    Returns: Bool, True if resource was incremented.
    """

    # define defaults
    success = False

    # check allowance
    if (int(account.usage[f'{resource}']) + 1) <= int(account.usage[f'{resource}_allowed']):
        
        # increment and update success
        account.usage[f'{resource}'] = 1 + int(account.usage[f'{resource}'])
        account.save()
        success = True

    # return response
    return success




@shared_task(bind=True, base=BaseTaskWithRetry)
def create_site_and_pages_bg(self, site_id: str=None, configs: dict=settings.CONFIGS) -> None:
    """ 
    Takes a newly created `Site`, initiates a Crawl and 
    initial `Scan` for each crawled page

    Expcets: {
        site_id: str, 
        configs: dict
    }
    
    Returns -> None
    """

    # getting site and updating for time_crawl_start
    site = Site.objects.get(id=site_id)
    site.time_crawl_started = timezone.now()
    site.time_crawl_completed = None
    site.save()

    # crawl site 
    pages = Crawler(url=site.site_url, max_urls=site.account.max_pages).get_links()
    
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
            if check_and_increment_resource(site.account, 'scans'):

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
    site.time_crawl_completed = timezone.now()
    site.save()

    logger.info('Added site and all pages')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def crawl_site_bg(self, site_id: str=None, configs: dict=settings.CONFIGS) -> None:
    """ 
    Takes an existing `Site`, initiates a new Crawl and 
    initial `Scan` for each newly added page

    Expcets: {
        site_id: str, 
        configs: dict
    }
    
    Returns -> None
    """
    
    # getting site and updating for time_crawl_start
    site = Site.objects.get(id=site_id)
    site.time_crawl_started = timezone.now()
    site.time_crawl_completed = None
    site.save()
    
    # getting old pages for comparison
    old_pages = Page.objects.filter(site=site)
    old_urls = []
    for p in old_pages:
        old_urls.append(p.page_url)

    # crawl site 
    new_urls = Crawler(url=site.site_url, max_urls=site.account.max_pages).get_links()
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
        if current_count < site.account.max_pages:
            page = Page.objects.create(
                site=site,
                page_url=url,
                user=site.user,
                account=site.account,
            )

            # check resouce allowance
            if check_and_increment_resource(site.account, 'scans'):

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
    site.time_crawl_completed = timezone.now()
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
    latest_test = None
    latest_scan = None

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
        
        if Scan.objects.filter(page=p).exists()and \
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
            if page == p:

                # latest_scan info
                if latest_scan:
                    page.info['latest_scan']['id'] = str(latest_scan.id)
                    page.info['latest_scan']['time_created'] = str(latest_scan.time_created)
                    page.info['latest_scan']['time_completed'] = str(latest_scan.time_completed)
                    page.info['latest_scan']['score'] = latest_scan.score
                    page.info['lighthouse'] = latest_scan.lighthouse.get('scores')
                    page.info['yellowlab'] = latest_scan.yellowlab.get('scores')
                if latest_scan is None and (resource == 'scan' or resource == 'all'):
                    page.info['latest_scan']['id'] = None
                    page.info['latest_scan']['time_created'] = None
                    page.info['latest_scan']['time_completed'] = None
                    page.info['latest_scan']['score'] = None
                    page.info['lighthouse'] = None
                    page.info['yellowlab'] = None

                # latest_test info
                if latest_test:
                    page.info['latest_test']['id'] = str(latest_test.id)
                    page.info['latest_test']['time_created'] = str(latest_test.time_created)
                    page.info['latest_test']['time_completed'] = str(latest_test.time_completed)
                    page.info['latest_test']['score'] = (round(latest_test.score * 100) / 100)
                    page.info['latest_test']['status'] = latest_test.status
                if latest_test is None and (resource == 'test' or resource == 'all'):
                    page.info['latest_test']['id'] = None
                    page.info['latest_test']['time_created'] = None
                    page.info['latest_test']['time_completed'] = None
                    page.info['latest_test']['score'] = None
                    page.info['latest_test']['status'] = None

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
        scan_id: str=None, 
        test_id: str=None, 
        automation_id: str=None, 
        configs: dict=settings.CONFIGS
    ) -> None:
    """ 
    Runs all the requested `Scan` components 
    of the passed `Scan`.

    Expects: {
        scan_id       : str, 
        test_id       : str, 
        automation_id : str, 
        configs       : dict
    }

    Returns -> None
    """
    
    # get scan object
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
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def create_scan(
        self,
        scan_id: str=None,
        page_id: str=None, 
        type: list=settings.TYPES,
        automation_id: str=None, 
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
        automation_id   : str, 
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

    # run scan and automation if necessary
    scan = S(scan=created_scan).build_scan()
    if automation_id:
        print('running automation from `task.create_scan`')
        Automater(automation_id, scan.id).run_automation()
    
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
        'account_id'    : str
        'type'          : list,
        'configs'       : dict,
        'tags'          : list,
        'automation_id' : str,
        'task_id'       : str
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
    automation_id = kwargs.get('automation_id')
    task_id = kwargs.get('task_id')

    # setting defaults
    pages = []
    sites = []

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
        if check_and_increment_resource(page.account, 'scans'):

            # updating latest_scan info for page
            page.info['latest_scan']['id'] = 'placeholder'
            page.info['latest_scan']['time_created'] = str(timezone.now())
            page.info['latest_scan']['time_completed'] = None
            page.info['latest_scan']['score'] = None
            page.info['latest_scan']['score'] = None
            page.save()

            # updating latest_scan info for site
            page.site.info['latest_scan']['id'] = 'placeholder'
            page.site.info['latest_scan']['time_created'] = str(timezone.now())
            page.site.info['latest_scan']['time_completed'] = None
            page.site.save()

            # init scan in bg
            create_scan.delay(
                page_id=str(page.id),
                type=type,
                configs=configs,
                tags=tags,
                automation_id=automation_id
            )
    
    # update schedule if task_id is not None
    if task_id:
        try:
            last_run = timezone.now()
            Schedule.objects.filter(periodic_task_id=task_id).update(
                time_last_run=last_run
            )
        except Exception as e:
            print(e)
    
    logger.info('created new Scans')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def run_html_and_logs_bg(self, scan_id: str=None, test_id: str=None, automation_id: str=None) -> None:
    """ 
    Runs the html & logs components of the passed `Scan`

    Expects: {
        scan_id         : str, 
        test_id         : str, 
        automation_id   : str
    }
    
    Returns -> None
    """
    
    # run html and logs component
    _html_and_logs(scan_id, test_id, automation_id)

    logger.info('ran html & logs component')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def run_vrt_bg(self, scan_id: str=None, test_id: str=None, automation_id: str=None) -> None:
    """ 
    Runs the VRT component of the passed `Scan`

    Expects: {
        scan_id         : str, 
        test_id         : str, 
        automation_id   : str
    }
    
    Returns -> None
    """

    # run VRT component
    _vrt(scan_id, test_id, automation_id)

    logger.info('ran vrt component')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def run_lighthouse_bg(self, scan_id: str=None, test_id: str=None, automation_id: str=None) -> None:
    """ 
    Runs the lighthouse component of the passed `Scan`

    Expects: {
        scan_id         : str, 
        test_id         : str, 
        automation_id   : str
    }
    
    Returns -> None
    """

    # run lighthouse component
    _lighthouse(scan_id, test_id, automation_id)

    logger.info('ran lighthouse component')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def run_yellowlab_bg(self, scan_id: str=None, test_id: str=None, automation_id: str=None) -> None:
    """ 
    Runs the yellowlab component of the passed `Scan`

    Expects: {
        scan_id         : str, 
        test_id         : str, 
        automation_id   : str
    }
    
    Returns -> None
    """

    # run yellowlab component
    _yellowlab(scan_id, test_id, automation_id)

    logger.info('ran yellowlab component')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def run_test(self, test_id: str, automation_id: str=None) -> None:
    """ 
    Helped function to shorted the code base 
    when creating a `Test`.

    Expects: {
        test_id         : str, 
        automation_id   : str
    }
    
    Returns -> None
    """
    # get test 
    test = Test.objects.get(id=test_id)

    # execute test
    test = T(test=test).run_test()
    if automation_id:
        print('running automation from `task.run_test`')
        Automater(automation_id, test.id).run_automation()

    logger.info('Test completed')
    return None




@shared_task(bind=True, base=BaseTaskWithRetry)
def create_test(
        self,
        test_id: str=None,
        page_id: str=None, 
        automation_id: str=None, 
        configs: dict=settings.CONFIGS, 
        type: list=settings.TYPES,
        index: int=None,
        pre_scan: str=None,
        post_scan: str=None,
        tags: list=None,
        threshold: float=settings.TEST_THRESHOLD,
    ) -> None:
    """ 
    Creates a `post_scan` if necessary, waits for completion,
    and runs a `Test`

    Expects: {
        test_id       : str,
        page_id       : str, 
        automation_id : str, 
        configs       : dict, 
        type          : list,
        index         : int,
        pre_scan      : str,
        post_scan     : str,
        tags          : list,
        threshold     : float,
    }
    
    Returns -> None
    """

    # setting defaults
    created_test = None

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
                    configs=configs,
                )

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
        if not check_and_increment_resource(page.account, 'scans'):
            
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

    # check if pre and post scan are complete and start test if True
    if pre_scan.time_completed is not None and post_scan.time_completed is not None:
        run_test.delay(test_id=created_test.id, automation_id=automation_id)
    
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
        automation_id : str
        pre_scan      : str
        post_scan     : str
        threshold     : float
        task_id       : str
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
    automation_id = kwargs.get('automation_id')
    pre_scan = kwargs.get('pre_scan')
    post_scan = kwargs.get('post_scan')
    task_id = kwargs.get('task_id')

    # create test if none was passed
    if test_id is None:
        
        # setting defaults
        pages = []
        sites = []

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
            # check resource 
            if check_and_increment_resource(page.account, 'tests'):

                # updating latest_test info for page
                page.info['latest_test']['id'] = 'placeholder'
                page.info['latest_test']['time_created'] = str(timezone.now())
                page.info['latest_test']['time_completed'] = None
                page.info['latest_test']['score'] = None
                page.info['latest_test']['status'] = 'working'
                page.save()

                # updating latest_test info for site
                page.site.info['latest_test']['id'] = 'placeholder'
                page.site.info['latest_test']['time_created'] = str(timezone.now())
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
                    automation_id=automation_id
                )
    
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
            automation_id=str(automation_id)
        )

    # update schedule if task_id is not None
    if task_id:
        try:
            last_run = timezone.now()
            Schedule.objects.filter(periodic_task_id=task_id).update(
                time_last_run=last_run
            )
        except Exception as e:
            print(e)

    logger.info('Created new Tests')
    return None




@shared_task
def create_report(page_id: str=None, automation_id: str=None) -> None:
    """ 
    Generates a new PDF `Report` of the requested `Page`
    and runs the associated `Automation` if requested

    Expcets: {
        page_id       : str, 
        automation_id : str
    }
    
    Returns -> None
    """
    
    # get page
    page = Page.objects.get(id=page_id)
    
    # check if report exists
    if Report.objects.filter(page=page).exists():
        report = Report.objects.filter(page=page).order_by('-time_created')[0]
    
    # create new report obj
    else:
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
    R(report=report).generate_report()
    if automation_id:
        Automater(automation_id, str(report.id)).run_automation()
    
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
        'automation_id' : str
        'task_id'       : str
    }
     
    Returns -> None
    """

    # get data
    scope = kwargs.get('scope')
    resources = kwargs.get('resources', [])
    account_id = kwargs.get('account_id')
    automation_id = kwargs.get('automation_id')
    task_id = kwargs.get('task_id')

    # setting defaults
    pages = []
    sites = []

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

    # create reports for each page
    for page in pages:
        create_report.delay(
            page_id=page.id,
            automation_id=automation_id
        )
    
    # update schedule if task_id is not None
    if task_id:
        try:
            last_run = timezone.now()
            Schedule.objects.filter(periodic_task_id=task_id).update(
                time_last_run=last_run
            )
        except Exception as e:
            print(e)
    
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

    # get objects
    site = Site.objects.get(id=site_id)
    process = Process.objects.get(id=process_id)

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
    Runs

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
def run_testcase(
        testcase_id: str=None, 
        automation_id: str=None,
    ) -> None:
    """
    Runs a Testcase.

    Expects: {
        testcase_id   : str, 
        automation_id : str,
    }
    
    Returns -> None
    """
    
    # get testcase
    testcase = Testcase.objects.get(id=testcase_id)

    # running testcase
    testresult = Caser(testcase=testcase).run()

    # run automation if requested
    if automation_id:
        Automater(automation_id, str(testcase.id)).run_automation()

    logger.info('Ran Testcase')
    return None




@shared_task
def create_testcase_bg(*args, **kwargs) -> None:
    """ 
    Creates and or runs a Testcase.

    Expects: {
        testcase_id   : str, 
        resources     : list, 
        scope         : str, 
        account_id    : str, 
        case_id       : str, 
        updates       : list, 
        automation_id : str,
        configs       : dict,
        task_id       : str
    }
    
    Returns -> None
    """

    # get data
    testcase_id = kwargs.get('testcase_id')
    case_id = kwargs.get('case_id')
    account_id = kwargs.get('account_id')
    resources = kwargs.get('resources', [])
    scope = kwargs.get('scope')
    updates = kwargs.get('updates')
    automation_id = kwargs.get('automation_id')
    task_id = kwargs.get('task_id')
    configs = kwargs.get('configs', settings.CONFIGS)

    # settign defaults 
    case = None
    steps = None
    testcases = []
    sites = []

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

    # getting testcase
    if testcase_id:
        testcases = [Testcase.objects.get(id=testcase_id),]
    
    # creating testcase from case
    if testcase_id is None:
        
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
            if check_and_increment_resource(site.account, 'testcases'):
    
                # create new testcase
                _testcase = Testcase.objects.create(
                    case = case,
                    case_name = case.name,
                    site = site,
                    user = site.user,
                    account = site.account,
                    configs = configs,
                    steps = steps
                )

                # add to list
                testcases.append(
                    _testcase
                )

    # iterate through testcases and run
    for testcase in testcases:
        run_testcase.delay(
            testcase_id=str(testcase.id),
            automation_id=automation_id
        )
    
    # update schedule if task_id is not None
    if task_id:
        try:
            last_run = timezone.now()
            Schedule.objects.filter(periodic_task_id=task_id).update(
                time_last_run=last_run
            )
        except Exception as e:
            print(e)

    logger.info('Created Testcases')
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
def delete_testcase_s3_bg(testcase_id: str) -> None:
    """
    Deletes the directory in s3 bucked associated 
    with passed test

    Expects: {
        'testcase_id': str,
    }

    Returns -> None
    """

    # deleting s3 objects
    try:
        bucket = s3().Bucket(settings.AWS_STORAGE_BUCKET_NAME)
        bucket.objects.filter(Prefix=str(f'static/testcase/{testcase_id}/')).delete()
    except:
        pass

    logger.info('Deleted testcase s3 objects')
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

    Expcets: {
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

    # reset account.ussage
    def reset_usage(account):
        account.usage['scans'] = 0
        account.usage['tests'] = 0
        account.usage['testcases'] = 0
        account.save()

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
            if today == sub_date or account_id is not None:

                # reset usage
                reset_usage(account)

                # update account.meta.last_usage_reset
                account.meta = {'last_usage_reset': today.strftime(f)}
                account.save()

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

                    # update account.meta.last_usage_reset
                    account.meta = {'last_usage_reset': today.strftime(f)}
                    account.save()
            
    return None




@shared_task
def update_sub_price(account_id: str=None, max_sites: int=None) -> None:
    """ 
    Update price for existing stripe Subscription 
    based on new `Account.max_sites`

    Expects: {
        'account_id'   : <str> (REQUIRED)   
        'max_sites' : <int> (OPTIONAL)   
    }

    Returns: None
    """

    # init Stripe client
    stripe.api_key = settings.STRIPE_PRIVATE

    # get account
    account = Account.objects.get(id=account_id)

    # set new max_sites
    if max_sites is not None:
        account.max_sites = max_sites
        account.save()
    
    # get max_sites
    if max_sites is None:
        max_sites = account.max_sites

    # get account coupon
    discount = 0
    if account.meta.get('coupon'):
        discount = account.meta['coupon']['discount']

    # calculate 
    if max_sites <= 5:
        price = 8900
    elif max_sites > 5 and max_sites <= 10:
        price = 17900
    elif max_sites > 10 and max_sites <= 25:
        price = 34900
    elif max_sites > 25:
        price = (
            ( 
                (-0.0003 * (max_sites ** 2)) + 
                (1.5142 * max_sites) + 325.2
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
    account.price_amount = 0
    account.price_amount = price_amount
    account.usage['scans_allowed'] = (max_sites * 200)
    account.usage['tests_allowed'] = (max_sites * 200)
    account.usage['testcases_allowed'] = (max_sites * 100)
    account.save()

    print(f'new price -> {price_amount}')
    
    # return 
    return None




@shared_task
def delete_old_resources(account_id: str=None, days_to_live: int=30) -> None:
    """ 
    Deletes all `Tests`, `Scans`, `Testcases`, 
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
        testcases = Testcase.objects.filter(account__id=account_id, time_created__lte=max_date)
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
        testcases = Testcase.objects.filter(time_created__lte=max_date)
        processes = Process.objects.filter(time_created__lte=max_proc_date)
        logs = Log.objects.filter(time_created__lte=max_proc_date)

    # delete each resource in each type
    for test in tests:
        delete_test_s3_bg.delay(test.id, test.site.id, test.page.id)
        test.delete()
    for scan in scans:
        delete_scan_s3_bg.delay(scan.id, scan.site.id, scan.page.id)
        scan.delete()
    for testcase in testcases:
        delete_testcase_s3_bg.delay(testcase.id)
        testcase.delete()
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
            days_to_live=account.retention_days
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

    # get user by id
    user = User.objects.get(email=user_email)

    # get account by user
    account = Account.objects.get(user=user)
    
    # setup configs
    url = f'{settings.LANDING_API_ROOT}/ops/prospect'
    headers = {
        "content-type": "application/json",
        "Authorization" : f'Token {settings.LANDING_API_KEY}'
    }
    data = {
        'first_name': str(user.first_name),
        'last_name': str(user.last_name),
        'email': str(user.email),
        'phone': str(account.phone),
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



