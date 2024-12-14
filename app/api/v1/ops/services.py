from django.contrib.auth.models import User
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from django.db.models import Q
from django.http import HttpResponse
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework import status
from cryptography.fernet import Fernet
from cursion import celery
from redis import Redis
from cursion import settings
from celery import app
from .serializers import *
from ...tasks import *
from ...models import *
from ...utils.reporter import Reporter as R
from ...utils.devices import devices
from datetime import datetime, timedelta, timezone as timezone
import json, boto3, asyncio, os, requests, uuid, secrets






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




def decrement_resource(account: object, resource: str) -> None:
    """ 
    Removes '1' from the resource total 

    Expcets: {
        'account'  : <object>,
        'resource' : <str> 'site', 'page', 'schedule'
    }

    Returns: Non
    """

    # remove 1 from account.usage[{resource}]
    account.usage[f'{resource}'] -= 1
    account.save()

    # return None
    return None




def check_location(request: None, local: None) -> dict:
    """ 
    Reroutes a request to a geo-specific 
    instance of Cursion Server. 

    Expcets: {
        'request': obj,
        'local'  : str,
    }

    Returns: data: {
        'routed': bool (True if request was forwarded)
        'response': obj (HTTP response from forwarded request)
    }
    """

    # set defaults
    routed = False
    response = None

    # checking if request was passed
    if request:

        # get user and account
        user = request.user
        member = Member.objects.get(user=user)
        account = member.account

        # get configs obj & location
        configs = request.data.get('configs', account.configs)
        location = local if local else configs.get('location', settings.LOCATION)

        # get path & build url
        path = request.path
        root = settings.API_URL_ROOT.lstrip('https://')
        url = f'https://{location}-{root}{path}'

        # get authorization & build headers
        auth = request.headers.get('Authorization')
        headers = {
            'Content-Type': 'application/json',
            'Authorization': auth
        }
        
        # check location and forward request
        if location != settings.LOCATION:
            routed = True
            # send request
            print(f'forwarding request to: {url}')
            resp = requests.post(
                url=url,
                headers=headers,
                data=json.dumps(request.data)
            )
            # build response
            response = HttpResponse(
                content=resp.content,
                status=resp.status_code,
                headers=resp.headers
            )
    
    # return data
    data = {
        'routed': routed,
        'response': response
    }
    return data




def check_permissions_and_usage(
        member: object=None, 
        resource: str=None, 
        action: str='get', 
        id: str=None, 
        id_type: str=None,
        url: str=None
    ) -> dict:
    """ 
    References Member.permissions to determine if 
    give action is allowed on given resource.

    Expects: {
        'member'    : obj, (REQUIRED)
        'resource'  : str, (REQUIRED)
        'action'    : str, (OPTIONAL, 'get')
        'id'        : str, (OPTIONAL)
        'id_type'   : str, (OPTIONAL)
        'url'       : str, (OPTIONAL)
    }
    
    Returns: {
        'allowed'   : bool,
        'error'     : str,
        'code':     : str, 
        'status':   : object
    }
    """

    # get account from member
    account = member.account

    # set default 
    allowed = True
    error = 'not allowed'
    code = '403'
    _status = status.HTTP_403_FORBIDDEN

    # ignore site assoc checks on these resorces
    ignore_list = ['alert', 'schedule', 'log', 'process', 'flow', 'secret']
    
    # check usage on these resources
    usage_list = ['site', 'schedule', 'caserun', 'flowrun', 'scan', 'test']

    # helper method to search permissions.sites
    def site_in_sites(id) -> bool:
        if len(member.permissions.get('sites', [])) == 0:
            return True
        for site in member.permissions.get('sites'):
            if id == site['id']:
                return True
        return False


    # check action with permissions
    if action not in member.permissions.get('actions'):
        return {
            'allowed': False,
            'error': error,
            'code': code,
            'status': _status
        }


    # check resource with permissions
    if resource not in member.permissions.get('resources'):
        return {
            'allowed': False,
            'error': error,
            'code': code,
            'status': _status
        }


    # check id 
    if id and id_type:

        # create obj_str
        obj_str = id_type.capitalize()
        if 'run' in obj_str:
            obj_str = obj_str.replace('run', 'Run')

        # retrieve obj
        if id_type not in ['scan', 'test']:
            objs = eval(f'{obj_str}.objects.filter(id="{id}", account__id="{account.id}")')
        if id_type in ['scan', 'test']:
            objs = eval(f'{obj_str}.objects.filter(id="{id}", site__account__id="{account.id}")')
        
        # return False if not found
        if len(objs) == 0:
            return {
                'allowed': False,
                'error': f'{resource} not found',
                'code': '404',
                'status': status.HTTP_404_NOT_FOUND
            }


    # check for site association
    if (id and id_type) and id_type not in ignore_list:

        # special case for `Issue`
        if id_type == 'issue':
            affected_type = objs[0].affected.get('type') 

            if affected_type == 'site':
                # check site in permissions.sites
                if not site_in_sites(objs[0].affected.get('id')):
                    return {
                        'allowed': False,
                        'error': error,
                        'code': code,
                        'status': _status
                    }
            
            if affected_type == 'page':
                # check page.site in permissions.sites
                try:
                    page = Page.objects.get(id=objs[0].affected.get('id'))
                    if not site_in_sites(str(page.site.id)):
                        return {
                            'allowed': False,
                            'error': error,
                            'code': code,
                            'status': _status
                        }
                except:
                    return {
                        'allowed': False,
                        'error': f'{resource} not found',
                        'code': '404',
                        'status': status.HTTP_404_NOT_FOUND
                    }

        # check site in permissions.sites
        elif id_type == 'site':
            if not site_in_sites(str(objs[0].id)):
                return {
                    'allowed': False,
                    'error': error,
                    'code': code,
                    'status': _status
                }

        # check associated site in permissions.sites
        else:
            if not site_in_sites(str(objs[0].site.id)):
                return {
                    'allowed': False,
                    'error': error,
                    'code': code,
                    'status': _status
                }


    # handle special cases for site and page
    if resource == 'site' or resource == 'page':
        # check existance
        if url:
            if eval(f'{resource.capitalize()}.objects.filter(account__id="{account.id}", {resource}_url="{url}").exists()'):
                return {
                    'allowed': False,
                    'error': f'{resource} exists',
                    'code': '409',
                    'status': status.HTTP_409_CONFLICT
                }

        # check usage for page only
        if resource == 'page' and id_type == 'site' and action == 'add':
            if account.usage['pages_allowed'] == Page.objects.filter(site__id=id).count():
                return {
                    'allowed': False,
                    'error': f'max pages reached',
                    'code': '426',
                    'status': status.HTTP_426_UPGRADE_REQUIRED
                }
            

    # check for cloud / enterprise plan
    if (account.type == 'enterprise' or account.type == 'cloud') and resource == 'site':
        
        # add to sites_allowed only for enterprise and cloud plans
        if action == 'add' and account.usage['sites_allowed'] == Site.objects.filter(account=account).count():
            account.usage['sites_allowed'] += 1
            account.usage['schedules_allowed'] += 1
            account.save()
            # update price for sub
            update_sub_price.delay(account.id)


    # check usage if action is 'add'
    if action == 'add' and resource in usage_list:

        # check if usage allows for add
        if int(account.usage[f'{resource}s']) >= int(account.usage[f'{resource}s_allowed']):
            return {
                'allowed': False,
                'error': f'max {resource}s reached',
                'code': '426',
                'status': status.HTTP_426_UPGRADE_REQUIRED
            }
        
    # return True
    return {
        'allowed': True,
        'error': None,
        'code': '201' if action == 'add' else '200',
        'status': status.HTTP_201_CREATED if action == 'add' else status.HTTP_200_OK
    }




### ------ Begin Site Services ------ ###




def create_site(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account
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
    check_data = check_permissions_and_usage(
        member=member, resource='site', action='add',
        url=site_url
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
    
    # updated accounts usage
    account.usage['sites'] += 1
    account.save()

    # create process obj
    process = Process.objects.create(
        site=site,
        type='case.generate',
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




def crawl_site(request: object=None, id: str=None, user: object=None) -> object:
    """ 
    Initiates a new Crawl for the passed `Site`.id

    Expects: {
        'request' : object, 
        'id'      : str,
        'user'    : object
    }
    
    Returns -> HTTP Response object
    """

    # get user and account
    if request:
        user = request.user

    member = Member.objects.get(user=user)
    account = member.account
    configs = request.data.get('configs', None)

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='site', action='get', 
        id=id, id_type='site'
    )
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




def get_sites(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check if site_id was passed
    if site_id != None:

        # check account and resource
        check_data = check_permissions_and_usage(
            member=member, resource='site', action='get', id=site_id, id_type='site'
        )
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

    # filter out all non permissioned sites
    if len(member.permissions.get('sites', [])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        sites = sites.filter(id__in=id_list).order_by('-time_created')

    # serialize response and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(sites, request)
    serializer_context = {'request': request,}
    serialized = SiteSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_site(request: object=None, id: str=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='site', action='get', 
        id=id, id_type='site'
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




def delete_site(request: object=None, id: str=None, user: object=None) -> object:
    """ 
    Deletes the `Site` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str,
        'user'    : object,
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    if request:
        user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='site', 
        action='delete', id=id, id_type='site'
    )
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
    delete_tasks_and_schedules(resource_id=str(site.id), scope='site', account=account)

    # remove any site associated Issues
    Issue.objects.filter(affected__icontains=str(id)).delete()

    # remove any page associated Issues
    for page in Page.objects.filter(site=site):
        Issue.objects.filter(affected__icontains=str(page.id)).delete()
    
    # remove site
    site.delete()

    # decrememt resouce in account
    decrement_resource(account=account, resource='sites')

    # update account if enterprise or cloud
    if account.type == 'enterprise' or account.type == 'cloud':
        account.usage['sites_allowed'] -= 1
        account.usage['schedules_allowed'] -= 1
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




def delete_many_sites(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

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
                # delete site and associated resources
                data = delete_site(id=id, user=user)
                if data.get('reason'):
                    raise Exception(data['reason'])

                # add to success attempts
                num_succeeded += 1
                succeeded.append(str(id))

            except Exception as e:
                print(e)
                # add to failed attempts
                num_failed += 1
                failed.append(str(id))
                this_status = False

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




def get_sites_zapier(request: object=None) -> object:
    """ 
    Get all `Sites` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account
    sites = None
    
    # deciding on scope
    resource = 'site'

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource=resource, action='get',
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        return Response(data, status=check_data['status'])

    # get all account assocoiated sites
    if sites is None:
        sites = Site.objects.filter(
            account=account,
        ).order_by('-time_created')

    # filter out all non permissioned sites
    if len(member.permissions.get('sites', [])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        sites = sites.filter(id__in=id_list).order_by('-time_created')

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




def create_page(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account
    site = Site.objects.get(id=site_id)

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # creating many pages if page_urls was passed
    if page_urls is not None:
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
    check_data = check_permissions_and_usage(
        member=member, resource='page', action='add', 
        id=site_id, id_type='site', url=page_url,
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
    member = Member.objects.get(user=user)
    account = member.account

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # get site and current pages
    site = Site.objects.get(id=site_id)
    pages = Page.objects.filter(site=site)

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='page', action='add', 
        id=site_id, id_type='site'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        if http_response:
            return Response(data, status=check_data['status'])
        return data

    # pre check for max_pages
    if (pages.count() + len(page_urls)) > account.usage['pages_allowed']:
        print('max pages reached')
        data = {'reason': 'max pages reached',}
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

    
    

def get_pages(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check for params
    if page_id is None and site_id is None:
        data = {'reason': 'neet site or page id'}
        record_api_call(request, data, '400')
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='page', action='get', 
        id=(site_id if site_id else page_id), 
        id_type=('site' if site_id else 'page')
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




def get_page(request: object=None, id: str=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='page', action='get', 
        id=id, id_type='page'
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




def delete_page(request: object=None, id: str=None, user: object=None) -> object:
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
        user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='page', 
        action='delete', id=id, id_type='page'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        print(data)
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # get page by id
    page = Page.objects.get(id=id)

    # remove s3 objects
    delete_page_s3_bg.delay(page_id=id, site_id=page.site.id)

    # remove any schedules and associated tasks
    delete_tasks_and_schedules(resource_id=str(page.id), scope='page', account=account)

    # remove any associated Issues
    Issue.objects.filter(affected__icontains=str(id)).delete()

    # remove page
    page.delete()

    # format and return
    data = {'message': 'Page has been deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data




def delete_many_pages(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

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

            # trying to delete page
            try:
                # delete page and all assocaited resourses
                data = delete_page(id=id, user=user)
                if data.get('reason'):
                    raise Exception

                # add to success attempts
                num_succeeded += 1
                succeeded.append(str(id))
            except Exception as e:
                # add to failed attempts
                print(e)
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




def get_pages_zapier(request: object=None) -> object:
    """ 
    Get all `Pages` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    member = Member.objects.get(user=request.user)
    account = member.account
    site_id = request.query_params.get('site_id')
    pages = None
    
    # deciding on scope
    resource = 'page'

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource=resource, action='get',
        id=site_id, id_type='site'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
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

        # filter out all non permissioned sites
        if len(member.permissions.get('sites',[])) != 0:
            id_list = [item['id'] for item in member.permissions.get('sites')]
            pages = pages.filter(site__id__in=id_list)

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




def create_scan(request: object=None, **kwargs) -> object:
    """ 
    Create one or more `Scans` depanding on 
    `Page` or `Site` scope

    Expects: {
        'request': object, 
    }

    Returns -> dict or HTTP Response object
    """

    # check location
    location_data = check_location(request, None)
    if location_data['routed']:
        return location_data['response']

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
    member = Member.objects.get(user=user)
    account = member.account

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # checking args
    site_id = '' if site_id is None else site_id
    page_id = '' if page_id is None else page_id
    site_id = site_id if len(str(site_id)) > 0 else None
    page_id = page_id if len(str(page_id)) > 0 else None
    id = site_id if site_id else page_id
    id_type = 'site' if site_id else 'page'

    # verifying types
    if len(types) == 0:
        types = settings.TYPES

    # check account and resource for site or page
    check_data = check_permissions_and_usage(
        member=member, resource='scan', action='add', 
        id=id, id_type=id_type
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
        check_data = check_permissions_and_usage(
            member=member, resource='scan', action='add',
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

        # setting format for timestamp
        f = '%Y-%m-%d %H:%M:%S.%f'
        timestamp = datetime.today().strftime(f)

        # updating latest_scan info for page
        p.info['latest_scan']['id'] = str(created_scan.id)
        p.info['latest_scan']['time_created'] = timestamp
        p.info['latest_scan']['time_completed'] = None
        p.info['latest_scan']['score'] = None
        p.info['latest_scan']['score'] = None
        p.save()

        # updating latest_scan info for site
        p.site.info['latest_scan']['id'] = str(created_scan.id)
        p.site.info['latest_scan']['time_created'] = timestamp
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




def create_many_scans(request: object=None) -> object:
    """ 
    Bulk creates `Scans` for each requested `Page`.
    Either scoped for many `Pages` or many `Sites`.

    Expcets: {
        'request' : object,
    }

    Returns -> HTTP Response object
    """

    # check location
    location_data = check_location(request, None)
    if location_data['routed']:
        return location_data['response']

    # get request data
    site_ids = request.data.get('site_ids')
    page_ids = request.data.get('page_ids')
    configs = request.data.get('configs', None)
    types = request.data.get('type', settings.TYPES)
    tags = request.data.get('tags')
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

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
                res = create_scan(**data)
                if res['success']:
                    num_succeeded += 1
                    succeeded.append(str(id))
                else:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))
                    print(res['reason'])
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
                res = create_scan(**data)
                if res['success']:
                    num_succeeded += 1
                    succeeded.append(str(id))
                else:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))
                    print(res['reason'])
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




def get_scans(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account
    
    # deciding on scope
    id = page_id if page_id else scan_id
    id_type = 'page' if page_id else 'scan'

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='scan', 
        action='get', id=id, id_type=id_type
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




def get_scan(request: object=None, id: str=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='scan', action='get',
        id=id, id_type='scan'
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




def get_scan_lean(request: object=None, id: str=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='scan', action='get',
        id=id, id_type='scan'
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




def delete_scan(request: object=None, id: str=None, user: object=None) -> object:
    """ 
    Deletes the `Scan` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str,
        'account' : object,
        'user'    : object
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    if request:
        user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='scan', action='delete',
        id=id, id_type='scan'
    )
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

    # update page and site
    update_site_and_page_info.delay(
        resource='scan',
        page_id=str(scan.page.id)
    )

    # delete scan
    scan.delete()

    # return response
    data = {'message': 'Scan has been deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data




def delete_many_scans(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

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
                # delete scan and all assocaited resourses
                data = delete_scan(id=id, user=user)
                if data.get('reason'):
                    raise Exception

                # add to success attempts
                num_succeeded += 1
                succeeded.append(str(id))
            except Exception as e:
                # add to failed attempts
                print(e)
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




def get_scans_zapier(request: object=None) -> object: 
    """ 
    Get all `Scans` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    member = Member.objects.get(user=request.user)
    account = member.account
    page_id = request.query_params.get('page_id')
    site_id = request.query_params.get('site_id')
    id = page_id if page_id else site_id
    id_type = 'page' if page_id else 'site'
    scans = None
    
    # deciding on scope
    resource = 'scan'

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource=resource, 
        action='get', id=id, id_type=id_type
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
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

    # get all account assocoiated scans
    if scans is None:
        scans = Scan.objects.filter(
            site__account=account,
        ).exclude(
            time_completed=None,
        ).order_by('-time_created')

    # filter out all non permissioned sites
    if len(member.permissions.get('sites',[])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        scans = scans.filter(site__id__in=id_list).order_by('-time_created')

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




def create_test(request: object=None, **kwargs) -> object:
    """ 
    Create one or more `Tests` depanding on 
    `Page` or `Site` scope

    Expects: {
        'request': object, 
        'delay': bool
    }

    Returns -> dict or HTTP Response object
    """

    # check location
    location_data = check_location(request, None)
    if location_data['routed']:
        return location_data['response']

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
    member = Member.objects.get(user=user)
    account = member.account

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
    id = site_id if site_id else page_id
    id_type = 'site' if site_id else 'page'

    # check account and resource for page or site
    check_data = check_permissions_and_usage(
        member=member, resource='test', action='add', 
        id=id, id_type=id_type
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
        check_data = check_permissions_and_usage(
            member=member, action='add', resource='test'
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

        # setting format for timestamp
        f = '%Y-%m-%d %H:%M:%S.%f'
        timestamp = datetime.today().strftime(f)

        # updating latest_test info for page
        p.info['latest_test']['id'] = str(test.id)
        p.info['latest_test']['time_created'] = timestamp
        p.info['latest_test']['time_completed'] = None
        p.info['latest_test']['score'] = None
        p.info['latest_test']['status'] = 'working'
        p.save()

        # updating latest_test info for site
        p.site.info['latest_test']['id'] = str(test.id)
        p.site.info['latest_test']['time_created'] = timestamp
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




def create_many_tests(request: object=None) -> object:
    """ 
    Bulk creates `Tests` for each requested `Page`.
    Either scoped for many `Pages` or many `Sites`.

    Expcets: {
        'request' : object,
    }

    Returns -> HTTP Response object
    """

    # check location
    location_data = check_location(request, None)
    if location_data['routed']:
        return location_data['response']

    # get request data
    site_ids = request.data.get('site_ids')
    page_ids = request.data.get('page_ids')
    configs = request.data.get('configs', None)
    threshold = request.data.get('threshold', settings.TEST_THRESHOLD)
    types = request.data.get('type', settings.TYPES)
    tags = request.data.get('tags')
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

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
                res = create_test(**data)
                if res['success']:
                    num_succeeded += 1
                    succeeded.append(str(id))
                else:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))
                    print(res['reason'])
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
                res = create_test(**data)
                if res['success']:
                    num_succeeded += 1
                    succeeded.append(str(id))
                else:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))
                    print(res['reason'])
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
    



def get_tests(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account
    
    # deciding on scope
    id = test_id if test_id else page_id
    id_type = 'page' if page_id else 'test'

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='test', 
        action='add',id=id, id_type=id_type
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




def get_test(request: object=None, id: str=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='test',
        action='get', id=id, id_type='test'
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




def get_test_lean(request: object=None, id: str=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='test',
        action='get', id=id, id_type='test'
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




def delete_test(request: object=None, id: str=None, user: object=None) -> object:
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
        user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='test',
        action='delete', id=id, id_type='test'
    )
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

    # update site and page with most recent data
    update_site_and_page_info.delay(
        resource='test',
        page_id=str(test.page.id)
    )

    # delete test
    test.delete()
    
    # return response
    data = {'message': 'Test has been deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data




def delete_many_tests(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

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

            # trying to delete test
            try:
                # delete test and all assocaited resourses
                data = delete_test(id=id, user=user)
                if data.get('reason'):
                    raise Exception

                # add to success attempts
                num_succeeded += 1
                succeeded.append(str(id))
            except Exception as e:
                # add to failed attempts
                print(e)
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




def get_tests_zapier(request: object=None) -> object:
    """ 
    Get all `Tests` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    member = Member.objects.get(user=request.user)
    account = member.account
    page_id = request.query_params.get('page_id')
    site_id = request.query_params.get('site_id')
    id = page_id if page_id else site_id
    id_type = 'page' if page_id else 'site'
    _status = request.query_params.get('status')
    tests = None
    
    # deciding on scope
    resource = 'test'

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource=resource, 
        action='get', id=id, id_type=id_type
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
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

    # filter out all non permissioned sites
    if len(member.permissions.get('sites',[])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        tests = tests.filter(site__id__in=id_list).order_by('-time_created')

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
        user = request.user
        member = Member.objects.get(user=user)
        account = member.account
    
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
        user_id = kwargs.get('user_id')
        user = User.objects.get(id=user_id)
        member = Member.objects.get(user=user)
        account = Account.objects.get(id=account_id)

    # decide on action
    action = 'update' if id else 'add'

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='issue', 
        action=action, id=id, id_type='issue'
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
    data = {
        'success': True, 
        'issue': issue,
    }
    return data




def update_many_issues(request: object=None) -> object:
    """ 
    Updates many `Issues` passed in a list

    Expects: {
        'ids'     : list
        'updates' : dict
    }
    
    Returns -> HTTP Response object
    """
    
    #  get request data
    ids = request.data.get('ids')
    updates = request.data.get('updates')
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # set defaults
    num_succeeded = 0
    succeeded = []
    num_failed = 0
    failed = []
    this_status = True

    # loop through ids and update
    for id in ids:
        # reformat update data
        data = updates
        data['id'] = str(id)
        data['account_id'] = str(account.id)
        data['user_id'] = str(user.id)

        # send update
        try:
            data = create_or_update_issue(**data)
            if data.get('reason'):
                raise Exception
            
            # add to success attempts
            num_succeeded += 1
            succeeded.append(str(id))

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
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def get_issues(request: object=None) -> object:
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
    
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account
    issues = None
    
    # deciding on scope
    resource = 'issue'
    id = issue_id if issue_id else (site_id if site_id else page_id)
    id_type = 'issue' if issue_id else ('site' if site_id else 'page')

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource=resource, action='get',
        id=id, id_type=id_type,
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

    # filter out all non permissioned sites
    if len(member.permissions.get('sites',[])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        new_ids = id_list
        for id in id_list:
            for page in Page.objects.filter(site__id=id):
                new_ids.append(str(page.id))
        issues = issues.filter(affected__id__in=new_ids).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(issues, request)
    serializer_context = {'request': request,}
    serialized = IssueSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_issue(request: object=None, id: str=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='issue', action='get', 
        id=id, id_type='issue'
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




def search_issues(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account
    query = request.query_params.get('query')

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='issue', action='get'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    
    # search for issues
    issues = Issue.objects.filter(
        Q(account=account, title__icontains=query) |
        Q(account=account, details__icontains=query) |
        Q(account=account, affected__icontains=query)
    ).order_by('-status', '-time_created')

    # filter out all non permissioned sites
    if len(member.permissions.get('sites',[])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        new_ids = id_list
        for id in id_list:
            for page in Page.objects.filter(site__id=id):
                new_ids.append(str(page.id))
        issues = issues.filter(affected__id__in=new_ids).order_by('-time_created')
    
    # serialize and rerturn
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(issues, request)
    serializer_context = {'request': request,}
    serialized = IssueSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response 




def delete_issue(request: object=None, id: str=None, user: object=None) -> object:
    """ 
    Deletes the `Issue` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    if request:
        user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='issue', action='delete',
        id=id, id_type='issue',
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # get issue if checks passed
    issue = Issue.objects.get(id=id)

    # delete test
    issue.delete()

    # return response
    data = {'message': 'Issue has been deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data
    



def delete_many_issues(request: object=None) -> object:
    """ 
    Deletes many `Issues` passed in a list

    Expects: {
        'ids': list
    }
    
    Returns -> HTTP Response object
    """
    
    #  get request data
    ids = request.data.get('ids')
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # set defaults
    num_succeeded = 0
    succeeded = []
    num_failed = 0
    failed = []
    this_status = True

    # loop through ids and delete
    for id in ids:

        # trying to delete issue
        try:
            # delete issue and all assocaited resourses
            data = delete_issue(id=id, user=user)
            if data.get('reason'):
                raise Exception

            # add to success attempts
            num_succeeded += 1
            succeeded.append(str(id))
        except Exception as e:
            # add to failed attempts
            print(e)
            num_failed += 1
            failed.append(str(id))
            this_status = False

    # format and return
    data = {
        'success': this_status,
        'num_succeeded': num_succeeded,
        'succeeded': succeeded,
        'num_failed': num_failed,
        'failed': failed, 
    }
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def get_issues_zapier(request: object=None) -> object:
    """ 
    Get all `Issues` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    member = Member.objects.get(user=request.user)
    account = member.account
    page_id = request.query_params.get('page_id')
    site_id = request.query_params.get('site_id')
    id = page_id if page_id else site_id
    id_type = 'page' if page_id else 'site'
    issues = None
    
    # deciding on scope
    resource = 'issue'

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource=resource, 
        action='get', id=id, id_type=id_type
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
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

    # filter out all non permissioned sites
    if len(member.permissions.get('sites',[])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        new_ids = id_list
        for id in id_list:
            for page in Page.objects.filter(site__id=id):
                new_ids.append(str(page.id))
        issues = issues.filter(affected__id__in=new_ids).order_by('-time_created')

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




def create_or_update_schedule(request: object=None, **kwargs) -> object:
    """ 
    Creates or Updates a `Schedule` 

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    if request:
        schedule_status = request.data.get('status')
        begin_date_raw = request.data.get('begin_date')
        time = request.data.get('time')
        timezone = request.data.get('timezone')
        freq = request.data.get('frequency')
        task_type = request.data.get('task_type')
        types = request.data.get('type', settings.TYPES)
        configs = request.data.get('configs', None)
        threshold = request.data.get('threshold', settings.TEST_THRESHOLD)
        schedule_id = request.data.get('schedule_id')
        resources = request.data.get('resources')
        scope = request.data.get('scope')
        case_id = request.data.get('case_id')
        flow_id = request.data.get('flow_id')
        updates = request.data.get('updates')
        user = request.user
    
    if not request:
        schedule_status = kwargs.get('status')
        begin_date_raw = kwargs.get('begin_date')
        time = kwargs.get('time')
        timezone = kwargs.get('timezone')
        freq = kwargs.get('frequency')
        task_type = kwargs.get('task_type')
        types = kwargs.get('type', settings.TYPES)
        configs = kwargs.get('configs', None)
        threshold = kwargs.get('threshold', settings.TEST_THRESHOLD)
        schedule_id = kwargs.get('schedule_id')
        resources = kwargs.get('resources')
        scope = kwargs.get('scope')
        case_id = kwargs.get('case_id')
        flow_id = kwargs.get('flow_id')
        updates = kwargs.get('updates')
        user_id = kwargs.get('user_id')
        user = User.objects.get(id=user_id)
        

    # get account
    member = Member.objects.get(user=user)
    account = member.account

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # setting defaults
    schedule = None
    
    # deciding on action type
    action = 'add' if not schedule_id else 'update'

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='schedule', 
        action=action, id=schedule_id, id_type='schedule'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # get schedule if checks passed and id is present
    if schedule_id:
        schedule = Schedule.objects.get(id=schedule_id)

    # toggling schedule status
    if schedule_status != None and schedule != None:
        # update task
        task = PeriodicTask.objects.get(id=schedule.periodic_task_id)
        if schedule_status == 'Paused':
            task.enabled = False
        if schedule_status == 'Active':
            task.enabled = True
        # update schedule
        schedule.status = schedule_status
        task.save() 
        schedule.save()
    
    # creating or updating schedule
    if not schedule_status:

        # get alert if schedule exists
        alert_id = None
        if schedule:
            if Alert.objects.filter(schedule=schedule).exists():
                alert = Alert.objects.filter(schedule=schedule)[0]
                alert_id = str(alert.id)

        # build task
        task = f'api.tasks.create_{task_type}_bg'

        # build args
        arguments = {
            'scope': scope,
            'resources': resources,
            'account_id': str(account.id),
            'updates': updates,
            'configs': configs,
            'case_id': case_id,
            'flow_id': flow_id,
            'type': types,
            'threshold': threshold,
            'alert_id': alert_id,
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

        # create unique str for 
        rand_str = secrets.token_urlsafe(6)

        # building unique task name
        task_name = f'{task_type}_{scope}_{rand_str}_{freq}_@{time}_{account.user.id}'

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
                
                # grabbing task_id
                arguments['task_id'] = str(periodic_task[0].id)
               
                # updating task with args
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
                data = {'reason': 'Schedule already exists', 'code': '401'}
                if request:
                    record_api_call(request, data, '401')
                    return Response(data, status=status.HTTP_401_UNAUTHORIZED)
                return data

            # create new periodic task 
            periodic_task = PeriodicTask.objects.create(
                crontab=crontab, 
                name=task_name, 
                task=task,   
            )
            
            # inserting task_id
            arguments['task_id'] = str(periodic_task.id)
            
            # updating args
            periodic_task.kwargs = json.dumps(arguments)
            periodic_task.save()

        # building extras for scheduls
        extras = {
            "configs": configs,
            "type": types,
            "case_id": case_id, 
            "flow_id": flow_id, 
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
            if resources is not None:
                schedule.resources = resources
            
            # save udpdates
            schedule.save()

        # create new schedule
        if not schedule:
            schedule = Schedule.objects.create(
                user=request.user, 
                scope=scope,
                resources=resources, 
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

            # updated accounts usage
            account.usage['schedules'] += 1
            account.save()

    # deciding on response type
    if request:
        # serialize and return
        serializer_context = {'request': request,}
        data = ScheduleSerializer(schedule, context=serializer_context).data
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    
    # return object response
    data = {
        'success': True, 
        'schedule': schedule,
    }
    return data




def update_many_schedules(request: object=None) -> object:
    """ 
    Updates many `Schedules` passed in a list

    Expects: {
        'ids'     : list
        'updates' : dict
    }
    
    Returns -> HTTP Response object
    """
    
    #  get request data
    ids = request.data.get('ids')
    updates = request.data.get('updates')
    member = Member.objects.get(user=request.user)
    account = member.account

    # set defaults
    num_succeeded = 0
    succeeded = []
    num_failed = 0
    failed = []
    this_status = True

    # loop through ids and update
    for id in ids:
        # reformat update data
        data = updates
        data['schedule_id'] = str(id)
        data['user_id'] = str(request.user.id)

        # send update
        try:
            data = create_or_update_schedule(**data)
            if data.get('reason'):
                raise Exception(data['reason'])
            # add to success attempts
            num_succeeded += 1
            succeeded.append(str(id))

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
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def run_schedule(request: object=None) -> object:
    """
    Grabs all the args from the asociated perodic_task
    and executes the task manually without interupting
    the perodic_task's normal cycle.

    Expects: {
        requests: object
    } 

    Return -> HTTP Response object
    """

    # get request data
    schedule_id = request.data.get('schedule_id')

    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='schedule', 
        action='get', id=schedule_id, id_type='schedule'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get schedule and assocated task if checks passed
    schedule = Schedule.objects.get(id=schedule_id)
    task = schedule.task_type
    perodic_task = PeriodicTask.objects.get(id=schedule.periodic_task_id)
    task_kwargs = json.loads(perodic_task.kwargs)

    # check location
    local = schedule.extras['configs'].get('location', settings.LOCATION)
    location_data = check_location(request, local)
    if location_data['routed']:
        return location_data['response']

    # decidign on which task 
    if task == 'scan':
        # run create_scan_bg
        create_scan_bg.delay(
            **task_kwargs
        )
    if task == 'test':
        # run create_test_bg
        create_test_bg.delay(
            **task_kwargs
        )
    if task == 'caserun':
        # run create_caserun_bg
        create_caserun_bg.delay(
            **task_kwargs
        )
    if task == 'flowrun':
        # run create_flowrun_bg
        create_flowrun_bg.delay(
            **task_kwargs
        )
    if task == 'report':
        # run create_report_bg
        create_report_bg.delay(
            **task_kwargs
        )

    # serialize and return
    serializer_context = {'request': request,}
    data = ScheduleSerializer(schedule, context=serializer_context).data
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def get_schedules(request: object=None) -> object:
    """ 
    Get one or more `Schedules`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    schedule_id = request.query_params.get('schedule_id')
    scope = request.query_params.get('scope')
    resource_id = request.query_params.get('resource_id')
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # setting default
    schedules = None

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='schedule', 
        action='get', id=schedule_id, id_type='schedule'
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

    # get all account scoped schedules
    if scope == 'account':
        schedules = Schedule.objects.filter(
            account=account,
            scope='account'
        ).order_by('-time_created')

    # get all non account scoped
    if scope != 'account' and resource_id is None:
        schedules = Schedule.objects.filter(
            account=account,
            scope=scope
        ).order_by('-time_created')
    
    # get all non account scoped schedules with resource_id
    if scope != 'account' and resource_id:
        schedules = Schedule.objects.filter(
            account=account,
            resources__icontains=resource_id,
            scope=scope
        ).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(schedules, request)
    serializer_context = {'request': request,}
    serialized = ScheduleSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_schedule(request: object=None, id: str=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='schedule', 
        action='get', id=id, id_type='schedule'
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




def delete_schedule(request: object=None, id: str=None, user: object=None) -> object:
    """ 
    Deletes the `Schedule` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str,
        'user'    : object
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    if request:
        user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='schedule',
        action='delete', id=id, id_type='schedule'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # get schedule and task if checks passed
    schedule = Schedule.objects.get(id=id)
    task = PeriodicTask.objects.get(id=schedule.periodic_task_id)

    # delete schedule
    schedule.delete()

    # delete task
    task.delete()

    # decrement resource
    decrement_resource(account=account, resource='schedules')

    # return response
    data = {'message': 'Schedule has been deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data




def delete_many_schedules(request: object=None) -> object:
    """ 
    Deletes many `Schedules` passed in a list

    Expects: {
        'ids': list
    }
    
    Returns -> HTTP Response object
    """
    
    #  get request data
    ids = request.data.get('ids')
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # set defaults
    num_succeeded = 0
    succeeded = []
    num_failed = 0
    failed = []
    this_status = True

    # loop through ids and delete
    for id in ids:

        # trying to delete schedule
        try:
            # delete issue and all assocaited resourses
            data = delete_schedule(id=id, user=user)
            if data.get('reason'):
                raise Exception

            # add to success attempts
            num_succeeded += 1
            succeeded.append(str(id))
        except Exception as e:
            # add to failed attempts
            print(e)
            num_failed += 1
            failed.append(str(id))
            this_status = False

    # format and return
    data = {
        'success': this_status,
        'num_succeeded': num_succeeded,
        'succeeded': succeeded,
        'num_failed': num_failed,
        'failed': failed, 
    }
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def delete_tasks_and_schedules(
        resource_id : str=None, 
        scope       : object=None, 
        account     : object=None
    ) -> None:
    """ 
    Helper function to delete any `Schedules` & `PerodicTasks`
    associated with the passed "resource_id", "scope", and 
    "account"

    Expects: {
        'resource_id'   : str, 
        'scope'         : str
        'account'       : object
    }

    Returns -> None
    """ 
    # get all scopped Schedules
    schedules = Schedule.objects.filter(
        resources__icontains=resource_id,
        account=account,
        scope=scope 
    )

    # remove any associated tasks
    for schedule in schedules:
        task = PeriodicTask.objects.get(id=schedule.periodic_task_id)
        try:
            task.delete()
        except Exception as e:
            print(e)
    
    # delete Schedules
    schedules.delete()
    
    return None




### ------ Begin Alert Services ------ ###




def create_or_update_alert(request: object=None) -> object:
    """ 
    Creates or Updates an `Alert` 

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """
    
    # get request data
    actions = request.data.get('actions')
    schedule_id = request.data.get('schedule_id')
    alert_id = request.data.get('alert_id')
    name = request.data.get('name')
    expressions = request.data.get('expressions')

    # set defaults
    alert = None
    schedule = None
    
    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # deciding on recsource
    id = alert_id if alert_id else schedule_id
    id_type = 'alert' if alert_id else 'schedule'
    action = 'add' if schedule_id else 'update'

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='alert', 
        action=action, id=id, id_type=id_type,
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get schedule if checks passed
    if schedule_id:
        schedule = Schedule.objects.get(id=schedule_id)
    if alert_id:
        alert = Alert.objects.get(id=alert_id)
        schedule = alert.schedule

    # update existing alert
    if alert:
        if name:
            alert.name = name
        if expressions:
            alert.expressions = expressions
        if actions:
            alert.actions = actions
        if schedule:
            alert.schedule = schedule
        # save updates
        alert.save()

    # create new alert
    if not alert:
        alert = Alert.objects.create(
            name=name, 
            expressions=expressions, 
            actions=actions,
            schedule=schedule, 
            user=user, 
            account=account
        )

    # update schedule 
    if schedule:

        # update schedule with new alert
        schedule.alert = alert
        schedule.save()

        # update associated periodicTask
        task = PeriodicTask.objects.get(id=schedule.periodic_task_id)

        # update periodic task
        arguments = {
            'scope': json.loads(task.kwargs).get('scope'),
            'resources': json.loads(task.kwargs).get('resources'),
            'account_id': json.loads(task.kwargs).get('account_id'),
            'alert_id': str(alert.id),
            'configs': json.loads(task.kwargs).get('configs'), 
            'type': json.loads(task.kwargs).get('type'),
            'threshold': json.loads(task.kwargs).get('threshold'),
            'case_id': json.loads(task.kwargs).get('case_id'),
            'flow_id': json.loads(task.kwargs).get('flow_id'),
            'updates': json.loads(task.kwargs).get('updates'),
            'task_id': json.loads(task.kwargs).get('task_id'),
        }
        task.kwargs=json.dumps(arguments)
        task.save()

    # serialize and return
    serializer_context = {'request': request,}
    data = AlertSerializer(alert, context=serializer_context).data
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response

    


def get_alerts(request: object=None) -> object:
    """ 
    Get one or more `Alerts`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    alert_id = request.query_params.get('alert_id')
    
    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='alert', 
        action='get', id=alert_id, id_type='alert'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get single alert
    if alert_id:        
        
        # get alert
        alert = Alert.objects.get(id=alert_id)
        
        # serialize and return
        serializer_context = {'request': request,}
        serialized = AlertSerializer(alert, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)
    
    # get all alerts associated with account
    alerts = Alert.objects.filter(account=account).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(alerts, request)
    serializer_context = {'request': request,}
    serialized = AlertSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_alert(request: object=None, id: str=None) -> object:
    """
    Get single `Alert` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='alert', 
        action='get', id=id, id_type='alert'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get alert if checks passed
    alert = Alert.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = AlertSerializer(alert, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def delete_alert(request: object=None, id: str=None) -> object:
    """ 
    Deletes the `Alert` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='alert', 
        action='delete', id=id, id_type='alert'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get alert if checks passed
    alert = Alert.objects.get(id=id)

    # delete alert
    alert.delete()

    # return response
    data = {'message': 'Alert has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Report Services ------ ###




def create_or_update_report(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    id = report_id if report_id else page_id
    id_type = 'report' if report_id else 'page'
    action = 'update' if report_id else 'add'

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='report', 
        action=action, id=id, id_type=id_type
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




def get_reports(request: object=None) -> object:
    """ 
    Get one or more `Reports`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    page_id = request.query_params.get('page_id')
    report_id = request.query_params.get('report_id')
    
    # get user and account
    user = request.user 
    member = Member.objects.get(user=user)
    account = member.account

    id = report_id if report_id else page_id
    id_type = 'report' if report_id else 'page'

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='report', 
        action='add', id=id, id_type=id_type
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

    # filter out all non permissioned sites
    if len(member.permissions.get('sites',[])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        reports = reports.filter(site__id__in=id_list).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(reports, request)
    serializer_context = {'request': request,}
    serialized = ReportSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_report(request: object=None, id: str=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='report', 
        action='get', id=id, id_type='report'
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




def delete_report(request: object=None, id: str=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='report', 
        action='delete', id=id, id_type='report'
    )
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




def export_report(request: object=None) -> object:
    """
    Used to create and send a Cursion.landing 
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




def create_or_update_case(request: object=None) -> object:
    """ 
    Creates or Updates a `Case` 

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    case_id = request.data.get('case_id')
    steps = request.data.get('steps')
    site_url = request.data.get('site_url')
    site_id = request.data.get('site_id')
    title = request.data.get('title')
    tags = request.data.get('tags')
    _type = request.data.get('type')
    
    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # setting defaults
    site = None
    case = None
    action = 'update' if case_id else 'add'

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='case', 
        action=action, id=case_id, id_type='case'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])
    
    # get site if site_url passed
    if site_url:
        if Site.objects.filter(account=account, site_url=site_url).exists():
            site = Site.objects.filter(account=account, site_url=site_url)[0]
    
    # get site if site_id passed
    if site_id:
        if Site.objects.filter(account=account, id=site_id).exists():
            site = Site.objects.get(id=site_id)
            site_url = site.site_url

    # check for no site and no case_id
    if not site and not case_id:
        data = {'reason': 'site not found'}
        record_api_call(request, data, '404')
        response = Response(data, status=status.HTTP_404_NOT_FOUND)

    # get case if checks passed
    if case_id:
        case = Case.objects.get(id=case_id)

    # update Case   
    if case:
        if steps is not None:
            steps_data = save_case_steps(steps, case_id)
            case.steps = steps_data
        if title is not None:
            case.title = title
        if tags is not None:
            case.tags = tags
        if site is not None:
            case.site = site
        if site_url is not None:
            case.site_url = site_url
        # save updates
        case.save()
    
    # create Case
    if not case:

        # generate new uuid
        case_id = uuid.uuid4()

        # save step data in s3
        steps_data = save_case_steps(steps, case_id)
        
        # create new Case
        case = Case.objects.create(
            id = case_id,
            user = user,
            account = account,
            title = title, 
            type = _type if _type is not None else "recorded",
            site = site,
            site_url = site_url,
            steps = steps_data,
            
        )

        # create process obj
        process = Process.objects.create(
            site=site,
            type='case.pre_run',
            object_id=str(case.id),
            account=account,
            progress=1
        )

        # start pre_run for new Case
        case_pre_run_bg.delay(
            case_id=str(case.id),
            process_id=str(process.id)
        )

    # serialize and return
    serializer_context = {'request': request,}
    data = CaseSerializer(case, context=serializer_context).data
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response




def save_case_steps(steps: dict, case_id: str) -> dict:
    """ 
    Helper function that uploads the "steps" data to 
    s3 bucket

    Expects: {
        'steps'   : dict, 
        'case_id' : str
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
    steps_id = uuid.uuid4()
    with open(f'{steps_id}.json', 'w') as fp:
        json.dump(steps, fp)
    
    # seting up paths
    steps_file = os.path.join(settings.BASE_DIR, f'{steps_id}.json')
    remote_path = f'static/cases/{case_id}/{steps_id}.json'
    root_path = settings.AWS_S3_URL_PATH
    steps_url = f'{root_path}/{remote_path}'

    # upload to s3
    with open(steps_file, 'rb') as data:
        s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
            remote_path, ExtraArgs={
                'ACL': 'public-read', 
                'ContentType': 'application/json',
                'CacheControl': 'max-age=0'
            }
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




def get_cases(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # setting defaulta
    case = None
    site = None
    id = case_id if case_id else site_id
    id_type = 'case' if case_id else 'site'

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='case', 
        action='get', id=id, id_type=id_type
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

    # filter out all non permissioned sites
    if len(member.permissions.get('sites',[])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        cases = cases.filter(site__id__in=id_list).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(cases, request)
    serializer_context = {'request': request,}
    serialized = CaseSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_case(request: object=None, id: str=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='case', 
        action='get', id=id, id_type='case'
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




def search_cases(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account
    query = request.query_params.get('query')

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='case', action='get'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])
    
    # search for cases
    cases = Case.objects.filter(
        Q(account=account, title__icontains=query) |
        Q(account=account, site_url__icontains=query) 
    ).order_by('-time_created')

    # filter out all non permissioned sites
    if len(member.permissions.get('sites',[])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        cases = cases.filter(site__id__in=id_list).order_by('-time_created')
    
    # serialize and rerturn
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(cases, request)
    serializer_context = {'request': request,}
    serialized = CaseSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response 




def create_auto_cases(request: object=None) -> object:
    """
    Initiates a new `Case` generation task for the `Site` 
    associated with either the passed "site_url" or "site_id" 

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """
    
    # check location
    location_data = check_location(request, None)
    if location_data['routed']:
        return location_data['response']

    # get request data
    site_id = request.data.get('site_id')
    site_url = request.data.get('site_url')
    start_url = request.data.get('start_url')
    max_cases = request.data.get('max_cases', 4)
    max_layers = request.data.get('max_layers', 6)
    configs = request.data.get('configs', None)
    
    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # get site if only site_url present
    if site_url is not None:
        site = Site.objects.filter(account=account, site_url=site_url)[0]
        site_id = str(site.id)

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='case', 
        action='add', id=site_id, id_type='site'
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
        type='case.generate',
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




def copy_case(request: object=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='case', 
        action='add', id=case_id, id_type='case'
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
        id          = new_case_id,
        user        = user,
        account     = account,
        title       = f'Copy - {case.title}', 
        type        = case.type,
        site        = case.site,
        site_url    = case.site_url,
        steps       = steps_data,
        processed   = True
        
    )

    # return response
    serializer_context = {'request': request,}
    data = CaseSerializer(new_case, context=serializer_context).data
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response




def delete_case(request: object=None, id: str=None, user: object=None) -> object:
    """ 
    Deletes the `Case` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str,
        'user'    : object,
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    if request:
        user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='case', 
        action='delete', id=id, id_type='case'
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




def delete_many_cases(request: object=None) -> object:
    """ 
    Deletes many `Cases` passed in a list

    Expects: {
        'ids': list
    }
    
    Returns -> HTTP Response object
    """
    
    #  get request data
    ids = request.data.get('ids')
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # set defaults
    num_succeeded = 0
    succeeded = []
    num_failed = 0
    failed = []
    this_status = True

    # loop through ids and delete
    for id in ids:

        # trying to delete case
        try:
            # delete case and all assocaited resourses
            data = delete_case(id=id, user=user)
            if data.get('reason'):
                raise Exception

            # add to success attempts
            num_succeeded += 1
            succeeded.append(str(id))
        except Exception as e:
            # add to failed attempts
            print(e)
            num_failed += 1
            failed.append(str(id))
            this_status = False

    # format and return
    data = {
        'success': this_status,
        'num_succeeded': num_succeeded,
        'succeeded': succeeded,
        'num_failed': num_failed,
        'failed': failed, 
    }
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def get_cases_zapier(request: object=None) -> object:
    """ 
    Get all `Cases` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account
    site_id = request.query_params.get('site_id')
    cases = None
    
    # deciding on scope
    resource = 'case'

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource=resource, 
        action='get', id=site_id, id_type='site'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
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

    # filter out all non permissioned sites
    if len(member.permissions.get('sites',[])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        cases = cases.filter(site__id__in=id_list).order_by('-time_created')

    # build response data
    data = []

    for case in cases:
        data.append({
            'id'              :  str(case.id),
            'title'           :  case.title,
            'time_created'    :  str(case.time_created),
            'site'            :  str(case.site.id),
            'site_url'        :  case.site_url,
            'steps'           :  case.steps,
            'tags'            :  case.tags
        })

    # serialize and return
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin CaseRun Services ------ ###




def create_caserun(request: object=None) -> object:
    """ 
    Creates a new `CaseRun` from the passed "case_id" for the 
    passed "site_id"

    Expects: {
        'request': obejct
    }

    Returns -> HTTP Response object
    """

    # check location
    location_data = check_location(request, None)
    if location_data['routed']:
        return location_data['response']

    # get request data
    case_id = request.data.get('case_id')
    site_id = request.data.get('site_id')
    updates = request.data.get('updates')
    configs = request.data.get('configs', None)
    
    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # updating configs if None:
    configs = account.configs if configs == None else configs

    # check site
    if not Site.objects.filter(id=site_id, account=account).exists():
        data = {'reason': 'site not found'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='caserun', 
        action='add', id=case_id, id_type='case'
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

    # adding new info to steps for caserun
    for step in steps:
        # expanding action
        if step['action']['type'] != None:
            step['action']['time_created'] = None
            step['action']['time_completed'] = None
            step['action']['exception'] = None
            step['action']['status'] = None
            step['action']['img'] = None
        # expanding assertion
        if step['assertion']['type'] != None:
            step['assertion']['time_created'] = None
            step['assertion']['time_completed'] = None
            step['assertion']['exception'] = None
            step['assertion']['status'] = None

    # updating values if requested
    if updates != None:
        for update in updates:
            steps[int(update['index'])]['action']['value'] = update['value']

    # increment account.usage.caserun
    account.usage['caseruns'] += 1
    account.save()

    # create new tescase 
    caserun = CaseRun.objects.create(
        case = case,
        title = case.title,
        site = site,
        user = request.user,
        configs = configs, 
        steps = steps,
        account = account
    )

    # pass the newly created CaseRun to the backgroud task to run
    run_case.delay(caserun_id=caserun.id)

    # serialize and return
    data = {
        'id': str(caserun.id),
        'title': str(flowrun.title),
        'site': str(site.id),
        'time_created': str(caserun.time_created)
    }
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response




def get_caseruns(request: object=None) -> object:
    """ 
    Get one or more `CaseRun`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """
    
    # get request data
    caserun_id = request.query_params.get('caserun_id')
    site_id = request.query_params.get('site_id')
    lean = request.query_params.get('lean')

    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # defaults
    id = caserun_id if caserun_id else site_id
    id_type = 'caserun' if caserun_id else 'site'

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='caserun', 
        action='get', id=id, id_type=id_type
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get single caserun
    if caserun_id:        

        # get caserun
        caserun = CaseRun.objects.get(id=caserun_id)

        # serialize and return
        serializer_context = {'request': request,}
        serialized = CaseRunSerializer(caserun, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    # get caseruns scoped to site
    if site_id:
        site = Site.objects.get(id=site_id, account=account)
        caseruns = CaseRun.objects.filter(site=site).order_by('-time_created')
    
    # get caseruns scoped to account
    if not site_id:
        caseruns = CaseRun.objects.filter(account=account).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(caseruns, request)
    serializer_context = {'request': request,}
    serialized = CaseRunSerializer(result_page, many=True, context=serializer_context)
    if str(lean).lower() == 'true':
        serialized = SmallCaseRunSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_caserun(request: object=None, id: str=None) -> object:
    """
    Get single `CaseRun` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='caserun', 
        action='get', id=id, id_type='caserun'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get caserun if checks passed
    caserun = CaseRun.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = CaseRunSerializer(caserun, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def delete_caserun(request: object=None, id: str=None, user: object=None) -> object:
    """ 
    Deletes the `CaseRun` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str,
        'user' : object
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    if request:
        user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='caserun', 
        action='delete', id=id, id_type='caserun'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # get caserun if checks passed
    caserun = CaseRun.objects.get(id=id)

    # remove s3 objects
    delete_caserun_s3_bg.delay(caserun_id=id)

    # delete caserun
    caserun.delete()

    # return response
    data = {'message': 'CaseRun has been deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data




def get_caseruns_zapier(request: object=None) -> object:
    """ 
    Get all `CaseRuns` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    _status = request.query_params.get('status')
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account
    caseruns = None
    
    # deciding on scope
    resource = 'caserun'

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource=resource,
        action='get',
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        return Response(data, status=check_data['status'])

    # get all account assocoiated caseruns
    if caseruns is None:
        caseruns = CaseRun.objects.filter(
            account=account,
        ).exclude(
            time_completed=None,
        ).order_by('-time_created')

    # filter by _status if requested
    if _status is not None:
        caseruns = caseruns.filter(status=_status)

    # filter out all non permissioned sites
    if len(member.permissions.get('sites',[])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        caseruns = caseruns.filter(site__id__in=id_list).order_by('-time_created')
    
    # build response data
    data = []

    for caserun in caseruns:
        data.append({
            'id'              :  str(caserun.id),
            'case'            :  str(caserun.case.id),
            'title'           :  str(caserun.title),
            'site'            :  str(caserun.site.id),
            'time_created'    :  str(caserun.time_created),
            'time_completed'  :  str(caserun.time_completed),
            'configs'         :  caserun.configs,
            'status'          :  str(caserun.status),
        })

    # serialize and return
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Flow Services ------ ###




def create_or_update_flow(request: object=None) -> object:
    """ 
    Creates or Updates a `Flow` 

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    flow_id = request.data.get('flow_id')
    nodes = request.data.get('nodes')
    edges = request.data.get('edges')
    title = request.data.get('title')
    
    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # setting defaults
    flow = None
    action = 'update' if flow_id else 'add'

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='flow', 
        action=action, id=flow_id, id_type='flow'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get flow if checks passed
    if flow_id:
        flow = Flow.objects.get(id=flow_id)

    # update flow   
    if flow:
        if title is not None:
            flow.title = title
        if nodes is not None:
            flow.nodes = nodes
        if edges is not None:
            flow.edges = edges
        # save updates
        flow.save()
    
    # create Case
    if not flow:
        
        # create new Flow
        flow = Flow.objects.create(
            user = request.user,
            account = account,
            title = title if title is not None else 'Untitled Flow',  
        )

    # serialize and return
    serializer_context = {'request': request,}
    data = FlowSerializer(flow, context=serializer_context).data
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response




def get_flows(request: object=None) -> object:
    """ 
    Get one or more `Flows`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    flow_id = request.query_params.get('flow_id')
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # setting default
    flow = None

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='flow', 
        action='get', id=flow_id, id_type='flow'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get single flow
    if flow_id:        

        # get flow
        flow = Flow.objects.get(id=flow_id)

        # serialize and return
        serializer_context = {'request': request,}
        serialized = FlowSerializer(flow, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    # get flows scoped by account
    flows = Flow.objects.filter(account=account).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(flows, request)
    serializer_context = {'request': request,}
    serialized = FlowSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_flow(request: object=None, id: str=None) -> object:
    """
    Get single `Flow` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='flow', 
        action='get', id=id, id_type='flow'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get flow if checks passed
    flow = Flow.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = FlowSerializer(flow, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def search_flows(request: object=None) -> object:
    """ 
    Searches for matching `Flows` to the passed 
    "query"

    Expects: {
        'request': obejct
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account
    query = request.query_params.get('query')

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='flow', 
        action='get'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])
    
    # search for flows
    flows = Flow.objects.filter(
        Q(account=account, title__icontains=query)
    ).order_by('-time_created')
    
    # serialize and rerturn
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(flows, request)
    serializer_context = {'request': request,}
    serialized = FlowSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response 




def copy_flow(request: object=None) -> object:
    """ 
    Creates a copy of the passed `Flow`

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response obejct
    """

    # get request data
    flow_id = request.data.get('flow_id')

    # get user and acount
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='flow', 
        action='add', id=flow_id, id_type='flow'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get flow if checks passed
    if flow_id:
        flow = Flow.objects.get(id=flow_id, account=account)

    # create new flow
    new_flow = Flow.objects.create(
        user = request.user,
        account = account,
        title = f'Copy - {flow.title}', 
        nodes = flow.nodes,
        edges = flow.edges
    )

    # return response
    serializer_context = {'request': request,}
    data = FlowSerializer(new_flow, context=serializer_context).data
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response
    



def delete_flow(request: object=None, id: str=None, user: object=None) -> object:
    """ 
    Deletes the `Flow` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str,
        'user'    : object,
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    if request:
        user = request.user
    member = Member.objects.get(user=user)
    account = member.account
        
    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='flow', 
        action='delete', id=id, id_type='flow'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # get flow if checks passed
    flow = Flow.objects.get(id=id)

    # delete flow
    flow.delete()

    # return response
    data = {'message': 'Flow has been deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data




def delete_many_flows(request: object=None) -> object:
    """ 
    Deletes many `Flows` passed in a list

    Expects: {
        'ids': list
    }
    
    Returns -> HTTP Response object
    """
    
    #  get request data
    ids = request.data.get('ids')
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # set defaults
    num_succeeded = 0
    succeeded = []
    num_failed = 0
    failed = []
    this_status = True

    # loop through ids and delete
    for id in ids:

        # trying to delete flow
        try:
            # delete flow and all assocaited resourses
            data = delete_flow(id=id, user=user)
            if data.get('reason'):
                raise Exception

            # add to success attempts
            num_succeeded += 1
            succeeded.append(str(id))
        except Exception as e:
            # add to failed attempts
            print(e)
            num_failed += 1
            failed.append(str(id))
            this_status = False

    # format and return
    data = {
        'success': this_status,
        'num_succeeded': num_succeeded,
        'succeeded': succeeded,
        'num_failed': num_failed,
        'failed': failed, 
    }
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def get_flows_zapier(request: object=None) -> object:
    """ 
    Get all `Flows` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account
    flows = None
    
    # deciding on scope
    resource = 'flow'

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='flow', 
        action='get',
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        return Response(data, status=check_data['status'])

    # get all account assocoiated flows
    if flows is None:
        flows = Flow.objects.filter(
            account=account,
        ).order_by('-time_created')

    # build response data
    data = []

    for flow in flows:
        data.append({
            'id'              :  str(flow.id),
            'title'           :  flow.title,
            'time_created'    :  str(flow.time_created)
        })

    # serialize and return
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin FlowRun Services ------ ###




def create_flowrun(request: object=None) -> object:
    """ 
    Creates a new `FlowRun` from the passed 
    "flow_id" & "site_id"

    Expects: {
        'request': obejct
    }

    Returns -> HTTP Response object
    """

    # get request data
    flow_id = request.data.get('flow_id')
    site_id = request.data.get('site_id')
    configs = request.data.get('configs', None)
    
    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # update configs
    configs = account.configs if configs is None else configs

    # check site
    if not Site.objects.filter(id=site_id, account=account).exists():
        data = {'reason': 'site not found'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='flowrun', 
        action='add', id=flow_id, id_type='flow'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get flow if checks passed
    flow = Flow.objects.get(id=flow_id)

    # get site if checks passed
    site = Site.objects.get(id=site_id)

    # increment account.usage.runs
    account.usage['flowruns'] += 1
    account.save()

    # set flowrun_id
    flowrun_id = uuid.uuid4()

    # update nodes
    nodes = flow.nodes
    for i in range(len(nodes)):
        nodes[i]['data']['status'] = 'queued'
        nodes[i]['data']['finalized'] = False
        nodes[i]['data']['time_started'] = None
        nodes[i]['data']['time_completed'] = None
        nodes[i]['data']['objects'] = []

    # updates edges
    edges = flow.edges
    for i in range(len(edges)):
        edges[i]['animated'] = False
        edges[i]['style'] = None

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
        nodes   = nodes,
        edges   = edges,
        logs    = logs,
        configs = configs
    )

    # update flow with time_last_run
    flow = Flow.objects.get(id=flow_id)
    flow.time_last_run = datetime.now(timezone.utc)
    flow.save()

    # signals.py should pick up this `create()`
    # event and then run the first instance of flowr.py

    # serialize and return
    data = {
        'id': str(flowrun.id),
        'title': str(flowrun.title),
        'site': str(site.id),
        'time_created': str(flowrun.time_created)
    }
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response




def get_flowruns(request: object=None) -> object:
    """ 
    Get one or more `FlowRun`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """
    
    # get request data
    flowrun_id = request.query_params.get('flowrun_id')
    site_id = request.query_params.get('site_id')
    lean = request.query_params.get('lean')

    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # defaults
    id = site_id if site_id else flowrun_id
    id_type = 'site' if site_id else 'flowrun'

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='flowrun', 
        action='get', id=id, id_type=id_type
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get single flowrun
    if flowrun_id:        

        # get flowrun
        flowrun = FlowRun.objects.get(id=flowrun_id)

        # serialize and return
        serializer_context = {'request': request,}
        serialized = FlowRunSerializer(flowrun, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)
    
    # getting site scoped flowruns
    if site_id:
        flowruns = FlowRun.objects.filter(
            site__id=site_id, 
            account=account
        ).order_by('-time_created')
    
    # get flowruns scoped to account
    if not site_id:
        flowruns = FlowRun.objects.filter(
            account=account
        ).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(flowruns, request)
    serializer_context = {'request': request,}
    serialized = FlowRunSerializer(result_page, many=True, context=serializer_context)
    if str(lean).lower() == 'true':
        serialized = SmallFlowRunSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_flowrun(request: object=None, id: str=None) -> object:
    """
    Get single `FlowRun` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='flowrun', 
        action='get', id=id, id_type='flowrun'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get flowruns if checks passed
    flowruns = FlowRun.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = FlowRunSerializer(flowruns, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def delete_flowrun(request: object=None, id: str=None, user: object=None) -> object:
    """ 
    Deletes the `FlowRun` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str,
        'account' : object
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    if request:
        user = request.user
    member = Member.objects.get(user=user)
    account = member.account
    
    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='flowrun', 
        action='delete', id=id, id_type='flowrun'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # get flowrun if checks passed
    flowrun = FlowRun.objects.get(id=id)

    # delete flowrun
    flowrun.delete()

    # return response
    data = {'message': 'FlowRun has been deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data




def get_flowruns_zapier(request: object=None) -> object:
    """ 
    Get all `FlowRuns` associated with user's Account.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    _status = request.query_params.get('status')
    member = Member.objects.get(user=request.user)
    account = member.account
    flowruns = None
    
    # deciding on scope
    resource = 'flowrun'

    # check account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='flowrun', 
        action='get',
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        return Response(data, status=check_data['status'])

    # get all account assocoiated flowruns
    if flowruns is None:
        flowruns = FlowRun.objects.filter(
            account=account,
        ).exclude(
            time_completed=None,
        ).order_by('-time_created')

    # filter by _status if requested
    if _status is not None:
        flowruns = flowruns.filter(status=_status)

    # filter out all non permissioned sites
    if len(member.permissions.get('sites',[])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        flowruns = flowruns.filter(site__id__in=id_list).order_by('-time_created')

    # build response data
    data = []

    for run in flowruns:
        data.append({
            'id'              :  str(run.id),
            'flow'            :  str(run.flow.id),
            'site'            :  str(run.site.id),
            'title'           :  str(run.title),
            'time_created'    :  str(run.time_created),
            'time_completed'  :  str(run.time_completed),
            'status'          :  str(run.status)
        })

    # serialize and return
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Secret Services ------ ###




def create_or_update_secret(request: object=None) -> object:
    """ 
    Creates or Updates a `Secret`

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """
    
    # get request data
    secret_id = request.data.get('secret_id')
    name = request.data.get('name')
    value = request.data.get('value')
    action = 'update' if secret_id else 'add'
    
    # get user & account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account
    

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='secret', 
        action=action, id=secret_id, id_type='secret'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # encrypt value if passed
    f = Fernet(settings.SECRETS_KEY)
    bytes_value = bytes(value, 'utf-8')
    encrypted_value = f.encrypt(bytes_value).decode('utf-8')

    # update secret
    if secret_id:
        
        # get secret 
        secret = Secret.objects.get(id=secret_id)

        # save new value
        secret.value = encrypted_value
        secret.save()
    
    # create new secret
    if not secret_id:
        secret = Secret.objects.create(
            account=account,
            user=user,
            name=name,
            value=encrypted_value
        )

    # serialize and return
    serializer_context = {'request': request,}
    serialized = SecretSerializer(secret, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def get_secrets(request: object=None) -> object:
    """ 
    Get one or more `Secrets`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """
    
    # get request data
    secret_id = request.query_params.get('secret_id')
    lean = request.query_params.get('lean')

    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='secret', 
        action='get', id=secret_id, id_type='secret'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get single secret
    if secret_id:        

        # get secret
        secret = Secret.objects.get(id=secret_id)

        # serialize and return
        serializer_context = {'request': request,}
        serialized = SecretSerializer(secret, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)
    
    # get secrets scoped to account
    secrets = Secret.objects.filter(account=account).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(secrets, request)
    serializer_context = {'request': request,}
    serialized = SecretSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_secret(request: object=None, id: str=None) -> object:
    """
    Get single `Secret` from the passed "id"

    Expects: {
        'request' : object,
        'id'      : str 
    }

    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='secret', 
        action='get', id=id, id_type='secret'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get secrets if checks passed
    secrets = Secret.objects.get(id=id)
        
    # serialize and return
    serializer_context = {'request': request,}
    serialized = SecretSerializer(secrets, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def get_secrets_all(request: object=None) -> object:
    """ 
    Get all `Secrets` associated with the 
    equesting user's `Account`.

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='secret', 
        action='get'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

    # get secrets scoped to account
    secrets = Secret.objects.filter(account=account).order_by('-time_created')

    # build into list
    data = []
    for secret in secrets:
        data.append({
            'name': secret.name,
            'value': secret.name,
            'task': 'any'
        })

    # return list
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def delete_secret(request: object=None, id: str=None, user: object=None) -> object:
    """ 
    Deletes the `Secret` associated with the passed "id" 

    Expcets: {
        'request' : object,
        'id'      : str,
        'user'    : object
    }

    Returns -> HTTP Response object
    """

    # get user and account info
    if request:
        user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='secret', 
        action='delete', id=id, id_type='secret'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        if request:
            record_api_call(request, data, check_data['code'])
            return Response(data, status=check_data['status'])
        return data

    # get secret if checks passed
    secret = Secret.objects.get(id=id)

    # delete secret
    secret.delete()

    # return response
    data = {'message': 'Secret has been deleted',}
    if request:
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    return data




### ------ Begin Process Services ------ ###




def get_processes(request: object=None) -> object:
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
    object_id = request.query_params.get('object_id')

    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    id = process_id if process_id else site_id
    id_type = 'process' if process_id else 'site'

    # checking account and resource 
    check_data = check_permissions_and_usage(
        member=member, resource='process', 
        action='get', id=id, id_type=id_type
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
        if _type is None and object_id is None:
            processes = Process.objects.filter(account=account).order_by('-time_created')
        if _type is not None:
            processes = Process.objects.filter(account=account, type=_type).order_by('-time_created')
        if object_id is not None:
            processes = Process.objects.filter(account=account, object_id=object_id).order_by('-time_created')

    # filter out all non permissioned sites
    if len(member.permissions.get('sites',[])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        processes = processes.filter(site__id__in=id_list).order_by('-time_created')

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(processes, request)
    serializer_context = {'request': request,}
    serialized = ProcessSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_process(request: object=None, id: str=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='process', 
        action='get', id=id, id_type='process'
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




def get_logs(request: object=None) -> object:
    """ 
    Get one or more `CaseRun`.

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
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='log', 
        action='get', id=log_id, id_type='log'
    )
    if not check_data['allowed']:
        data = {'reason': check_data['error'],}
        record_api_call(request, data, check_data['code'])
        return Response(data, status=check_data['status'])

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




def get_log(request: object=None, id: str=None) -> object:
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
    member = Member.objects.get(user=user)
    account = member.account

    # check account and resource
    check_data = check_permissions_and_usage(
        member=member, resource='log', 
        action='get', id=id, id_type='log'
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




def search_resources(request: object=None) -> object:
    """
    This method will search for any `Page` or `Site`
    that is associated with the user's `Account` and
    matches the query string.

    Expects:
        'query': <str> the query string
    
    Returns:
        data -> [
            {
                'str' : <str>,
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
    member = Member.objects.get(user=user)
    account = member.account
    actions = member.permissions.get('actions', [])
    resources = member.permissions.get('resources', [])
    allowed_ids = [item['id'] for item in member.permissions.get('sites')]
    data = []
    cases = []
    pages = []
    sites = []
    issues = []
    flows = []

    # check action permissons
    if 'get' not in actions:
        data = {'reason': 'not allowed',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    # check for object specification i.e 'site:', 'case:', 'issue:'
    resource_type = query.replace('https://', '').replace('http://', '').split(':')[0]
    query = query.replace('https://', '').replace('http://', '').split(':')[-1]

    # search for sites
    if (resource_type == 'site' or resource_type == query) and 'site' in resources:
        sites = Site.objects.filter(account=account).filter(
            site_url__icontains=query
        )
        # filter out all non permisioned
        if len(allowed_ids) > 0:
            sites = sites.filter(id__in=allowed_ids)

    # search for pages
    if (resource_type == 'page' or resource_type == query) and 'page' in resources:
        pages = Page.objects.filter(account=account).filter(
            page_url__icontains=query
        )
        # filter out all non permisioned
        if len(allowed_ids) > 0:
            pages = pages.filter(site__id__in=allowed_ids)

    # search for cases
    if (resource_type == 'case' or resource_type == query) and 'case' in resources:
        cases = Case.objects.filter(account=account).filter(
            title__icontains=query
        )
        # filter out all non permisioned
        if len(allowed_ids) > 0:
            cases = cases.filter(site__id__in=allowed_ids)

    # search for issues
    if (resource_type == 'issue' or resource_type == query) and 'issue' in resources:
        issues = Issue.objects.filter(account=account).filter(
            title__icontains=query
        )
        # filter out all non permisioned
        if len(allowed_ids) > 0:
            new_ids = allowed_ids
            for id in allowed_ids:
                for page in Page.objects.filter(site__id=id):
                    new_ids.append(str(page.id))
            issues = issues.filter(affected__id__in=new_ids)

    # search for flows
    if (resource_type == 'flow' or resource_type == query) and 'flow' in resources:
        flows = Flow.objects.filter(account=account).filter(
            title__icontains=query
        )

    # adding first several sites if present
    i = 0
    sites_allowed = 10 if resource_type == 'site' else 3
    while i <= sites_allowed and i <= (len(sites)-1):
        data.append({
            'str': str(sites[i].site_url),
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
            'str': str(pages[i].page_url),
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
            'str': str(cases[i].title),
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
            'str': str(issues[i].title),
            'path': f'/issue/{issues[i].id}',
            'id'  : str(issues[i].id),
            'type': 'issue',
        })
        i+=1

    # adding first several flows if present
    i = 0
    max_flows = 10 if resource_type == 'flows' else 2
    while i <= max_flows and i <= (len(flows)-1):
        data.append({
            'str': str(flows[i].title),
            'path': f'/flow/{flows[i].id}',
            'id'  : str(flows[i].id),
            'type': 'flow',
        })
        i+=1
    
    # return response
    response = Response(data, status=status.HTTP_200_OK)
    return response




def get_devices(request: object=None) -> object:
    """ 
    Retrieves a list of all Cursion "devices"
    
    Expects: None

    Returns -> HTTP Response object
    """
    
    # format data
    data = {
        'devices': devices
    }

    # return response
    response = Response(data, status=status.HTTP_200_OK)
    return response




### ------ Begin Metrics Services ------ ###




def get_home_metrics(request: object=None) -> object:
    """ 
    Builds metrics for account "Home" view 
    on Cursion.client

    Expects: {
        'request' : object
    }

    Returns -> HTTP Response object
    """

    # get user, account, sites, & issues
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account
    sites = Site.objects.filter(account=account).count()
    issues = Issue.objects.filter(account=account, status='open')
    schedules = Schedule.objects.filter(account=account).count()
    
    # filter issues by allowed sites
    if len(member.permissions.get('sites',[])) != 0:
        id_list = [item['id'] for item in member.permissions.get('sites')]
        new_ids = id_list
        for id in id_list:
            for page in Page.objects.filter(site__id=id):
                new_ids.append(str(page.id))
        issues = issues.filter(affected__id__in=new_ids)
    
    # setting resource defaults
    tests = account.usage['tests']
    scans = account.usage['scans']
    caseruns = account.usage['caseruns']
    flowruns = account.usage.get('flowruns', 0)
    issues = issues.count()

    # calculate usages
    sites_usage = round((sites/account.usage['sites_allowed'])*100, 2) if sites > 0 else 0
    schedules_usage = round((schedules/account.usage['schedules_allowed'])*100, 2) if schedules > 0 else 0
    scans_usage = round((scans/account.usage['scans_allowed'])*100, 2) if scans > 0 else 0
    tests_usage = round((tests/account.usage['tests_allowed'])*100, 2) if tests > 0 else 0
    caseruns_usage = round((caseruns/account.usage['caseruns_allowed'])*100, 2) if caseruns > 0 else 0
    flowruns_usage = round((flowruns/account.usage['flowruns_allowed'])*100, 2) if flowruns > 0 else 0
    
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
        "caseruns": caseruns,
        "caseruns_usage": caseruns_usage,
        "flowruns": flowruns,
        "flowruns_usage": flowruns_usage,
        "open_issues": issues,
    }
    
    # return response
    response = Response(data, status=status.HTTP_200_OK)
    return response




def get_site_metrics(request: object=None) -> object:
    """ 
    Builds metrics for account "Site" view 
    on Cursion.client

    Expects: {
        'request' : object
    }

    Returns -> HTTP Response object
    """

    # get user, account, site, & pages
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account
    site_id = request.query_params.get('site_id')
    site = Site.objects.get(id=site_id)
    sites_allowed = account.usage['sites_allowed']
    pages = Page.objects.filter(site=site)

    # get last reset day 
    f = '%Y-%m-%d %H:%M:%S.%f'
    last_usage_date_str = account.meta.get('last_usage_reset')
    last_usage_date = None
    if last_usage_date_str:  
        last_usage_date_str = last_usage_date_str.replace('T', ' ').replace('Z', '')
        last_usage_date = datetime.strptime(last_usage_date_str, f)
    else:
        last_usage_date = datetime.now() - timedelta(30)

    # get scans
    scans = Scan.objects.filter(
        site=site,
        time_created__gte=last_usage_date
    ).count()

    # get tests
    tests = Test.objects.filter(
        site=site,
        time_created__gte=last_usage_date
    ).count()

    # get caseruns
    caseruns = CaseRun.objects.filter(
        site=site,
        time_created__gte=last_usage_date
    ).count()

    # get flowruns
    flowruns = FlowRun.objects.filter(
        site=site,
        time_created__gte=last_usage_date
    ).count()

    # get site scoped schedules
    schedules = Schedule.objects.filter(
        resources__icontains=str(site.id), scope='site',
        account=account
    ).count()

    # calculating page scoped schedules
    for page in pages:
        schedules += Schedule.objects.filter(
            resources__icontains=str(page.id), scope='page',
            account=account
        ).count()
        
    # calculate usage
    pages = pages.count()
    pages_usage = round((pages/account.usage['pages_allowed'])*100, 2) if pages > 0 else 0
    schedules_usage = round((schedules/account.usage['schedules_allowed'])*100, 2) if schedules > 0 else 0
    scans_usage = round((scans/account.usage['scans_allowed'])*100, 2) if scans > 0 else 0
    tests_usage = round((tests/account.usage['tests_allowed'])*100, 2) if tests > 0 else 0
    caseruns_usage = round((caseruns/account.usage['caseruns_allowed'])*100, 2) if caseruns > 0 else 0
    flowruns_usage = round((flowruns/account.usage['flowruns_allowed'])*100, 2) if flowruns > 0 else 0

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
        "caseruns": caseruns,
        "caseruns_usage": caseruns_usage,
        "flowruns": flowruns,
        "flowruns_usage": flowruns_usage,
    }

    # return response
    response = Response(data, status=status.HTTP_200_OK)
    return response




def get_celery_metrics(request: object=None) -> object:
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

    # Active tasks
    active = i.active()

    # init task & replica counters & ratio 
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




def migrate_site(request: object=None) -> object:
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
    check_data = check_permissions_and_usage(
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





