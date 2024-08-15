from datetime import datetime
from django.contrib.auth.models import User
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from django.db.models import Q
from ...models import *
from rest_framework.response import Response
from rest_framework import status
from scanerr import celery
from redis import Redis
from scanerr import settings
from celery import app
from .serializers import *
from ...tasks import *
from rest_framework.pagination import LimitOffsetPagination
from ...utils.scanner import Scanner as S
from ...utils.tester import Tester as T
from ...utils.imager import Imager as I
from ...utils.reporter import Reporter as R
from ...utils.wordpress import Wordpress as W
from ...utils.caser import Caser
from ...utils.crawler import Crawler
import json, boto3, asyncio, os, requests






def record_api_call(request: object, data: dict, status: str) -> None:
    """ 
    Records an request and resposne if 
    the request was sent with Token auth. 
    Creates a `Log` with the recorded info

    Expects: {
        request : object, 
        data    : dict, 
        status  : str
    }
    
    Returns -> None
    """
    
    # get auth type
    auth = request.headers.get('Authorization')

    # check if Token auth
    if auth.startswith('Token'):

        # getting the request data
        if request.method == 'POST':
            request_data = request.data
        elif request.method == 'GET':
            request_data = request.query_params
        elif request.method == 'DELETE':
            request_data = request.query_params

        # recording info 
        log = Log.objects.create(
            user=request.user,
            path=request.path,
            status=status,
            request_type=request.method,
            request_payload=request_data,
            response_payload=data
        )

    return None




def check_account_and_resource(
        request: object=None, 
        user: object=None, 
        resource: str=None, 
        action: str='get',
        **kwargs
    ) -> dict:
    """ 
    Based on the passed "resource" & kwargs, checks to see 
    if account is allowed to add/get a "resource". 
    Also increments the `Account.usage` for the specified resource.

    Expects: {
        'request'   : object, 
        'user'      : object, 
        'resource'  : str, 
        **kwargs    : dict
    }
    
    Returns -> data: {
        'allowed'   : bool,
        'error'     : str,
        'status'    : object 
        'code'      : str
    }
    """
    
    # setting defaults
    allowed = True
    error = None
    member = None
    _status = status.HTTP_402_PAYMENT_REQUIRED
    code = '402'

    # checking for kwargs
    site_id = kwargs.get('site_id')
    site_url = kwargs.get('site_url')
    page_id = kwargs.get('page_id')
    page_url = kwargs.get('page_url')
    test_id = kwargs.get('test_id')
    scan_id = kwargs.get('scan_id')
    case_id = kwargs.get('case_id')
    testcase_id = kwargs.get('testcase_id')
    issue_id = kwargs.get('issue_id')
    schedule_id = kwargs.get('schedule_id')
    automation_id = kwargs.get('automation_id')
    process_id = kwargs.get('process_id')
    report_id = kwargs.get('report_id')

    # retrieving account
    if request is not None:
        user = request.user
    if Member.objects.filter(user=user).exists():
        member = Member.objects.get(user=user)
        account = member.account
        allowed = member.account.active
        if not allowed:
            error = 'account not funded'
    else:
        allowed = False
        error = 'no account assocation'
        _status = status.HTTP_401_UNAUTHORIZED
        code = '401'
    
    # returning early bc account 
    # is not funded or not associated
    if not allowed:
        data = {
            'allowed': allowed,
            'error': error, 
            'status': _status,
            'code': code
        }
        return data

    # checking resource limit
    if resource is not None:
        
        # checking pages
        if resource == 'page':
            if not page_id:
                if site_id:
                    if not Site.objects.filter(id=site_id, account=account).exists():
                        allowed = False
                        error = 'site not found'
                        _status = status.HTTP_404_NOT_FOUND
                        code = '404'
                    else:
                        current_count = Page.objects.filter(account=account, site__id=site_id).count()
                        if current_count >= account.max_pages and action == 'add':
                            allowed = False
                            error = 'max pages reached'
                            _status = status.HTTP_402_PAYMENT_REQUIRED
                            code = '402'
            if page_id:
                if not Page.objects.filter(id=page_id, account=account).exists():
                    allowed = False
                    error = 'page not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
            if page_url:
                if Page.objects.filter(page_url=page_url, account=account).exists():
                    allowed = False
                    error = 'page already exists'
                    _status = status.HTTP_409_CONFLICT
                    code = '409'
        
        # checking sites
        if resource == 'site':
            if site_id:
                if not Site.objects.filter(id=site_id, account=account).exists():
                    allowed = False
                    error = 'site not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
            if site_url:
                current_count = Site.objects.filter(account=account).count()
                if Site.objects.filter(site_url=site_url, account=account).exists():
                    allowed = False
                    error = 'site already exists'
                    _status = status.HTTP_409_CONFLICT
                    code = '409'
                elif current_count >= account.max_sites and action == 'add' and (account.type != 'custom' and account.type != 'enterprise'):
                    allowed = False
                    error = 'max sites reached'
                    _status = status.HTTP_402_PAYMENT_REQUIRED
                    code = '402'
                elif current_count >= account.max_sites  and action == 'add' and (account.type == 'enterprise' or account.type == 'custom'):
                    # add to max_sites only for enterprise
                    account.max_sites += 1
                    account.max_schedules += 1
                    account.save()
                    # update price for sub
                    update_sub_price.delay(account.id)
        
        # checking schedules
        if resource == 'schedule':
            if not schedule_id:
                current_count = Schedule.objects.filter(account=account).count()
                if current_count >= account.max_schedules and action == 'add':
                    allowed = False
                    error = 'max schedules reached'
                    _status = status.HTTP_402_PAYMENT_REQUIRED
                    code = '402'
                elif page_id:
                    if not Page.objects.filter(id=page_id, account=account).exists():
                        allowed = False
                        error = 'page not found'
                        _status = status.HTTP_404_NOT_FOUND
                        code = '404'
                elif site_id:
                    if not Site.objects.filter(id=site_id, account=account).exists():
                        allowed = False
                        error = 'site not found'
                        _status = status.HTTP_404_NOT_FOUND
                        code = '404'
                
            if schedule_id:
                if not Schedule.objects.filter(id=schedule_id, account=account).exists():
                    allowed = False
                    error = 'schedule not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
                if page_id:
                    if not Page.objects.filter(id=page_id, account=account).exists():
                        allowed = False
                        error = 'page not found'
                        _status = status.HTTP_404_NOT_FOUND
                        code = '404'
                if site_id:
                    if not Site.objects.filter(id=site_id, account=account).exists():
                        allowed = False
                        error = 'site not found'
                        _status = status.HTTP_404_NOT_FOUND
                        code = '404'
        
        # checking automations
        if resource == 'automation':
            if automation_id:
                if not Automation.objects.filter(id=automation_id, account=account).exists():
                    allowed = False
                    error = 'automation not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
        
        # checking testcases
        if resource == 'testcase':
            if not testcase_id and action == 'add':
                if not check_resource(account, 'testcases'):
                    allowed = False
                    error = 'max testcases reached'
                    _status = status.HTTP_402_PAYMENT_REQUIRED
                    code = '402'
            if testcase_id:
                if not Testcase.objects.filter(id=testcase_id, account=account).exists():
                    allowed = False
                    error = 'testcase not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
            if case_id:
                if not Case.objects.filter(id=case_id, account=account).exists():
                    allowed = False
                    error = 'case not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
            if site_id:
                if not Site.objects.filter(id=site_id, account=account).exists():
                    allowed = False
                    error = 'site not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
            
        # checking cases
        if resource == 'case':
            if case_id:
                if not Case.objects.filter(id=case_id, account=account).exists():
                    allowed = False
                    error = 'case not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
            if site_id:
                if not Site.objects.filter(id=site_id, account=account).exists():
                    allowed = False
                    error = 'site not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
        
        # checking issues
        if resource == 'issue':
            if issue_id:
                if not Issue.objects.filter(id=issue_id, account=account).exists():
                    allowed = False
                    error = 'issue not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
            if site_id:
                if not Site.objects.filter(id=site_id, account=account).exists():
                    allowed = False
                    error = 'site not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
            if page_id:
                if not Page.objects.filter(id=page_id, account=account).exists():
                    allowed = False
                    error = 'page not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
        
        # checking scans
        if resource == 'scan':
            if not scan_id and action == 'add':
                if not check_resource(account, 'scans'):
                    allowed = False
                    error = 'max scans reached'
                    _status = status.HTTP_402_PAYMENT_REQUIRED
                    code = '402'
            if scan_id:
                if not Scan.objects.filter(id=scan_id, page__account=account).exists():
                    allowed = False
                    error = 'scan not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
        
        # checking tests
        if resource == 'test':
            if not test_id and action == 'add':
                if not check_resource(account, 'tests'):
                    allowed = False
                    error = 'max tests reached'
                    _status = status.HTTP_402_PAYMENT_REQUIRED
                    code = '402'
            if test_id:
                if not Test.objects.filter(id=test_id, page__account=account).exists():
                    allowed = False
                    error = 'test not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'

        # checking process
        if resource == 'process':
            if process_id:
                if not Process.objects.filter(id=process_id, account=account).exists():
                    allowed = False
                    error = 'process not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
        
        # checking reports
        if resource == 'report':
            if report_id:
                if not Report.objects.filter(id=report_id, account=account).exists():
                    allowed = False
                    error = 'report not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
            if page_id:
                if not Page.objects.filter(id=page_id, account=account).exists():
                    allowed = False
                    error = 'page not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
        
        # checking logs
        if resource == 'log':
            if log_id:
                if not Log.objects.filter(id=log_id, account=account).exists():
                    allowed = False
                    error = 'log not found'
                    _status = status.HTTP_404_NOT_FOUND
                    code = '404'
            
    # returning data
    data = {
        'allowed': allowed,
        'error': error, 
        'status': _status,
        'code': code
    }
    return data




def check_resource(account: object, resource: str) -> bool:
    """ 
    Validates if account can add a new {resource} 

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
        # update success
        success = True

    # return response
    return success



    
### ------ Begin Site Services ------ ###




def create_site(request: object, delay: bool=False) -> object:
    """ 
    Creates a new `Site`, initiates a Crawl, initial `Scans` 
    for each added `Page`, and generates new `Cases`. 

    Expects: {
        request : object, 
        delay   : bool
    }

    Returns -> HTTP Response object
    """

    # getting data
    site_url = request.data.get('site_url')
    page_urls = request.data.get('page_urls')
    onboarding = request.data.get('onboarding', None)
    tags = request.data.get('tags', None)
    configs = request.data.get('configs', None)
    no_scan = request.data.get('no_scan', False)
    
    # gettting account
    user = request.user
    account = Member.objects.get(user=user).account
    sites = Site.objects.filter(account=account)

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # checking if in onboarding flow
    if onboarding is not None:
        if str(onboarding).lower() == 'true':
            onboarding = True
        if str(onboarding).lower() == 'false':
            onboarding = False

    # clean & check site url
    if site_url.endswith('/'):
        site_url = site_url.rstrip('/')
    if site_url is None or site_url == '':
        data = {'reason': 'the site_url cannot be empty',}
        record_api_call(request, data, '400')
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

    # check account and resource
    check_data = check_account_and_resource(
        request=request, resource='site', action='add',
        site_url=site_url
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # creating site if checks passed
    site = Site.objects.create(
        site_url=site_url,
        user=user,
        tags=tags,
        account=account,
        time_crawl_started=datetime.now()
    )

    # create process obj
    process = Process.objects.create(
        site=site,
        type='case',
        account=account,
        progress=1
    )

    # auto gen Cases using bg_autocase_task
    create_auto_cases_bg.delay(
        site_id=site.id,
        process_id=process.id,
        start_url=str(site.site_url),
        configs=configs,
        max_cases=3,
        max_layers=8
    )
    
    # check if this is account's first site and onboarding = True
    if Site.objects.filter(account=account).count() == 1 \
        and onboarding == True:
        # send POST to landing/v1/ops/prospect
        create_prospect.delay(user_email=str(user.email))

    # check if scan requested
    if no_scan == False:

        # adding pages passed in request
        if page_urls is not None:
            for url in page_urls:
                if url.startswith(site.site_url):
                    # add new page
                    page = Page.objects.create(
                        site=site,
                        page_url=url,
                        user=site.user,
                        account=site.account,
                    )
                    # create scan
                    create_scan(
                        page_id=page.id, 
                        configs=configs, 
                        user_id=request.user.id,
                        delay=True
                    )
                    site.time_crawl_started = datetime.now()
                    site.time_crawl_completed = datetime.now()
                    site.info["latest_scan"]["time_created"] = str(datetime.now())
                    site.save()
        
        # starting crawler and scans in background
        else:
            create_site_and_pages_bg.delay(
                site_id=site.id, 
                configs=configs
            )
            
    # serialize response and return
    serializer_context = {'request': request,}
    serialized = SiteSerializer(site, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response




def crawl_site(request: object=None, id: str=None, account: object=None) -> object:
    """ 
    Initiates a new Crawl for the passed `Site`.id

    Expects: {
        'request' : object, 
        'id'      : str,
        'account' ; object
    }
    
    Returns -> HTTP Response object
    """

    # get user and account
    if request:
        user = request.user
        account = Member.objects.get(user=user).account
        configs = request.data.get('configs', None)
    
    if not request:
        user = account.user
        configs = account.configs

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # check account and resource
    check_data = check_account_and_resource(user=user, site_id=id, resource='site')
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # update site info
    site = Site.objects.get(id=id)
    site.time_crawl_completed = None
    site.save()

    # starting crawl
    crawl_site_bg.delay(site_id=site.id, configs=configs)

    # serializing and returning
    if request:
        serializer_context = {'request': request,}
        serialized = SiteSerializer(site, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '201')
        response = Response(data, status=status.HTTP_201_CREATED)
        return response
    return None




def get_sites(request: object) -> object:
    """ 
    Get one or more `Sites` in paginated response

    Expects: {
        'request': object,
    } 

    Returns -> HTTP Response object
    """

    # getting request data
    site_id = request.query_params.get('site_id')
    user = request.user

    # getting account
    account = Member.objects.get(user=user).account

    # check if site_id was passed
    if site_id != None:

        # check account and resource
        check_data = check_account_and_resource(request=request, site_id=site_id, resource='site')
        if not check_data['allowed']:
            data = {'reason': check_data['error'],}
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        
        # get site if checks passed
        site = Site.objects.get(id=site_id)

        # serialize single site response and return
        serializer_context = {'request': request,}
        serialized = SiteSerializer(site, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)
    
    # getting all account assoicated sites
    sites = Site.objects.filter(account=account).order_by('-time_created')

    # serialize response and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(sites, request)
    serializer_context = {'request': request,}
    serialized = SiteSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_site(request: object, id: str) -> object:
    """
    Get single `Site` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, 
        site_id=id, resource='site'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get site if checks passed
    site = Site.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = SiteSerializer(site, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK) 




def delete_site(request: object=None, id: str=None, account: object=None) -> object:
    """ 
    Deletes the `Site` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str,
        'account' : object,
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    if request:
        account = Member.objects.get(user=request.user).account
        user = request.user
    
    if not request:
        user = account.user

    # check account and resource
    check_data = check_account_and_resource(user=user, site_id=id, resource='site')
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data
    
    # get site if checks passed
    site = Site.objects.get(id=id)

    # remove s3 objects
    delete_site_s3_bg.delay(site_id=id)
    
    # remove any associated tasks 
    delete_tasks(site=site)

    # remove any associated Issues
    issues = Issue.objects.filter(affected__icontains=id).delete()
    
    # remove site
    site.delete()

    # update account if enterprise or custom
    if account.type == 'enterprise' or account.type == 'custom':
        account.max_sites -= 1
        account.max_schedules -= 1
        account.save()

        # update billing
        update_sub_price.delay(account_id=account.id)

    # returning response
    data = {'message': 'site deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data




def delete_many_sites(request: object) -> object:
    """ 
    Deletes one or more `Sites` associated
    with the passed "request.ids" 

    Expcets: {
        'request' : object,
    }

    Returns -> HTTP Response object
    """

    # get request data
    ids = request.data.get('ids')

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check for ids
    if ids is not None:

        # setting defaults
        count = len(ids)
        num_succeeded = 0
        succeeded = []
        num_failed = 0
        failed = []
        user = request.user
        this_status = True

        # loop through passed ids
        for id in ids:

            # trying to delete site
            try:
                site = Site.objects.get(id=id)
                if site.account == account:

                    # delete site and associated resources
                    delete_site_s3_bg.delay(site_id=id)
                    delete_tasks(site=site)
                    Issue.objects.filter(affected__icontains=id).delete()

                # add to success attempts
                num_succeeded += 1
                succeeded.append(str(id))

            except:
                # add to failed attempts
                num_failed += 1
                failed.append(str(id))
                this_status = False

        
        # update account if enterprise or custom
        if account.type == 'enterprise' or account.type == 'custom':
            account.max_sites -= num_succeeded
            account.max_schedules -= num_succeeded
            account.save()

            # update billing
            update_sub_price.delay(account_id=account.id)

        # format response
        data = {
            'success': this_status,
            'num_succeeded': num_succeeded,
            'succeeded': succeeded,
            'num_failed': num_failed,
            'failed': failed, 
        }

        # returning response
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    
    # returning error
    data = {
        'reason': 'you must provide an array of id\'s'
    }
    record_api_call(request, data, '400')
    response = Response(data, status=status.HTTP_400_BAD_REQUEST)
    return response




def get_sites_zapier(request: object) -> object:
    """ 
    Get all `Sites` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    account = Member.objects.get(user=request.user).account
    sites = None
    
    # deciding on scope
    resource = 'site'

    # check account and resource 
    check_data = check_account_and_resource(
        user=request.user, resource=resource,
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get all account assocoiated sites
    if sites is None:
        sites = Site.objects.filter(
            account=account,
        ).order_by('-time_created')

    # build response data
    data = []

    for site in sites:
        data.append({
            'id'               :  str(site.id),
            'site_url'         :  str(site.site_url),
            'time_created'     :  str(site.time_created),
            'tags'             :  site.tags,
            'info'             :  site.info,
        })

    # serialize and return
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Page Services ------ ###




def create_page(request: object, delay: bool=False) -> object:
    """ 
    Creates one or more pages.

    Expcets: {
        'requests': object
    }
    
    Returns -> HTTP Response object
    """

    # getting request data
    site_id = request.data.get('site_id')
    page_url = request.data.get('page_url')
    page_urls = request.data.get('page_urls')
    tags = request.data.get('tags', None)
    configs = request.data.get('configs', None)
    no_scan = request.data.get('no_scan', False)

    # retrieving user, account, & site
    user = request.user
    account = Member.objects.get(user=user).account
    site = Site.objects.get(id=site_id)

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # creating many pages if page_urls was passed
    if page_urls is not None:
        print('trying to add many pages')
        data = create_many_pages(request=request, http_response=False)
        _status = status.HTTP_201_CREATED
        if data.get('reason') is not None:
            _status = status.HTTP_402_PAYMENT_REQUIRED
        response = Response(data, status=_status)
        return response
    
    # validating page_url
    if page_url.endswith('/'):
        page_url = page_url.rstrip('/')
    if page_url is None or page_url == '':
        data = {'reason': 'the page_url cannot be empty',}
        record_api_call(request, data, '400')
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

    # check account and resource
    check_data = check_account_and_resource(
        request=request, resource='page', site_id=site_id, page_url=page_url,
        action='add'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # adding page if checks passed
    page = Page.objects.create(
        site=site,
        page_url=page_url,
        user=user,
        tags=tags,
        account=account
    )

    # deciding on scan
    if no_scan == False:

        # create initial scan
        scan = Scan.objects.create(
            site=site,
            page=page, 
            type=settings.TYPES,
            configs=configs
        )
        page.info["latest_scan"]["id"] = str(scan.id)
        page.info["latest_scan"]["time_created"] = str(scan.time_created)
        page.save()

        # running scan in background
        scan_page_bg.delay(scan_id=scan.id, configs=configs)

            
    # serialize response and return
    serializer_context = {'request': request,}
    serialized = PageSerializer(page, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response




def create_many_pages(request: object, http_response: bool=True) -> object:
    """ 
    Bulk creates `Pages` for each url passed in "page_urls"

    Expcets: {
        'request'       : object,
        'http_response'  : bool
    }

    Returns -> dict or HTTP Response object
    """

    # get request data
    site_id = request.data.get('site_id')
    page_urls = request.data.get('page_urls')
    tags = request.data.get('tags', None)
    configs = request.data.get('configs', None)
    no_scan = request.data.get('no_scan', False)
    
    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # get site and current pages
    site = Site.objects.get(id=site_id)
    pages = Page.objects.filter(site=site)

    # check account and resource
    check_data = check_account_and_resource(
        request=request, resource='page', site_id=site_id, action='add'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        if http_response:
            return Response(data, status=check_data['status'])
        return data

    # pre check for max_pages
    if (pages.count() + len(page_urls)) > account.max_pages:
        print('max pages aparently')
        data = {'reason': 'maximum number of pages reached',}
        record_api_call(request, data, '402')
        if http_response:
            return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)
        return data
    
    # setting defaults
    count = len(page_urls)
    num_succeeded = 0
    succeeded = []
    num_failed = 0
    failed = []
    this_status = True

    # looping through each "page_url"
    for url in page_urls:

        # clean url
        if url.endswith('/'):
            url = url.rstrip('/')

        # check for duplicates
        if not Page.objects.filter(page_url=url, user=user).exists():
            
            # adding pages
            page = Page.objects.create(
                site=site,
                page_url=url,
                user=user,
                tags=tags,
                account=account
            )

            # deciding on scan
            if no_scan == False:

                # create initial scan
                scan = Scan.objects.create(
                    site=site,
                    page=page, 
                    type=settings.TYPES,
                    configs=configs
                )
                
                # update page with new scan data
                page.info["latest_scan"]["id"] = str(scan.id)
                page.info["latest_scan"]["time_created"] = str(scan.time_created)
                page.save()
                
                # run scanner
                scan_page_bg.delay(scan_id=scan.id, configs=configs)

                # update info
                succeeded.append(url)
                num_succeeded = num_succeeded + 1

        else:
            # update info
            this_status = False
            failed.append(url)
            num_failed = num_failed + 1

    # formatting response
    data = {
        'success': this_status,
        'num_succeeded': num_succeeded,
        'succeeded': succeeded,
        'num_failed': num_failed,
        'failed': failed, 
    }

    # record successful API call
    record_api_call(request, data, '201')

    # decide on response type
    if http_response:
        print('requested http response')
        # returning HTTP Response
        response = Response(data, status=status.HTTP_201_CREATED)
        return response
    
    # return dict response
    print('requested data response')
    return data

    
    

def get_pages(request: object) -> object:
    """ 
    Get one or more `Pages` from either 
    "page_id" or "site_id"

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    site_id = request.query_params.get('site_id')
    page_id = request.query_params.get('page_id')

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check for params
    if page_id is None and site_id is None:
        data = {'reason': 'must provide a Site or Page id'}
        record_api_call(request, data, '400')
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

    # check account and resource
    check_data = check_account_and_resource(
        request=request, resource='page', site_id=site_id, page_id=page_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])
    
    # getting single page
    if page_id != None:
        
        # get page
        page = Page.objects.get(id=page_id)

        # serialize and return
        serializer_context = {'request': request,}
        serialized = PageSerializer(page, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    # get site and assocaited pages
    site = Site.objects.get(id=site_id)
    pages = Page.objects.filter(site=site).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(pages, request)
    serializer_context = {'request': request,}
    serialized = PageSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_page(request: object, id: str) -> object:
    """
    Get single `Page` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, 
        page_id=id, resource='page'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get page if checks passed
    page = Page.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = PageSerializer(page, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK) 




def delete_page(request: object=None, id: str=None, account: object=None) -> object:
    """ 
    Deletes the `Page` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str
    }

    Returns -> HTTP Response object
    """
    
    # get user and account info
    if request:
        account = Member.objects.get(user=request.user).account
        user = request.user
    
    if not request:
        user = account.user

    # check account and resource
    check_data = check_account_and_resource(user=user, page_id=id, resource='page')
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # get page by id
    page = Page.objects.get(id=id)

    # remove s3 objects
    delete_page_s3_bg.delay(page_id=id, site_id=page.site.id)

    # remove any schedules and associated tasks
    delete_tasks(page=page)

    # remove any associated Issues
    issues = Issue.objects.filter(
        affected__icontains=id
    )
    for issue in issues:
        issue.delete()
    
    # remove page
    page.delete()

    # format and return
    data = {'message': 'Page has been deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data




def delete_many_pages(request: object) -> object:
    """ 
    Deletes one or more `Pages` associated
    with the passed "request.ids" 

    Expcets: {
        'request' : object,
    }

    Returns -> HTTP Response object
    """

    # get request data
    ids = request.data.get('ids')

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check for ids
    if ids is not None:

        # setting defaults
        count = len(ids)
        num_succeeded = 0
        succeeded = []
        num_failed = 0
        failed = []
        user = request.user
        this_status = True

        # loop through passed ids
        for id in ids:

            # trying to delete site
            try:
                page = Page.objects.get(id=id)
                if page.account == account:
                    delete_page_s3_bg.delay(page_id=id, site_id=page.site.id)
                    delete_tasks(page=page)
                    page.delete()
                # add to success attempts
                num_succeeded += 1
                succeeded.append(str(id))
            except:
                # add to failed attempts
                num_failed += 1
                failed.append(str(id))
                this_status = False

        # format data
        data = {
            'success': this_status,
            'num_succeeded': num_succeeded,
            'succeeded': succeeded,
            'num_failed': num_failed,
            'failed': failed, 
        }
        
        # returning response
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    
    # returning error
    data = {
        'reason': 'you must provide an array of id\'s'
    }
    record_api_call(request, data, '400')
    response = Response(data, status=status.HTTP_400_BAD_REQUEST)
    return response




def get_pages_zapier(request: object) -> object:
    """ 
    Get all `Pages` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    account = Member.objects.get(user=request.user).account
    site_id = request.query_params.get('site_id')
    pages = None
    
    # deciding on scope
    resource = 'page'

    # check account and resource 
    check_data = check_account_and_resource(
        user=request.user, resource=resource, site_id=site_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get all site associated pages
    if site_id:
        pages = Page.objects.filter(
            account=account,
            site__id=site_id,
        ).order_by('-time_created')

    # get all account assocoiated pages
    if pages is None:
        pages = Page.objects.filter(
            account=account,
        ).order_by('-time_created')

    # build response data
    data = []

    for page in pages:
        data.append({
            'id'               :  str(page.id),
            'page_url'         :  str(page.page_url),
            'site'             :  str(page.site.id),
            'site_url'         :  str(page.site.site_url),
            'time_created'     :  str(page.time_created),
            'tags'             :  page.tags,
            'info'             :  page.info,
        })

    # serialize and return
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Scan Services ------ ###




def create_scan(request: object=None, delay: bool=False, **kwargs) -> object:
    """ 
    Create one or more `Scans` depanding on 
    `Page` or `Site` scope

    Expects: {
        'request': object, 
        'delay': bool
    }

    Returns -> dict or HTTP Response object
    """

    # get request data
    if request is not None:
        site_id = request.data.get('site_id', '')
        page_id = request.data.get('page_id', '')
        configs = request.data.get('configs', None)
        types = request.data.get('type', settings.TYPES)
        tags = request.data.get('tags')
        user = request.user
    
    # getting kwargs data
    if request is None:
        site_id = kwargs.get('site_id', '')
        page_id = kwargs.get('page_id', '')
        configs = kwargs.get('configs', None)
        types = kwargs.get('type', settings.TYPES)
        tags = kwargs.get('tags')
        user_id = kwargs.get('user_id')
        user = User.objects.get(id=user_id)
    
    # getting account
    account = Member.objects.get(user=user).account

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # checking args
    site_id = '' if site_id is None else site_id
    page_id = '' if page_id is None else page_id
    site_id = site_id if len(str(site_id)) > 0 else None
    page_id = page_id if len(str(page_id)) > 0 else None

    # verifying types
    if len(types) == 0:
        types = settings.TYPES

    # deciding on scope
    resource = 'site' if site_id else 'page'

    # check account and resource for site or page
    check_data = check_account_and_resource(
        user=user, resource=resource, page_id=page_id, site_id=site_id
    )
    if not check_data['allowed']:
        data = {
            'reason': check_data['error'], 
            'success': False, 
            'code': check_data['code'], 
            'status': check_data['status']
        }
        if request is not None:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # get site or page
    if site_id is not None:
        site = Site.objects.get(id=site_id)
    if page_id is not None:
        page = Page.objects.get(id=page_id)

    # setting pages to loop through
    if site_id is not None and page_id is None:
        pages = Page.objects.filter(site=site)
    if site_id is None and page_id is not None:
        pages = [page,]

    # setting default
    created_scans = []

    # looping through each page
    for p in pages:

        # check for account usage
        check_data = check_account_and_resource(
            user=user, action='add', resource='scan'
        )
        if not check_data['allowed']:
            data = {
                'reason': check_data['error'], 
                'success': False, 
                'code': check_data['code'], 
                'status': check_data['status']
            }
            if request is not None:
                record_api_call(request, data, check_data['code'])
                return Response(data, status=check_data['status'])
            return data

        # increment account.usage.scans
        account.usage['scans'] += 1
        account.save() 

        # creating scan obj
        created_scan = Scan.objects.create(
            site=p.site,
            page=p,
            tags=tags, 
            type=types,
            configs=configs,
        )

        # adding scan to array
        created_scans.append(str(created_scan.id))
        message = 'Scans are being created in the background'

        # updating latest_scan info for page
        p.info['latest_scan']['id'] = str(created_scan.id)
        p.info['latest_scan']['time_created'] = str(timezone.now())
        p.info['latest_scan']['time_completed'] = None
        p.info['latest_scan']['score'] = None
        p.info['latest_scan']['score'] = None
        p.save()

        # updating latest_scan info for site
        p.site.info['latest_scan']['id'] = str(created_scan.id)
        p.site.info['latest_scan']['time_created'] = str(timezone.now())
        p.site.info['latest_scan']['time_completed'] = None
        p.site.save()

        # running scans components in parallel 
        if 'html' in types or 'logs' in types or 'full' in types:
            run_html_and_logs_bg.delay(scan_id=created_scan.id)
        if 'lighthouse' in types or 'full' in types:
            run_lighthouse_bg.delay(scan_id=created_scan.id)
        if 'yellowlab' in types or 'full' in types:
            run_yellowlab_bg.delay(scan_id=created_scan.id)
        if 'vrt' in types or 'full' in types:
            run_vrt_bg.delay(scan_id=created_scan.id)
    
    # returning dynaminc response
    data = {
        'success': True,
        'message': message,
        'ids': created_scans,
    }
    if request is not None:
        record_api_call(request, data, '201')
        return Response(data, status=status.HTTP_201_CREATED)
    return data




def create_many_scans(request: object) -> object:
    """ 
    Bulk creates `Scans` for each requested `Page`.
    Either scoped for many `Pages` or many `Sites`.

    Expcets: {
        'request' : object,
    }

    Returns -> HTTP Response object
    """

    # get request data
    site_ids = request.data.get('site_ids')
    page_ids = request.data.get('page_ids')
    configs = request.data.get('configs', None)
    types = request.data.get('type', settings.TYPES)
    tags = request.data.get('tags')
    user = request.user
    account = Member.objects.get(user=user).account

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # setting defaults
    num_succeeded = 0
    succeeded = []
    num_failed = 0
    failed = []
    this_status = True

    # scoped for sites
    if site_ids:
        for id in site_ids:
            data = {
                'site_id': str(id), 
                'configs': configs,
                'type': types,
                'tags': tags,
                'user_id': str(user.id)
            }
            try:
                # create scan
                res = create_scan(delay=True, **data)
                if res['success']:
                    num_succeeded += 1
                    succeeded.append(str(id))
                else:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))
                    print(res['message'])
            except Exception as e:
                print(e)
                if str(id) not in failed:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))

    # scoped for pages
    if page_ids:
        for id in page_ids:
            data = {
                'page_id': str(id), 
                'configs': configs,
                'type': types,
                'tags': tags,
                'user_id': str(user.id)
            }
            try:
                # create scan
                res = create_scan(delay=True, **data)
                if res['success']:
                    num_succeeded += 1
                    succeeded.append(str(id))
                else:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))
                    print(res['message'])
            except Exception as e:
                print(e)
                if str(id) not in failed:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))

    # format and return
    data = {
        'success': this_status,
        'num_succeeded': num_succeeded,
        'succeeded': succeeded,
        'num_failed': num_failed,
        'failed': failed, 
    }
    record_api_call(request, data, '201')
    return Response(data, status=status.HTTP_201_CREATED)




def get_scans(request: object) -> object:
    """ 
    Get one or more `Scans`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    scan_id = request.query_params.get('scan_id')
    page_id = request.query_params.get('page_id')
    lean = request.query_params.get('lean')
    user = request.user
    account = Member.objects.get(user=user).account
    
    # deciding on scope
    resource = 'page' if page_id else 'scan'

    # check account and resource 
    check_data = check_account_and_resource(
        user=user, resource=resource, page_id=page_id, scan_id=scan_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get single scan
    if scan_id != None:

        # get scan
        scan = Scan.objects.get(id=scan_id)
        
        # serialize and return
        serializer_context = {'request': request,}
        serialized = ScanSerializer(scan, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    # get page scoped scans
    page = Page.objects.get(id=page_id)
    scans = Scan.objects.filter(page=page).order_by('-time_created')
        
    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(scans, request)
    serializer_context = {'request': request,}
    serialized = ScanSerializer(result_page, many=True, context=serializer_context)
    if str(lean).lower() == 'true':
        serialized = SmallScanSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_scan(request: object, id: str) -> object:
    """
    Get single `Scan` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, 
        scan_id=id, resource='scan'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get scan if checks passed
    scan = Scan.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = ScanSerializer(scan, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def get_scan_lean(request: object, id: str) -> object:
    """ 
    Get a single `Scan` and only return scores & timestamps

    Expects: {
        'request' : object, 
        'id'      : str
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource 
    check_data = check_account_and_resource(
        user=user, resource='scan', scan_id=id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])
    
    # get scan if checks passed
    scan = Scan.objects.get(id=id)

    # get lighthouse scores if exists
    lighthouse = {"scores": scan.lighthouse.get('scores')}
    
    # get yellowlab scores if exists
    yellowlab = {"scores": scan.yellowlab.get('scores')}

    # format data
    data = {
        "id": str(scan.id),
        "site": str(scan.site.id),
        "tags": scan.tags,
        "type": scan.type,
        "time_created": str(scan.time_created),
        "time_completed": str(scan.time_completed),
        "lighthouse": lighthouse,
        "yellowlab": yellowlab,
    }

    # return response
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def delete_scan(request: object=None, id: str=None, account: object=None) -> object:
    """ 
    Deletes the `Scan` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str,
        'account' : object
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    if request:
        account = Member.objects.get(user=request.user).account
        user = request.user
    
    if not request:
        user = account.user

    # check account and resource
    check_data = check_account_and_resource(user=user, scan_id=id, resource='scan')
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data
    
    # get scan if checks passes
    scan = Scan.objects.get(id=id)

    # remove s3 objects
    delete_scan_s3_bg.delay(scan.id, scan.site.id, scan.page.id)

    # delete scan
    scan.delete()

    # return response
    data = {'message': 'Scan has been deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data




def delete_many_scans(request: object) -> object:
    """ 
    Deletes one or more `Scans` associated
    with the passed "request.ids" 

    Expcets: {
        'request' : object,
    }

    Returns -> HTTP Response object
    """

    # get request data
    ids = request.data.get('ids')

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check for ids
    if ids is not None:

        # setting defaults
        count = len(ids)
        num_succeeded = 0
        succeeded = []
        num_failed = 0
        failed = []
        user = request.user
        this_status = True

        # loop through passed ids
        for id in ids:
            
            # trying to delete scan
            try:
                scan = Scan.objects.get(id=id)
                if scan.site.account == account:
                    delete_scan_s3_bg.delay(scan.id, scan.site.id, scan.page.id)
                    scan.delete()
                # add to success attempts
                num_succeeded += 1
                succeeded.append(str(id))
            except Exception as e:
                # add to failed attempts
                num_failed += 1
                failed.append(str(id))
                this_status = False

        # format data
        data = {
            'success': this_status,
            'num_succeeded': num_succeeded,
            'succeeded': succeeded,
            'num_failed': num_failed,
            'failed': failed, 
        }
        
        # returning response
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response

    # return error
    data = {
        'reason': 'you must provide an array of id\'s'
    }
    record_api_call(request, data, '400')
    response = Response(data, status=status.HTTP_400_BAD_REQUEST)
    return response




def get_scans_zapier(request: object) -> object:
    """ 
    Get all `Scans` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    account = Member.objects.get(user=request.user).account
    page_id = request.query_params.get('page_id')
    site_id = request.query_params.get('site_id')
    scans = None
    
    # deciding on scope
    resource = 'scan'

    # check account and resource 
    check_data = check_account_and_resource(
        user=request.user, resource=resource, page_id=page_id, 
        site_id=site_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get all page associated scans
    if page_id:
        scans = Scan.objects.filter(
            page__account=account,
            page__id=page_id,
        ).exclude(
            time_completed=None,
        ).order_by('-time_created')

    # get all site associated scans
    if site_id:
        scans = Scan.objects.filter(
            site__account=account,
            site__id=site_id,
        ).exclude(
            time_completed=None,
        ).order_by('-time_created')

    # get all account assocoiated tests
    if scans is None:
        scans = Scan.objects.filter(
            site__account=account,
        ).exclude(
            time_completed=None,
        ).order_by('-time_created')

    # build response data
    data = []

    for scan in scans:
        data.append({
            'id'               :  str(scan.id),
            'page'             :  str(scan.page.id),
            'site'             :  str(scan.site.id),
            'time_created'     :  str(scan.time_created),
            'time_completed'   :  str(scan.time_completed),
            'type'             :  scan.type,
            'html'             :  scan.html,
            'logs'             :  scan.logs,
            'images'           :  scan.images,
            'lighthouse'       :  scan.lighthouse,
            'yellowlab'        :  scan.yellowlab,
            'configs'          :  scan.configs,
        })

    # serialize and return
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Test Services ------ ###




def create_test(request: object=None, delay: bool=False, **kwargs) -> object:
    """ 
    Create one or more `Tests` depanding on 
    `Page` or `Site` scope

    Expects: {
        'request': object, 
        'delay': bool
    }

    Returns -> dict or HTTP Response object
    """

    # get data from request
    if request is not None:
        configs = request.data.get('configs', None)
        threshold = request.data.get('threshold', settings.TEST_THRESHOLD)
        pre_scan_id = request.data.get('pre_scan')
        post_scan_id = request.data.get('post_scan')
        index = request.data.get('index')
        test_type = request.data.get('type', settings.TYPES)
        tags = request.data.get('tags')
        pre_scan = None
        post_scan = None
        site_id = request.data.get('site_id', '')
        page_id = request.data.get('page_id', '')
        user = request.user

    # get data from kwargs
    if request is None:
        configs = kwargs.get('configs', None)
        threshold = kwargs.get('threshold', settings.TEST_THRESHOLD)
        pre_scan_id = kwargs.get('pre_scan')
        post_scan_id = kwargs.get('post_scan')
        index = kwargs.get('index')
        test_type = kwargs.get('type', settings.TYPES)
        tags = kwargs.get('tags')
        pre_scan = None
        post_scan = None
        site_id = kwargs.get('site_id', '')
        page_id = kwargs.get('page_id', '')
        user_id = kwargs.get('user_id')
        user = User.objects.get(id=user_id)

    # get account
    account = Member.objects.get(user=user).account

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # verifying test_type
    if len(test_type) == 0:
        test_type = settings.TYPES

    # checking args
    site_id = '' if site_id is None else site_id
    page_id = '' if page_id is None else page_id
    site_id = site_id if len(str(site_id)) > 0 else None
    page_id = page_id if len(str(page_id)) > 0 else None

    # deciding on scope
    resource = 'site' if site_id else 'page'

    # check account and resource for page or site
    check_data = check_account_and_resource(
        user=user, resource=resource, page_id=page_id, site_id=site_id
    )
    if not check_data['allowed']:
        data = {
            'reason': check_data['error'], 
            'success': False, 
            'code': check_data['code'], 
            'status': check_data['status']
        }
        if request is not None:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # deciding on scope
    if site_id is not None:
        site = Site.objects.get(id=site_id)    
    if page_id is not None:
        page = Page.objects.get(id=page_id)

    # building pages list
    if site_id is not None and page_id is None:
        pages = Page.objects.filter(site=site)
    if site_id is None and page_id is not None:
        pages = [page]

    # setting default
    created_tests = []

    # looping through pages
    for p in pages:

        # check for account usage
        check_data = check_account_and_resource(
            user=user, action='add', resource='test'
        )
        if not check_data['allowed']:
            data = {
                'reason': check_data['error'], 
                'success': False, 
                'code': check_data['code'], 
                'status': check_data['status']
            }
            if request is not None:
                record_api_call(request, data, check_data['code'])
                return Response(data, status=check_data['status'])
            return data

        # checking for scan completion
        if not Scan.objects.filter(page=p).exists():
            data = {'reason': 'Page not yet onboarded', 'success': False,}
            print(data)
            record_api_call(request, data, '400')
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        
        # verifying pre_ and post_ scans exists
        if pre_scan_id:
            try:
                pre_scan = Scan.objects.get(id=pre_scan_id)
            except:
                data = {'reason': 'cannot find a Scan with that id - pre_scan', 'success': False,}
                print(data)
                if request is not None:
                    record_api_call(request, data, '404')
                    return Response(data, status=status.HTTP_404_NOT_FOUND)
                return data
        if post_scan_id:
            try:
                post_scan = Scan.objects.get(id=post_scan_id)
            except:
                data = {'reason': 'cannot find a Scan with that id - post_scan', 'success': False,}
                print(data)
                if request is not None:
                    record_api_call(request, data, '404')
                    return Response(data, status=status.HTTP_404_NOT_FOUND)
                return data

        # grabbing most recent Scan 
        if pre_scan_id is None:
            pre_scan = Scan.objects.filter(page=p).order_by('-time_created')[0]

        # verifying pre_ and post_ scans completion
        if pre_scan:
            if pre_scan.time_completed == None:
                data = {'reason': 'pre_scan still running', 'success': False,}
                print(data)
                if request is not None:
                    record_api_call(request, data, '400')
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)
                return data
        if post_scan:
            if post_scan.time_completed == None:
                data = {'reason': 'post_scan still running', 'success': False,}
                print(data)
                if request is not None:
                    record_api_call(request, data, '400')
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)
                return data

        # creating test object
        test = Test.objects.create(
            site=p.site,
            page=p,
            type=test_type,
            tags=tags,
            threshold=float(threshold),
            status='working',
        )

        # updating latest_test info for page
        p.info['latest_test']['id'] = str(test.id)
        p.info['latest_test']['time_created'] = str(timezone.now())
        p.info['latest_test']['time_completed'] = None
        p.info['latest_test']['score'] = None
        p.info['latest_test']['status'] = 'working'
        p.save()

        # updating latest_test info for site
        p.site.info['latest_test']['id'] = str(test.id)
        p.site.info['latest_test']['time_created'] = str(timezone.now())
        p.site.info['latest_test']['time_completed'] = None
        p.site.info['latest_test']['score'] = None
        p.site.info['latest_test']['status'] = 'working'
        p.site.save()

        # add test.id to list
        created_tests.append(str(test.id))

        # update account.usage.tests
        account.usage['tests'] += 1
        account.save()

        # running test in background
        create_test_bg.delay(
            page_id=p.id,
            test_id=test.id,
            configs=configs,
            type=test_type,
            index=index,
            pre_scan=pre_scan_id, 
            post_scan=post_scan_id,
            tags=tags,
            threshold=float(threshold),
        )
        message = 'Tests are being created in the background'

    # returning dynaminc response
    data = {
        'success': True,
        'message': message,
        'ids': created_tests,
    }
    if request is not None:
        record_api_call(request, data, '201')
        return Response(data, status=status.HTTP_201_CREATED)
    return data




def create_many_tests(request: object) -> object:
    """ 
    Bulk creates `Tests` for each requested `Page`.
    Either scoped for many `Pages` or many `Sites`.

    Expcets: {
        'request' : object,
    }

    Returns -> HTTP Response object
    """

    # get request data
    site_ids = request.data.get('site_ids')
    page_ids = request.data.get('page_ids')
    configs = request.data.get('configs', None)
    threshold = request.data.get('threshold', settings.TEST_THRESHOLD)
    types = request.data.get('type', settings.TYPES)
    tags = request.data.get('tags')
    user = request.user
    account = Member.objects.get(user=user).account

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # setting defaults
    num_succeeded = 0
    succeeded = []
    num_failed = 0
    failed = []
    this_status = True

    # scoped for sites
    if site_ids:
        for id in site_ids:
            data = {
                'site_id': str(id), 
                'configs': configs,
                'threshold': threshold,
                'type': types,
                'tags': tags,
                'user_id': str(user.id)
            }
            try:
                # create test
                res = create_test(delay=True, **data)
                if res['success']:
                    num_succeeded += 1
                    succeeded.append(str(id))
                else:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))
                    print(res['message'])
            except Exception as e:
                print(e)
                if str(id) not in failed:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))

    # scoped for pages
    if page_ids:
        for id in page_ids:
            data = {
                'page_id': str(id), 
                'configs': configs,
                'threshold': threshold,
                'type': types,
                'tags': tags,
                'user_id': str(user.id)
            }
            try:
                # create test
                res = create_test(delay=True, **data)
                if res['success']:
                    num_succeeded += 1
                    succeeded.append(str(id))
                else:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))
                    print(res['message'])
            except Exception as e:
                print(e)
                if str(id) not in failed:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))

    # format and return
    data = {
        'success': this_status,
        'num_succeeded': num_succeeded,
        'succeeded': succeeded,
        'num_failed': num_failed,
        'failed': failed, 
    }
    record_api_call(request, data, '201')
    return Response(data, status=status.HTTP_201_CREATED)
    



def get_tests(request: object) -> object:
    """ 
    Get one or more `Tests`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    test_id = request.query_params.get('test_id')
    page_id = request.query_params.get('page_id')
    lean = request.query_params.get('lean')
    user = request.user
    account = Member.objects.get(user=user).account
    
    # deciding on scope
    resource = 'page' if page_id else 'test'

    # check account and resource 
    check_data = check_account_and_resource(
        user=user, resource=resource, page_id=page_id, test_id=test_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get single test
    if test_id != None:
        
        # get test
        test = Test.objects.get(id=test_id)

        # serialize and return
        serializer_context = {'request': request,}
        serialized = TestSerializer(test, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    # get all page scoped tests
    page = Page.objects.get(id=page_id)
    tests = Test.objects.filter(page=page).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(tests, request)
    serializer_context = {'request': request,}
    serialized = TestSerializer(result_page, many=True, context=serializer_context)
    if str(lean).lower() == 'true':
        serialized = SmallTestSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_test(request: object, id: str) -> object:
    """
    Get single `Test` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, 
        test_id=id, resource='test'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get test if checks passed
    test = Test.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = TestSerializer(test, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def get_test_lean(request: object, id: str) -> object:
    """ 
    Get a single `Test` and only return scores & timestamps

    Expects: {
        'request' : object, 
        'id'      : str
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource 
    check_data = check_account_and_resource(
        user=user, resource='scan', scan_id=id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])
    
    # get test if checks passed
    test = Test.objects.get(id=id)

    # get images_delta if exists
    images_delta = {"average_score": test.images_delta.get('average_score')}

    # get lighthouse_delta if exists
    lighthouse_delta = {"scores": test.lighthouse_delta.get('scores')}

    # get lighthouse_delta if exists
    yellowlab_delta = {"scores": test.yellowlab_delta['scores']}

    # format data
    data = {
        "id": str(test.id),
        "site": str(test.site.id),
        "tags": test.tags,
        "type": test.type,
        "time_created": str(test.time_created),
        "time_completed": str(test.time_completed),
        "pre_scan": str(test.pre_scan.id),
        "post_scan": str(test.post_scan.id),
        "score": test.score,
        "lighthouse_delta": lighthouse_delta,
        "yellowlab_delta": yellowlab_delta,
        "images_delta": images_delta,
    }

    # return
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def delete_test(request: object=None, id: str=None, account: object=None) -> object:
    """ 
    Deletes the `Test` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str,
        'account' : object,
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    if request:
        account = Member.objects.get(user=request.user).account
        user = request.user
    
    if not request:
        user = account.user

    # check account and resource
    check_data = check_account_and_resource(user=user, test_id=id, resource='test')
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # get test if checks passed
    test = Test.objects.get(id=id)
    
    # remove s3 objects
    delete_test_s3_bg.delay(test.id, test.site.id, test.page.id)

    # delete test
    test.delete()

    # return response
    data = {'message': 'Test has been deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data




def delete_many_tests(request: object) -> object:
    """ 
    Deletes one or more `Tests` associated
    with the passed "request.ids" 

    Expcets: {
        'request' : object,
    }

    Returns -> HTTP Response object
    """

    # get request data
    ids = request.data.get('ids')

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check for ids
    if ids is not None:

        # setting defaults
        count = len(ids)
        num_succeeded = 0
        succeeded = []
        num_failed = 0
        failed = []
        user = request.user
        this_status = True

        # loop through passed ids
        for id in ids:

            # trying to delete site
            try:
                test = Test.objects.get(id=id)
                if test.site.account == account:
                    delete_test_s3_bg.delay(test.id, test.site.id, test.page.id)
                    test.delete()
                # add to success attempts
                num_succeeded += 1
                succeeded.append(str(id))
            except:
                # add to failed attempts
                num_failed += 1
                failed.append(str(id))
                this_status = False

        # format data
        data = {
            'success': this_status,
            'num_succeeded': num_succeeded,
            'succeeded': succeeded,
            'num_failed': num_failed,
            'failed': failed, 
        }

        # return response
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    
    # return error
    data = {
        'reason': 'you must provide an array of id\'s'
    }
    record_api_call(request, data, '400')
    response = Response(data, status=status.HTTP_400_BAD_REQUEST)
    return response




def get_tests_zapier(request: object) -> object:
    """ 
    Get all `Tests` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    account = Member.objects.get(user=request.user).account
    page_id = request.query_params.get('page_id')
    site_id = request.query_params.get('site_id')
    _status = request.query_params.get('status')
    tests = None
    
    # deciding on scope
    resource = 'test'

    # check account and resource 
    check_data = check_account_and_resource(
        user=request.user, resource=resource, page_id=page_id, 
        site_id=site_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get all page associated tests
    if page_id:
        tests = Test.objects.filter(
            page__account=account,
            page__id=page_id,
        ).exclude(
            time_completed=None,
            pre_scan=None,
            post_scan=None,
        ).order_by('-time_created')

    # get all site associated tests
    if site_id:
        tests = Test.objects.filter(
            site__account=account,
            site__id=site_id,
        ).exclude(
            time_completed=None,
            pre_scan=None,
            post_scan=None,
        ).order_by('-time_created')

    # get all account assocoiated tests
    if tests is None:
        tests = Test.objects.filter(
            site__account=account,
        ).exclude(
            time_completed=None,
            pre_scan=None,
            post_scan=None,
        ).order_by('-time_created')

    # filter my status if requested
    if status is not None:
        tests = tests.filter(status=_status)

    # build response data
    data = []

    for test in tests:
        data.append({
            'id'               :  str(test.id),
            'page'             :  str(test.page.id),
            'site'             :  str(test.site.id),
            'pre_scan'         :  str(test.pre_scan.id) if test.pre_scan else None,
            'post_scan'        :  str(test.post_scan.id) if test.post_scan else None,
            'time_created'     :  str(test.time_created),
            'time_completed'   :  str(test.time_completed),
            'type'             :  test.type,
            'status'           :  str(test.status),
            'score'            :  test.score,
            'threshold'        :  test.threshold,
            'component_scores' :  test.component_scores,
        })

    # serialize and return
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Issue Services ------ ###



def create_or_update_issue(request: object=None, **kwargs) -> object:
    """ 
    Creates or Updates an `Issue` 

    Expects: {
        'request': object
        'kwargs': dict
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    if request is not None:
        id = request.data.get('id')
        trigger = request.data.get('trigger')
        title = request.data.get('title')
        details = request.data.get('details')
        _status = request.data.get('status')
        affected = request.data.get('affected')
        labels = request.data.get('labels')
        account = Member.objects.get(user=request.user).account
    
    # get kwargs data
    if request is None:
        id = kwargs.get('id')
        trigger = kwargs.get('trigger')
        title = kwargs.get('title')
        details = kwargs.get('details')
        _status = kwargs.get('status')
        affected = kwargs.get('affected')
        labels = kwargs.get('labels')
        account_id = kwargs.get('account_id')
        account = Account.objects.get(id=account_id)

    # get Issue if id is present
    if id is not None:
        issue = Issue.objects.get(id=id)
        
        # update data
        if trigger is not None:
            issue.trigger = trigger
        if title is not None:
            issue.title = title
        if details is not None:
            issue.details = details
        if _status is not None:
            issue.status = _status
        if affected is not None:
            issue.affected = affected
        if labels is not None:
            issue.labels = labels
        
        # save new data
        issue.save()

    # create new Issue
    if id is None:
        issue = Issue.objects.create(
            account  = account,
            title    = title,
            details  = details,
            labels   = labels, 
            trigger  = trigger,
            affected = affected
        )
    
    # decide on response type
    if request is not None:
        # serialize and return
        serializer_context = {'request': request,}
        serialized = IssueSerializer(issue, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)
    
    # return object response
    return issue




def get_issues(request: object) -> object:
    """ 
    Get one or more `Issues`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    issue_id = request.query_params.get('issue_id')
    site_id = request.query_params.get('site_id')
    page_id = request.query_params.get('page_id')
    account = Member.objects.get(user=request.user).account
    issues = None
    
    # deciding on scope
    resource = 'issue'

    # check account and resource 
    check_data = check_account_and_resource(
        user=request.user, resource=resource, page_id=page_id, site_id=site_id,
        issue_id=issue_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get single issue
    if issue_id != None:
        
        # get test
        issue = Issue.objects.get(id=issue_id)

        # serialize and return
        serializer_context = {'request': request,}
        serialized = IssueSerializer(issue, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    # get all issues scoped page if page_id passed
    if page_id is not None:
        issues = Issue.objects.filter(
            affected__icontains={'id': page_id}, 
            account=account
        ).order_by('-status', '-time_created')
    # get all issues scoped page if page_id passed
    if site_id is not None:
        issues = Issue.objects.filter(
            affected__icontains={'id': site_id}, 
            account=account
        ).order_by('-status', '-time_created')
    
    # get all account assocoiated issues
    if issues is None:
        issues = Issue.objects.filter(
            account=account
        ).order_by('-status', '-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(issues, request)
    serializer_context = {'request': request,}
    serialized = IssueSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_issue(request: object, id: str) -> object:
    """
    Get single `Issue` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, 
        issue_id=id, resource='issue'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get issue if checks passed
    issue = Issue.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = IssueSerializer(issue, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def search_issues(request: object) -> object:
    """ 
    Searches for matching `Issues` to the passed 
    "query"

    Expects: {
        'request': obejct
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    user = request.user
    account = Member.objects.get(user=user).account
    query = request.query_params.get('query')
    
    # search for issues
    issues = Issue.objects.filter(
        Q(account=account, title__icontains=query) |
        Q(account=account, details__icontains=query) |
        Q(account=account, affected__icontains=query)
    ).order_by('-status', '-time_created')
    
    # serialize and rerturn
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(issues, request)
    serializer_context = {'request': request,}
    serialized = IssueSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response 




def delete_issue(request: object, id: str) -> object:
    """ 
    Deletes the `Issue` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, issue_id=id, resource='issue')
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get issue if checks passed
    issue = Issue.objects.get(id=id)

    # delete test
    issue.delete()

    # return response
    data = {'message': 'Issue has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def get_issues_zapier(request: object) -> object:
    """ 
    Get all `Issues` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    account = Member.objects.get(user=request.user).account
    page_id = request.query_params.get('page_id')
    site_id = request.query_params.get('site_id')
    issues = None
    
    # deciding on scope
    resource = 'issue'

    # check account and resource 
    check_data = check_account_and_resource(
        user=request.user, resource=resource, page_id=page_id,
        site_id=site_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])
    
    # get all page associated issues
    if page_id:
        issues = Issue.objects.filter(
            account=account,
            affected__icontains=page_id,
        ).order_by('-status','-time_created')

    # get all site associated issues
    if site_id:
        issues = Issue.objects.filter(
            account=account,
            affected__icontains=site_id,
        ).order_by('-status', '-time_created')

    # get all account assocoiated issues
    if issues is None:
        issues = Issue.objects.filter(
            account=account
        ).order_by('-status', '-time_created')

    # build response data
    data = []

    for issue in issues:
        data.append({
            'id'            :  str(issue.id),
            'title'         :  str(issue.title),
            'time_created'  :  str(issue.time_created),
            'details'       :  str(issue.details),
            'trigger'       :  issue.trigger,
            'affected'      :  issue.affected,
            'labels'        :  issue.labels,
            'status'        :  str(issue.status),
        })

    # serialize and return
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Schedule Services ------ ###




def create_or_update_schedule(request: object) -> object:
    """ 
    Creates or Updates a `Schedule` 

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    schedule_status = request.data.get('status')
    begin_date_raw = request.data.get('begin_date')
    time = request.data.get('time')
    timezone = request.data.get('timezone')
    freq = request.data.get('frequency')
    task_type = request.data.get('task_type')
    test_type = request.data.get('test_type', settings.TYPES)
    scan_type = request.data.get('scan_type', settings.TYPES)
    configs = request.data.get('configs', None)
    threshold = request.data.get('threshold', settings.TEST_THRESHOLD)
    schedule_id = request.data.get('schedule_id')
    site_id = request.data.get('site_id')
    page_id = request.data.get('page_id')
    case_id = request.data.get('case_id')
    updates = request.data.get('updates')

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # setting defaults
    schedule = None
    site = None
    page = None
    
    # deciding on action type
    action = 'add' if not schedule_id else None

    # checking account and resource 
    check_data = check_account_and_resource(
        request=request, resource='schedule', page_id=page_id, 
        site_id=site_id, schedule_id=schedule_id, action=action
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get schedule if checks passed and id is present
    if schedule_id:
        schedule = Schedule.objects.get(id=schedule_id)
    
    # converting to str for **kwargs
    if site_id is not None:
        site_id = str(site_id)
        site = Site.objects.get(id=site_id)
    if page_id is not None:
        page_id = str(page_id)
        page = Page.objects.get(id=page_id)

    # toggling schedule status
    if schedule_status != None and schedule != None:
        task = PeriodicTask.objects.get(id=schedule.periodic_task_id)
        if task.enabled == True:
            task.enabled = False
            schedule.status = 'Paused'
        else:
            task.enabled = True
            schedule.status = 'Active'
        task.save() 
        schedule.save()
    
    # creating or updating schedule
    if not schedule_status:

        # get automation if schedule exists
        auto_id = None
        if schedule:
            if Automation.objects.filter(schedule=schedule).exists():
                automation = Automation.objects.filter(schedule=schedule)[0]
                auto_id = str(automation.id)

        # build task
        task = f'api.tasks.create_{task_type}_bg'

        # build args
        arguments = {
            'site_id': site_id,
            'page_id': page_id,
            'updates': updates,
            'configs': configs,
            'case_id': case_id,
            'type': scan_type if task_type == 'scan' else test_type,
            'threshold': threshold,
            'automation_id': auto_id
        }

        # setting start date default
        begin_date = datetime.now()
        
        # parsing begin date
        if begin_date_raw:
            # begin_date = datetime.strptime(begin_date_raw, '%Y-%m-%d %H:%M:%S.%f') 
            begin_date = datetime.fromisoformat(begin_date_raw[:-1] + '+00:00')

        # building cron expression time & date
        num_day_of_week = begin_date.weekday()
        day = begin_date.strftime("%d")
        minute = time[3:5]
        hour = time[0:2]

        # building cron expression freq
        if freq == 'daily':
            day_of_week = '*'
            day_of_month = '*'
        elif freq == 'weekly':
            day_of_week = num_day_of_week
            day_of_month = '*'
        elif freq == 'monthly':
            day_of_week = '*'
            day_of_month = day

        # deciding on scope
        if site is not None:
            url = site.site_url
            level = 'site'
        if page is not None:
            url = page.page_url
            level = 'page'

        # building unique task name
        task_name = f'{task_type}_{level}_{url}_{freq}_@{time}_{account.user.id}'

        # building or updating crontab 
        crontab, _ = CrontabSchedule.objects.get_or_create(
            timezone=timezone, 
            minute=minute, 
            hour=hour,
            day_of_week=day_of_week, 
            day_of_month=day_of_month,
        )

        # updating periodic task if schedule
        periodic_task = None
        if schedule:
            if PeriodicTask.objects.filter(id=schedule.periodic_task_id).exists():
                # update existing task
                periodic_task = PeriodicTask.objects.filter(id=schedule.periodic_task_id)
                periodic_task.update(
                    crontab=crontab,
                    name=task_name, 
                    task=task,
                    kwargs=json.dumps(arguments),
                )
                # get periodic task by id
                periodic_task = PeriodicTask.objects.get(id=schedule.periodic_task_id)

        # check if no task yet
        if not periodic_task:

            # check if task exists
            if PeriodicTask.objects.filter(name=task_name).exists():
                data = {'reason': 'Schedule already exists',}
                record_api_call(request, data, '401')
                return Response(data, status=status.HTTP_401_UNAUTHORIZED)

            # create new periodic task 
            periodic_task = PeriodicTask.objects.create(
                crontab=crontab, 
                name=task_name, 
                task=task,
                kwargs=json.dumps(arguments),
            )

        # building extras for scheduls
        extras = {
            "configs": configs,
            "test_type": test_type,
            "scan_type": scan_type, 
            "case_id": case_id, 
            "updates": updates,
            "threshold": threshold,
        }
        
        # update existing schedule
        if schedule:
            
            # update each param if passed
            if timezone:
                schedule.timezone = timezone
            if begin_date:
                schedule.begin_date = begin_date 
            if time:
                schedule.time = time
            if freq:
                schedule.frequency = freq
            if task:
                schedule.task = task
            if crontab:
                schedule.crontab_id = crontab.id
            if task_type:
                schedule.task_type = task_type
            if extras:
                schedule.extras = extras 
            
            # save udpdates
            schedule.save()

        # create new schedule
        if not schedule:
            schedule = Schedule.objects.create(
                user=request.user, 
                site=site,
                page=page, 
                task_type=task_type, 
                timezone=timezone,
                begin_date=begin_date, 
                time=time, 
                frequency=freq,
                task=task, 
                crontab_id=crontab.id,
                periodic_task_id=periodic_task.id,
                extras=extras,
                account=account
            )

    # serialize and return
    serializer_context = {'request': request,}
    data = ScheduleSerializer(schedule, context=serializer_context).data
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def get_schedules(request: object) -> object:
    """ 
    Get one or more `Schedules`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    schedule_id = request.query_params.get('schedule_id')
    site_id = request.query_params.get('site_id')
    page_id = request.query_params.get('page_id')
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource 
    check_data = check_account_and_resource(
        user=user, resource='schedule', page_id=page_id, site_id=site_id, 
        schedule_id=schedule_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get single schedule
    if schedule_id:
        
        # get schedule
        schedule = Schedule.objects.get(id=schedule_id)

        # serialize and return
        serializer_context = {'request': request,}
        serialized = ScheduleSerializer(schedule, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)
    
    # get all site scoped schedules
    if site_id:
        site = Site.objects.get(id=site_id)
        schedules = Schedule.objects.filter(site=site).order_by('-time_created')
    
    # get all page scoped schedules
    if page_id:
        page = Page.objects.get(id=page_id)
        schedules = Schedule.objects.filter(page=page).order_by('-time_created')
    
    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(schedules, request)
    serializer_context = {'request': request,}
    serialized = ScheduleSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_schedule(request: object, id: str) -> object:
    """
    Get single `Schedule` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, 
        schedule_id=id, resource='schedule'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get schedule if checks passed
    schedule = Schedule.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = ScheduleSerializer(schedule, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def delete_schedule(request: object, id: str) -> object:
    """ 
    Deletes the `Schedule` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, schedule_id=id, resource='schedule')
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get schedule and task if checks passed
    schedule = Schedule.objects.get(id=id)
    task = PeriodicTask.objects.get(id=schedule.periodic_task_id)

    # delete schedule
    schedule.delete()

    # delete task
    task.delete()

    # return response
    data = {'message': 'Schedule has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def delete_tasks(page: object=None, site: object=None) -> None:
    """ 
    Helper function to delete any `Schedules` & `PerodicTasks`
    associated with the passed "site" or "page"

    Expects: {
        'page': object, 
        'site': object
    }

    Returns -> None
    """ 

    # get any schedules
    schedules = []
    
    # get all page scopped Schedules
    if page:
        schedules += Schedule.objects.filter(page=page)
    
    # get all site & page scopped Schedules
    if site:
        # get site scopped
        schedules += Schedule.objects.filter(site=site)
        # iterate over each site associated page and to schedules[]
        pages = Page.objects.filter(site=site)
        for p in pages:
            schedules += Schedule.objects.filter(page=p)

    # remove any associated tasks
    for schedule in schedules:
        task = PeriodicTask.objects.get(id=schedule.periodic_task_id)
        task.delete()
    
    return None




### ------ Begin Automation Services ------ ###




def create_or_update_automation(request: object) -> object:
    """ 
    Creates or Updates an `Automation` 

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """
    
    # get request data
    actions = request.data.get('actions')
    site_id = request.data.get('site_id')
    page_id = request.data.get('page_id')
    schedule_id = request.data.get('schedule_id')
    automation_id = request.data.get('automation_id')
    name = request.data.get('name')
    expressions = request.data.get('expressions')

    # set defaults
    automation = None
    schedule = None
    
    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # deciding on recsource
    resource = 'automation' if automation_id else 'schedule'

    # checking account and resource 
    check_data = check_account_and_resource(
        request=request, resource=resource, 
        automation_id=automation_id, schedule_id=schedule_id, 
        site_id=site_id, page_id=page_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get schedule if checks passed
    if schedule_id:
        schedule = Schedule.objects.get(id=schedule_id)
    if automation_id:
        automation = Automation.objects.get(id=automation_id)
        schedule = automation.schedule

    # update existing automation
    if automation:
        if name:
            automation.name = name
        if expressions:
            automation.expressions = expressions
        if actions:
            automation.actions = actions
        if schedule:
            automation.schedule = schedule
        # save updates
        automation.save()

    # create new automation
    if not automation:
        automation = Automation.objects.create(
            name=name, 
            expressions=expressions, 
            actions=actions,
            schedule=schedule, 
            user=user, 
            account=account
        )

    # update schedule 
    if schedule:

        # update schedule with new automation
        schedule.automation = automation
        schedule.save()

        # update associated periodicTask
        task = PeriodicTask.objects.get(id=schedule.periodic_task_id)
        
        # get associated page or site id
        site_id = None
        if schedule.site is not None:
            site_id = str(schedule.site.id)
        page_id = None
        if schedule.page is not None:
            page_id = str(schedule.page.id)

        # update periodic task
        arguments = {
            'site_id': site_id,
            'page_id': page_id,
            'automation_id': str(automation.id),
            'configs': json.loads(task.kwargs).get('configs'), 
            'type': json.loads(task.kwargs).get('type'),
            'threshold': json.loads(task.kwargs).get('threshold'),
            'case_id': json.loads(task.kwargs).get('case_id'),
            'updates': json.loads(task.kwargs).get('updates')
        }
        task.kwargs=json.dumps(arguments)
        task.save()

    # serialize and return
    serializer_context = {'request': request,}
    data = AutomationSerializer(automation, context=serializer_context).data
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response

    


def get_automations(request: object) -> object:
    """ 
    Get one or more `Automations`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    automation_id = request.query_params.get('automation_id')
    
    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource 
    check_data = check_account_and_resource(
        user=user, resource='automation', automation_id=automation_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get single automation
    if automation_id:        
        
        # get automation
        automation = Automation.objects.get(id=automation_id)
        
        # serialize and return
        serializer_context = {'request': request,}
        serialized = AutomationSerializer(automation, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)
    
    # get all automations associated with account
    automations = Automation.objects.filter(account=account).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(automations, request)
    serializer_context = {'request': request,}
    serialized = AutomationSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_automation(request: object, id: str) -> object:
    """
    Get single `Automation` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, 
        automation_id=id, resource='automation'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get automation if checks passed
    automation = Automation.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = AutomationSerializer(automation, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def delete_automation(request: object, id: str) -> object:
    """ 
    Deletes the `Automation` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, automation_id=id, resource='automation')
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get automation if checks passed
    automation = Automation.objects.get(id=id)

    # delete automation
    automation.delete()

    # return response
    data = {'message': 'Automation has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Report Services ------ ###




def create_or_update_report(request: object) -> object:
    """ 
    Creates or Updates an `Report` 

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    report_id = request.data.get('report_id')
    page_id = request.data.get('page_id')
    report_type = request.data.get('type', ['lighthouse', 'yellowlab'])
    text_color = request.data.get('text_color', '#24262d')
    background_color = request.data.get('background_color', '#e1effd')
    highlight_color = request.data.get('highlight_color', '#4283f8')

    # set defaults
    report = None
    page = None
    
    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # checking account and resource 
    check_data = check_account_and_resource(
        request=request, resource='report', 
        report_id=report_id, page_id=page_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get page if checks passed
    if page_id:    
        page = Page.objects.get(id=page_id)
    # get report if checks passed
    if report_id:
        report = Report.objects.get(id=report_id)

    # build report info
    info = {
        "text_color": text_color,
        "background_color": background_color,
        "highlight_color": highlight_color,
    }
    
    # update report
    if report:
        if info:
            report.info = info
        if report_type:
            report.type = report_type
        # save updates
        report.save()
        
    # create new report
    if not report:
        report = Report.objects.create(
            user=request.user, 
            page=page, 
            site=page.site, 
            account=account,
            info=info,
            type=report_type
        )
    
    # get uncached report 
    un_cached_report = Report.objects.get(id=report.id)

    # generate report
    report_data = R(report=un_cached_report).generate_report()

    # serialize report
    serializer_context = {'request': request,}
    new_report = ReportSerializer(
        report_data['report'], 
        context=serializer_context
    ).data

    # format return data
    data = {
        'report': new_report,
        'success': report_data['success'],
        'message': report_data['message']
    }

    # serialize and return
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response




def get_reports(request: object) -> object:
    """ 
    Get one or more `Reports`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    page_id = request.query_params.get('page_id', None)
    report_id = request.query_params.get('report_id', None)
    
    # get user and account
    user = request.user 
    account = Member.objects.get(user=user).account

    # check account and resource 
    check_data = check_account_and_resource(
        user=user, resource='report', report_id=report_id,
        page_id=page_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get single report
    if report_id:
        
        # get report
        report = Report.objects.get(id=report_id)

        # serialize and return
        serializer_context = {'request': request,}
        serialized = ReportSerializer(report, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    # get reports scoped to page if checks passed
    if page_id:
        page = Page.objects.get(id=page_id)
        reports = Report.objects.filter(page=page, account=account).order_by('-time_created')

    # get reports scoped to user if checks passed
    if page_id is None and report_id is None:
        reports = Report.objects.filter(user=request.user).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(reports, request)
    serializer_context = {'request': request,}
    serialized = ReportSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_report(request: object, id: str) -> object:
    """
    Get single `Report` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, 
       report_id=id, resource='report'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get report if checks passed
    report = Report.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = ReportSerializer(report, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def delete_report(request: object, id: str) -> object:
    """ 
    Deletes the `Report` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, report_id=id, resource='report')
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get report if checks passed
    report = Report.objects.get(id=id)

    # remove s3 objects
    delete_report_s3_bg.delay(report_id=id)
    
    # remove report
    report.delete()

    # return reponse
    data = {'message': 'Report has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def export_report(request: object) -> object:
    """
    Used to create and send a Scanerr.landing 
    `Report` to the passed "email"  

    Expects: {
        'request': object
    }

    Returns -> HTTP Response object
    """

    # getting data from request
    report_id = request.data.get('report_id')
    email = request.data.get('email')
    first_name = request.data.get('first_name')

    # send task to background
    create_report_export_bg.delay(
        report_id=report_id,
        email=email, 
        first_name=first_name
    )

    # building response
    data = {
        'success': True,
        'error': None
    }

    # returning response
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Cases Services ------ ###




def create_or_update_case(request: object) -> object:
    """ 
    Creates or Updates a `Report` 

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    case_id = request.data.get('case_id')
    steps = request.data.get('steps')
    site_url = request.data.get('site_url')
    name = request.data.get('name')
    tags = request.data.get('tags')
    _type = request.data.get('type')
    
    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # setting defaults
    site = None
    case = None

    # checking account and resource 
    check_data = check_account_and_resource(
        request=request, resource='case', 
        case_id=case_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])
    
    # get site if site_url passed
    if site_url:
        if Site.objects.filter(account=account, site_url=site_url).exists():
            site = Site.objects.filter(account=account, site_url=site_url)[0]

    # get case if checks passed
    if case_id:
        case = Case.objects.get(id=case_id)

    # udpate case   
    if case:
        if steps is not None:
            steps_data = save_case_steps(steps, case_id)
            case.steps = steps_data
        if name is not None:
            case.name = name
        if tags is not None:
            case.tags = tags
        # save updates
        case.save()
    
    # create case
    if not case:

        # generate new uuid
        case_id = uuid.uuid4()

        # save step data in s3
        steps_data = save_case_steps(steps, case_id)
        
        # create new case
        case = Case.objects.create(
            id = case_id,
            user = request.user,
            name = name, 
            type = _type if _type is not None else "recorded",
            site = site,
            site_url = site_url,
            steps = steps_data,
            account = account
        )

    # serialize and return
    serializer_context = {'request': request,}
    data = CaseSerializer(case, context=serializer_context).data
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response




def save_case_steps(steps: dict, steps_id: str) -> dict:
    """ 
    Helper function that uploads the "steps" data to 
    s3 bucket

    Expects: {
        'steps'   : dict, 
        'step_id' : str
    }

    Returns -> data: {
        'num_steps' : int,
        'url'       : str
    }
    """

    # setup boto3 configurations
    s3 = boto3.client(
        's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
        aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
        region_name=str(settings.AWS_S3_REGION_NAME), 
        endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
    )

    # saving as json file temporarily
    with open(f'{steps_id}.json', 'w') as fp:
        json.dump(steps, fp)
    
    # seting up paths
    steps_file = os.path.join(settings.BASE_DIR, f'{steps_id}.json')
    remote_path = f'static/cases/steps/{steps_id}.json'
    root_path = settings.AWS_S3_URL_PATH
    steps_url = f'{root_path}/{remote_path}'

    # upload to s3
    with open(steps_file, 'rb') as data:
        s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
            remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "application/json"}
        )

    # remove local copy
    os.remove(steps_file)

    # format data
    data = {
        'num_steps': len(steps),
        'url': steps_url
    }

    # return response
    return data




def get_cases(request: object) -> object:
    """ 
    Get one or more `Cases`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    case_id = request.query_params.get('case_id')
    site_id = request.query_params.get('site_id')
    user = request.user
    account = Member.objects.get(user=user).account

    # setting defaulta
    case = None
    site = None

    # checking account and resource 
    check_data = check_account_and_resource(
        request=request, resource='case', 
        case_id=case_id, site_id=site_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get single case
    if case_id:        

        # get case
        case = Case.objects.get(id=case_id)

        # serialize and return
        serializer_context = {'request': request,}
        serialized = CaseSerializer(case, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    # get site if checks passed
    if site_id:
        site = Site.objects.get(id=site_id)

    # get cases scoped by site
    if site:
        cases = Case.objects.filter(account=account, site=site).order_by('-time_created')
    
    # get cases scoped by account
    if not site:
        cases = Case.objects.filter(account=account).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(cases, request)
    serializer_context = {'request': request,}
    serialized = CaseSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_case(request: object, id: str) -> object:
    """
    Get single `Case` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, 
       case_id=id, resource='case'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get case if checks passed
    case = Case.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = CaseSerializer(case, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def search_cases(request: object) -> object:
    """ 
    Searches for matching `Cases` to the passed 
    "query"

    Expects: {
        'request': obejct
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    user = request.user
    account = Member.objects.get(user=user).account
    query = request.query_params.get('query')
    
    # search for cases
    cases = Case.objects.filter(
        Q(account=account, name__icontains=query) |
        Q(account=account, site_url__icontains=query) 
    ).order_by('-time_created')
    
    # serialize and rerturn
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(cases, request)
    serializer_context = {'request': request,}
    serialized = CaseSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response 




def create_auto_cases(request: object) -> object:
    """
    Initiates a new `Case` generation task for the `Site` 
    associated with either the passed "site_url" or "site_id" 

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    site_id = request.data.get('site_id')
    site_url = request.data.get('site_url')
    start_url = request.data.get('start_url')
    max_cases = request.data.get('max_cases', 4)
    max_layers = request.data.get('max_layers', 6)
    configs = request.data.get('configs', None)
    
    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # get site if only site_url present
    if site_url is not None:
        site = Site.objects.filter(account=account, site_url=site_url)[0]
        site_id = str(site.id)

    # checking account and resource 
    check_data = check_account_and_resource(
        request=request, resource='case', 
        site_id=site_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get site if only site_id present
    if site_id and not site_url:
        site = Site.objects.get(id=site_id)
   
    # create process obj
    process = Process.objects.create(
        site=site,
        type='case',
        account=account,
        progress=1
    )

    # send data to bg_autocase_task
    create_auto_cases_bg.delay(
        site_id=site_id,
        process_id=process.id,
        start_url=start_url,
        configs=configs,
        max_cases=max_cases,
        max_layers=max_layers,
    )

    # return response
    data = {
        'message': 'Cases are generating',
        'process': str(process.id),
    }
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def copy_case(request: object) -> object:
    """ 
    Creates a copy of the passed `Case`

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response obejct
    """

    # get request data
    case_id = request.data.get('case_id')

    # get user and acount
    user = request.user
    account = Member.objects.get(user=user).account

    # checking account and resource 
    check_data = check_account_and_resource(
        request=request, resource='case', 
        case_id=case_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get case if checks passed
    if case_id:
        case = Case.objects.get(id=case_id, account=account)

    # download steps 
    steps = requests.get(case.steps['url']).json()
    
    # save steps as new s3 obj
    new_case_id = uuid.uuid4()
    steps_data = save_case_steps(steps, new_case_id)

    # create new case
    new_case = Case.objects.create(
        id = new_case_id,
        user = request.user,
        name = f'Copy - {case.name}', 
        type = case.type,
        site = case.site,
        site_url = case.site_url,
        steps = steps_data,
        account = account
    )

    # return response
    serializer_context = {'request': request,}
    data = CaseSerializer(new_case, context=serializer_context).data
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response
    



def delete_case(request: object=None, id: str=None, account: object=None) -> object:
    """ 
    Deletes the `Case` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str,
        'account' : object,
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    if request:
        account = Member.objects.get(user=request.user).account
        user = request.user
    
    if not request:
        user = account.user

    # checking account and resource 
    check_data = check_account_and_resource(
        user=user, resource='case', 
        case_id=id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # get case if checks passed
    case = Case.objects.get(id=id)
    
    # delete case s3 objects
    delete_case_s3_bg.delay(case_id=id)

    # delete case
    case.delete()

    # return response
    data = {'message': 'Case has been deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data




def get_cases_zapier(request: object) -> object:
    """ 
    Get all `Cases` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    account = Member.objects.get(user=request.user).account
    site_id = request.query_params.get('site_id')
    cases = None
    
    # deciding on scope
    resource = 'case'

    # check account and resource 
    check_data = check_account_and_resource(
        user=request.user, resource=resource, site_id=site_id,
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get all site_id associated cases
    if site_id:
        site = Site.objects.get(id=site_id)
        cases = Case.objects.filter(
            account=account,
            site=site
        ).order_by('-time_created')


    # get all account assocoiated cases
    if cases is None:
        cases = Case.objects.filter(
            account=account,
        ).order_by('-time_created')

    # build response data
    data = []

    for case in cases:
        data.append({
            'id'              :  str(case.id),
            'name'            :  case.name,
            'time_created'    :  str(case.time_created),
            'site'            :  str(case.site.id),
            'site_url'        :  case.site_url,
            'steps'           :  case.steps,
            'tags'            :  case.tags
        })

    # serialize and return
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Testcase Services ------ ###




def create_testcase(request: object, delay: bool=False) -> object:
    """ 
    Creates a new `Testcase` from the passed "case_id" for the 
    passed "site_id"

    Expects: {
        'request': obejct
    }

    Returns -> HTTP Response object
    """

    # get request data
    case_id = request.data.get('case_id')
    site_id = request.data.get('site_id')
    updates = request.data.get('updates')
    configs = request.data.get('configs', None)
    
    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # checking account and resource 
    check_data = check_account_and_resource(
        request=request, resource='testcase', 
        case_id=case_id, site_id=site_id, action='add',
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get case & site if checks passed
    case = Case.objects.get(id=case_id, account=account)
    site = Site.objects.get(id=site_id, account=account)

    # getting steps from case
    steps = requests.get(case.steps['url']).json()

    # adding new info to steps for testcase
    for step in steps:
        # expanding action
        if step['action']['type'] != None:
            step['action']['time_created'] = None
            step['action']['time_completed'] = None
            step['action']['exception'] = None
            step['action']['passed'] = None
            step['action']['img'] = None
        # expanding assertion
        if step['assertion']['type'] != None:
            step['assertion']['time_created'] = None
            step['assertion']['time_completed'] = None
            step['assertion']['exception'] = None
            step['assertion']['passed'] = None

    # updating values if requested
    if updates != None:
        for update in updates:
            steps[int(update['index'])]['action']['value'] = update['value']

    # create new tescase 
    testcase = Testcase.objects.create(
        case = case,
        case_name = case.name,
        site = site,
        user = request.user,
        configs = configs, 
        steps = steps,
        account = account
    )

    # pass the newly created Testcase to the backgroud task to run
    create_testcase_bg.delay(testcase_id=testcase.id)

    # serialize and return
    serializer_context = {'request': request,}
    data = TestcaseSerializer(testcase, context=serializer_context).data
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response




def get_testcases(request: object) -> object:
    """ 
    Get one or more `Testcase`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """
    
    # get request data
    testcase_id = request.query_params.get('testcase_id')
    site_id = request.query_params.get('site_id')
    lean = request.query_params.get('lean')

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # checking account and resource 
    check_data = check_account_and_resource(
        request=request, resource='testcase', 
        testcase_id=testcase_id, site_id=site_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get single testcase
    if testcase_id:        

        # get testcase
        testcase = Testcase.objects.get(id=testcase_id)

        # serialize and return
        serializer_context = {'request': request,}
        serialized = TestcaseSerializer(testcase, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    # get testcases scoped to site
    if site_id:
        site = Site.objects.get(id=site_id, account=account)
        testcases = Testcase.objects.filter(site=site).order_by('-time_created')
    
    # get testcases scoped to account
    if not site_id:
        testcases = Testcase.objects.filter(account=account).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(testcases, request)
    serializer_context = {'request': request,}
    serialized = TestcaseSerializer(result_page, many=True, context=serializer_context)
    if str(lean).lower() == 'true':
        serialized = SmallTestcaseSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_testcase(request: object, id: str) -> object:
    """
    Get single `Testcase` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, 
       testcase_id=id, resource='testcase'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get testcase if checks passed
    testcase = Testcase.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = TestcaseSerializer(testcase, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def delete_testcase(request: object=None, id: str=None, account: object=None) -> object:
    """ 
    Deletes the `Testcase` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str,
        'account' : object
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    if request:
        account = Member.objects.get(user=request.user).account
        user = request.user
    
    if not request:
        user = account.user

    # checking account and resource 
    check_data = check_account_and_resource(
        user=user, resource='testcase', 
        testcase_id=id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # get testcase if checks passed
    testcase = Testcase.objects.get(id=id)

    # remove s3 objects
    delete_testcase_s3_bg.delay(testcase_id=id)

    # delete testcase
    testcase.delete()

    # return response
    data = {'message': 'Testcase has been deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data




def get_testcases_zapier(request: object) -> object:
    """ 
    Get all `Testcases` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    passed = request.query_params.get('passed')
    account = Member.objects.get(user=request.user).account
    testcases = None
    
    # deciding on scope
    resource = 'testcase'

    # check account and resource 
    check_data = check_account_and_resource(
        user=request.user, resource=resource
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get all account assocoiated testcases
    if testcases is None:
        testcases = Testcase.objects.filter(
            account=account,
        ).exclude(
            time_completed=None,
        ).order_by('-time_created')

    # filter by passed if requested
    if passed is not None:
        testcases = testcases.filter(passed=passed)

    # build response data
    data = []

    for testcase in testcases:
        data.append({
            'id'              :  str(testcase.id),
            'case'            :  str(testcase.case.id),
            'case_name'       :  str(testcase.case_name),
            'site'            :  str(testcase.site.id),
            'time_created'    :  str(testcase.time_created),
            'time_completed'  :  str(testcase.time_completed),
            'configs'         :  testcase.configs,
            'passed'          :  str(testcase.passed),
        })

    # serialize and return
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Process Services ------ ###




def get_processes(request: object) -> object:
    """ 
    Get one or more `Processes`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """
    
    # get request data
    site_id = request.query_params.get('site_id')
    process_id = request.query_params.get('process_id')
    _type = request.query_params.get('type')

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # checking account and resource 
    check_data = check_account_and_resource(
        request=request, resource='process', 
        process_id=process_id, site_id=site_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get single process
    if process_id:
        
        # get process
        process = Process.objects.get(id=process_id)
        
        # serialize and return
        serializer_context = {'request': request,}
        data = ProcessSerializer(process, context=serializer_context).data
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response

    # get processes scoped to site
    if site_id:
        site = Site.objects.get(id=site_id)
        processes = Process.objects.filter(site=site).order_by('-time_created')

    # get processes scoped to accout and/or type
    if site_id is None and process_id is None:
        if _type is None:
            processes = Process.objects.filter(account=account).order_by('-time_created')
        if _type is not None:
            processes = Process.objects.filter(account=account, type=_type).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(processes, request)
    serializer_context = {'request': request,}
    serialized = ProcessSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_process(request: object, id: str) -> object:
    """
    Get single `Process` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, 
       process_id=id, resource='process'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get process if checks passed
    process = Process.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = ProcessSerializer(process, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




### ------ Begin Log Services ------ ###




def get_logs(request: object) -> object:
    """ 
    Get one or more `Testcase`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    log_id = request.query_params.get('log_id')
    request_status = request.query_params.get('success')
    request_type = request.query_params.get('request_type')

    # get user 
    user = request.user

    # get single log
    if log_id:

        # get log
        log = Log.objects.get(id=log_id)
        
        # serialize and return
        serializer_context = {'request': request,}
        serialized = LogSerializer(log, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    # filtering logs by passed params
    if request_status != None and request_type != None:
        logs = Log.objects.filter(status=request_status, request_type=request_type, user=user).order_by('-time_created')
    elif request_status == None and request_type != None:
        logs = Log.objects.filter(request_type=request_type, user=user).order_by('-time_created')
    elif request_status != None and request_type == None:
        logs = Log.objects.filter(status=request_status, user=user).order_by('-time_created')
    else:
        logs = Log.objects.filter(user=user).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(logs, request)
    serializer_context = {'request': request,}
    serialized = LogSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    return response




def get_log(request: object, id: str) -> object:
    """
    Get single `Log` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Member.objects.get(user=user).account

    # check account and resource
    check_data = check_account_and_resource(request=request, 
       log_id=id, resource='log'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get log if checks passed
    log = Log.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = LogSerializer(log, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




### ------ Begin Search Services ------ ###




def search_resources(request: object) -> object:
    """
    This method will search for any `Page` or `Site`
    that is associated with the user's `Account` and
    matches the query string.

    Expects:
        'query': <str> the query string
    
    Returns:
        data -> [
            {
                'name': <str>,
                'type': <str>,
                'path': <str>,
                'id'  : <str>,
            }
            ...
        ]
    """

    # get data
    query = request.query_params.get('query')
    user = request.user
    account = Member.objects.get(user=user).account
    data = []
    cases = []
    pages = []
    sites = []
    issues = []

    # check for object specification i.e 'site:', 'case:', 'issue:'
    resource_type = query.replace('https://', '').replace('http://', '').split(':')[0]
    query = query.replace('https://', '').replace('http://', '').split(':')[-1]

    # search for sites
    if resource_type == 'site' or resource_type == query:
        sites = Site.objects.filter(account=account).filter(
            site_url__icontains=query
        )

    # search for pages
    if resource_type == 'page' or resource_type == query:
        pages = Page.objects.filter(account=account).filter(
            page_url__icontains=query
        )

    # search for cases
    if resource_type == 'case' or resource_type == query:
        cases = Case.objects.filter(account=account).filter(
            name__icontains=query
        )

    # search for issues
    if resource_type == 'issue' or resource_type == query:
        issues = Issue.objects.filter(account=account).filter(
            title__icontains=query
        )

    # adding first several sites if present
    i = 0
    max_sites = 10 if resource_type == 'site' else 3
    while i <= max_sites and i <= (len(sites)-1):
        data.append({
            'name': str(sites[i].site_url),
            'path': f'/site/{sites[i].id}',
            'id'  : str(sites[i].id),
            'type': 'site',
        })
        i+=1
    
    # adding first several pages if present
    i = 0
    max_pages = 10 if resource_type == 'page' else 3
    while i <= max_pages and i <= (len(pages)-1):
        data.append({
            'name': str(pages[i].page_url),
            'path': f'/page/{pages[i].id}',
            'id'  : str(pages[i].id),
            'type': 'page',
        })
        i+=1
    
    # adding first several cases if present
    i = 0
    max_cases = 10 if resource_type == 'case' else 3
    while i <= max_cases and i <= (len(cases)-1):
        data.append({
            'name': str(cases[i].name),
            'path': f'/case/{cases[i].id}',
            'id'  : str(cases[i].id),
            'type': 'case',
        })
        i+=1
    
    # adding first several issues if present
    i = 0
    max_issues = 10 if resource_type == 'issue' else 3
    while i <= max_issues and i <= (len(issues)-1):
        data.append({
            'name': str(issues[i].title),
            'path': f'/issue/{issues[i].id}',
            'id'  : str(issues[i].id),
            'type': 'issue',
        })
        i+=1
    
    # return response
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Metrics Services ------ ###




def get_home_metrics(request: object) -> object:
    """ 
    Builds metrics for account "Home" view 
    on Scanerr.client

    Expects: {
        'request' : object
    }

    Returns -> HTTP Response object
    """

    # get user, account, sites, & issues
    user = request.user
    account = Member.objects.get(user=user).account
    sites = Site.objects.filter(account=account)
    issues = Issue.objects.filter(account=account, status='open')
    
    # setting defaults
    issues = issues.count()
    tests = account.usage['tests']
    scans = account.usage['scans']
    testcases = account.usage['testcases']
    schedules = 0

    # calculating metrics
    for site in sites:
        schedules += Schedule.objects.filter(site=site).count()

        # getting associated pages
        pages = Page.objects.filter(site=site)

        # adding page scoped schedules 
        for page in pages:
            schedules += Schedule.objects.filter(page=page).count()

    # calculate usages
    sites = sites.count()
    sites_usage = round((sites/account.max_sites)*100, 2) if sites > 0 else 0
    schedules_usage = round((schedules/account.max_schedules)*100, 2) if schedules > 0 else 0
    scans_usage = round((scans/account.usage['scans_allowed'])*100, 2) if scans > 0 else 0
    tests_usage = round((tests/account.usage['tests_allowed'])*100, 2) if tests > 0 else 0
    testcases_usage = round((testcases/account.usage['testcases_allowed'])*100, 2) if testcases > 0 else 0
    
    # format data
    data = {
        "sites": sites, 
        "sites_usage": sites_usage,
        "tests": tests,
        "tests_usage": tests_usage,
        "scans": scans,
        "scans_usage": scans_usage,
        "schedules": schedules,
        "schedules_usage": schedules_usage,
        "testcases": testcases,
        "testcases_usage": testcases_usage,
        "open_issues": issues,
    }
    
    # return response
    response = Response(data, status=status.HTTP_200_OK)
    return response





def get_site_metrics(request: object) -> object:
    """ 
    Builds metrics for account "Site" view 
    on Scanerr.client

    Expects: {
        'request' : object
    }

    Returns -> HTTP Response object
    """

    # get user, account, site, & pages
    user = request.user
    account = Member.objects.get(user=user).account
    site_id = request.query_params.get('site_id')
    site = Site.objects.get(id=site_id)
    max_sites = account.max_sites
    pages = Page.objects.filter(site=site)

    # setting detaults
    # testcases = round(account.usage['testcases'] / max_sites) if account.usage['testcases'] > 0 else 0
    # tests = round(account.usage['tests'] / max_sites) if account.usage['tests'] > 0 else 0
    # scans = round(account.usage['scans'] / max_sites) if account.usage['scans'] > 0 else 0
    tests = account.usage['tests']
    scans = account.usage['scans']
    testcases = account.usage['testcases']
    schedules = Schedule.objects.filter(site=site).count()

    # calculating page scoped schedules
    for page in pages:
        schedules += Schedule.objects.filter(page=page).count()
    
    # calculate usage
    pages = pages.count()
    pages_usage = round((pages/account.max_pages)*100, 2) if pages > 0 else 0
    # scans_usage = round((scans/round(account.usage['scans_allowed']/max_sites))* 100, 2) if scans > 0 else 0
    # tests_usage = round((tests/round(account.usage['tests_allowed']/max_sites))* 100, 2) if tests > 0 else 0
    # testcases_usage = round((testcases/round(account.usage['testcases_allowed']/max_sites))* 100, 2) if testcases > 0 else 0
    # schedules_usage = round((schedules/round(account.max_schedules/max_sites))*100, 2) if schedules > 0 else 0
    schedules_usage = round((schedules/account.max_schedules)*100, 2) if schedules > 0 else 0
    scans_usage = round((scans/account.usage['scans_allowed'])*100, 2) if scans > 0 else 0
    tests_usage = round((tests/account.usage['tests_allowed'])*100, 2) if tests > 0 else 0
    testcases_usage = round((testcases/account.usage['testcases_allowed'])*100, 2) if testcases > 0 else 0


    # format data
    data = {
        "pages": pages, 
        "pages_usage": pages_usage, 
        "tests": tests,
        "tests_usage": tests_usage,
        "scans": scans,
        "scans_usage": scans_usage,
        "schedules": schedules,
        "schedules_usage": schedules_usage,
        "testcases": testcases,
        "testcases_usage": testcases_usage,
    }

    # return response
    response = Response(data, status=status.HTTP_200_OK)
    return response





def get_celery_metrics(request: object) -> object:
    """ 
    Builds metrics for current Celery task load.
    Used to provision and terminate new pods in 
    k8s cluster on PROD

    Expects: {
        'request' : object
    }

    Returns -> HTTP Response object
    """

    
    # get redis queue len
    redis_client = Redis.from_url(
        settings.CELERY_BROKER_URL, 
        socket_connect_timeout=3
    )
    redis_queue_len = redis_client.llen(
        app.default_app.conf.task_default_queue
    )

    # Inspect all nodes.
    i = celery.app.control.inspect()
    
    # Tasks received, but are still waiting to be executed.
    reserved = i.reserved()
    #
    #  Active tasks
    active = i.active()

    # init task & replica counters
    # & ratio 
    num_tasks = 0
    num_replicas = 0
    ratio = 0
    working_len = 0

    # loop through all reserved & active tasks and
    # add length of array (tasks) to total
    for replica in reserved:
        num_tasks += len(reserved[replica])
        num_replicas += 1
    for replica in active:
        num_tasks += len(active[replica])

    # build metrics
    if num_replicas > 0:
        ratio = num_tasks / num_replicas

    # get working length 
    working_len = redis_queue_len + num_tasks

    # format data
    data = {
        "num_tasks": num_tasks,
        "num_replicas": num_replicas,
        "ratio": ratio,
        "redis_queue": redis_queue_len,
        "working_len": working_len
    }

    # return response
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Beta Services ------ ###




def migrate_site(request: object) -> object:
    """
    Initiate a `Site` migration task in background

    Expects: {
        'request': object
    }

    Returns -> HTTP Response object
    """

    # get request data
    login_url = request.data.get('login_url', None)
    admin_url = request.data.get('admin_url', None)
    plugin_name = request.data.get('plugin_name', 'Cloudways WordPress Migrator')
    username = request.data.get('username', None)
    password = request.data.get('password', None)
    site_id = request.data.get('site_id', None)
    email_address = request.data.get('email_address', None)
    destination_url = request.data.get('destination_url', None)
    sftp_address = request.data.get('sftp_address', None) 
    dbname = request.data.get('dbname', None)
    sftp_username = request.data.get('sftp_username', None)
    sftp_password = request.data.get('sftp_password', None)
    wait_time = request.data.get('wait_time', 30)
    driver = request.data.get('driver', 'selenium')

    # checking account and resource 
    check_data = check_account_and_resource(
        request=request, resource='site', 
        site_id=site_id
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])
    
    # get site if checks passed
    site = Site.objects.get(id=site_id)

    # create new Process
    process = Process.objects.create(
        site=site,
        type='migration'
    )

    # start migrtation task in background
    migrate_site_bg.delay(
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
        process.id, 
        driver
    )
    
    # serialize and return
    serializer_context = {'request': request,}
    data = ProcessSerializer(process, context=serializer_context).data
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response





