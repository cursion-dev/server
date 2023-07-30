import json, boto3, asyncio, os
from datetime import datetime
from django.contrib.auth.models import User
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from ...models import *
from rest_framework.response import Response
from rest_framework import status
from scanerr import celery
from .serializers import *
from ...tasks import *
from rest_framework.pagination import LimitOffsetPagination
from ...utils.scanner import Scanner as S
from ...utils.tester import Tester as T
from ...utils.image import Image as I
from ...utils.reporter import Reporter as R
from ...utils.wordpress import Wordpress as W
from ...utils.wordpress_p import Wordpress as W_P
from ...utils.caser import Caser
from ...utils.crawler import Crawler






def record_api_call(request, data, status):

    auth = request.headers.get('Authorization')
    if auth.startswith('Token'):

        if request.method == 'POST':
            request_data = request.data

        elif request.method == 'GET':
            request_data = request.query_params

        elif request.method == 'DELETE':
            request_data = request.query_params

        log = Log.objects.create(
            user=request.user,
            path=request.path,
            status=status,
            request_type=request.method,
            request_payload=request_data,
            response_payload=data
        )
    
    return



def check_account(request=None, user=None):
    if request is not None:
        user = request.user
    if Member.objects.filter(user=user).exists():
        member = Member.objects.get(user=user)
        return member.account.active
    else:
        return False










def create_site(request, delay=False):
    site_url = request.data.get('site_url')
    page_urls = request.data.get('page_urls')
    user = request.user
    account = Member.objects.get(user=user).account
    sites = Site.objects.filter(account=account)


    if site_url.endswith('/'):
        site_url = site_url.rstrip('/')

    if site_url is None or site_url == '':
        data = {'reason': 'the site_url cannot be empty',}
        record_api_call(request, data, '400')
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

    account_is_active = check_account(request=request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    if sites.count() >= account.max_sites:
        data = {'reason': 'maximum number of sites reached',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    if Site.objects.filter(site_url=site_url, user=user).exists():
        data = {'reason': 'site already exists',}
        record_api_call(request, data, '409')
        return Response(data, status=status.HTTP_409_CONFLICT)
    else:
        tags = request.data.get('tags', None)
        configs = request.data.get('configs', None)
        no_scan = request.data.get('no_scan', False)
        site = Site.objects.create(
            site_url=site_url,
            user=user,
            tags=tags,
            account=account
        )

        if not configs:
            configs = {
                'window_size': '1920,1080',
                'interval': 5,
                'driver': 'selenium',
                'device': 'desktop',
                'mask_ids': None,
                'min_wait_time': 10,
                'max_wait_time': 60,
                'timeout': 300,
                'disable_animations': False
            }

        if no_scan == False:
            if delay == True:
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
                            create_scan(
                                page_id=page.id, 
                                configs=configs, 
                                user_id=request.user.id,
                                delay=True
                            )
                else:
                    create_site_and_pages_bg.delay(site_id=site.id, configs=configs)
                site.time_crawl_started = datetime.now()
                site.time_crawl_completed = datetime.now()
                site.info["latest_scan"]["time_created"] = str(datetime.now())
                site.save()

            else:
                # running crawler
                pages = Crawler(url=site.site_url, max_urls=account.max_pages).get_links()
                for url in pages:
                    # add new page
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
                    # run each scan component
                    S(site=site, page=page, configs=configs).first_scan()
                    page.info["latest_scan"]["id"] = str(scan.id)
                    page.info["latest_scan"]["time_created"] = str(scan.time_created)
                    page.save()
                

        serializer_context = {'request': request,}
        serialized = SiteSerializer(site, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '201')
        response = Response(data, status=status.HTTP_201_CREATED)
        return response




def crawl_site(request, id):
    user = request.user
    account = Member.objects.get(user=user).account

    account_is_active = check_account(request=request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)
    try:
        site = Site.objects.get(id=id)
    except:
        data = {'reason': 'cannot find a Site with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)
    
    if site.account != account:
        data = {'reason': 'cannot crawl a Site you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)
    
    configs = request.data.get('configs', None)
    if not configs:
        configs = {
            'window_size': '1920,1080',
            'interval': 5,
            'driver': 'selenium',
            'device': 'desktop',
            'mask_ids': None,
            'min_wait_time': 10,
            'max_wait_time': 60,
            'timeout': 300,
            'disable_animations': False
        }

    # update site info
    site.time_crawl_completed = None
    site.save()

    crawl_site_bg.delay(site_id=site.id, configs=configs)

    serializer_context = {'request': request,}
    serialized = SiteSerializer(site, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response




def get_sites(request):
    site_id = request.query_params.get('site_id')
    user = request.user
    account = Member.objects.get(user=user).account


    if site_id != None:
        
        try:
            site = Site.objects.get(id=site_id)
        except:
            data = {'reason': 'cannot find a Site with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        
        if site.account != account:
            data = {'reason': 'cannot retrieve a Site you do not own',}
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        serializer_context = {'request': request,}
        serialized = SiteSerializer(site, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)
    
    sites = Site.objects.filter(account=account).order_by('-time_created')
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(sites, request)
    serializer_context = {'request': request,}
    serialized = SiteSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def delete_site(request, id):
    user = request.user
    account = Member.objects.get(user=user).account
    
    try:
        site = Site.objects.get(id=id)
    except:
        data = {'reason': 'cannot find a Site with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)

    if site.account != account:
        data = {'reason': 'delete a Site you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    # remove s3 objects
    delete_site_s3_bg.delay(site_id=id)
    
    # remove site
    site.delete()

    data = {'message': 'Site has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def delete_many_sites(request):
    ids = request.data.get('ids')
    user = request.user
    account = Member.objects.get(user=user).account

    if ids is not None:
        count = len(ids)
        num_succeeded = 0
        succeeded = []
        num_failed = 0
        failed = []
        user = request.user
        this_status = True

        for id in ids:
            try:
                site = Site.objects.get(id=id)
                if site.account == account:
                    delete_site_s3_bg.delay(site_id=id)
                    site.delete()
                num_succeeded += 1
                succeeded.append(str(id))
            except:
                num_failed += 1
                failed.append(str(id))
                this_status = False

        data = {
            'success': this_status,
            'num_succeeded': num_succeeded,
            'succeeded': succeeded,
            'num_failed': num_failed,
            'failed': failed, 
        }
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    
    data = {
        'reason': 'you must provide an array of id\'s'
    }
    record_api_call(request, data, '400')
    response = Response(data, status=status.HTTP_400_BAD_REQUEST)
    return response










def create_page(request, delay=False):
    site_id = request.data.get('site_id')
    page_url = request.data.get('page_url')
    page_urls = request.data.get('page_urls')
    user = request.user
    account = Member.objects.get(user=user).account
    site = Site.objects.get(id=site_id)
    pages = Page.objects.filter(site=site)

    if page_urls is not None:
        data = create_many_pages(request=request, obj_response=False)
        record_api_call(request, data, '201')
        response = Response(data, status=status.HTTP_201_CREATED)
        return response

    if page_url.endswith('/'):
        page_url = page_url.rstrip('/')

    if page_url is None or page_url == '':
        data = {'reason': 'the page_url cannot be empty',}
        record_api_call(request, data, '400')
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

    account_is_active = check_account(request=request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    if pages.count() >= account.max_pages:
        data = {'reason': 'maximum number of pages reached',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    if Page.objects.filter(page_url=page_url, user=user).exists():
        data = {'reason': 'page already exists',}
        record_api_call(request, data, '409')
        return Response(data, status=status.HTTP_409_CONFLICT)
    else:
        tags = request.data.get('tags', None)
        configs = request.data.get('configs', None)
        no_scan = request.data.get('no_scan', False)
        page = Page.objects.create(
            site=site,
            page_url=page_url,
            user=user,
            tags=tags,
            account=account
        )

        if not configs:
            configs = {
                'window_size': '1920,1080',
                'interval': 5,
                'driver': 'selenium',
                'device': 'desktop',
                'mask_ids': None,
                'min_wait_time': 10,
                'max_wait_time': 60,
                'timeout': 300,
                'disable_animations': False
            }

        if no_scan == False:

            # create initial scan
            scan = Scan.objects.create(
                site=site,
                page=page, 
                type=['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'],
                configs=configs
            )
            page.info["latest_scan"]["id"] = str(scan.id)
            page.info["latest_scan"]["time_created"] = str(scan.time_created)
            page.save()

            if delay == True:
                scan_page_bg.delay(scan_id=scan.id, configs=configs)

            else:
                # create initial scan
                scan = Scan.objects.create(
                    site=site,
                    page=page, 
                    type=['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'],
                    configs=configs
                )
                # run each scan component
                S(site=site, page=page, configs=configs).first_scan()
                page.info["latest_scan"]["id"] = str(scan.id)
                page.info["latest_scan"]["time_created"] = str(scan.time_created)
                page.save()
                

        serializer_context = {'request': request,}
        serialized = PageSerializer(page, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '201')
        response = Response(data, status=status.HTTP_201_CREATED)
        return response




def create_many_pages(request, obj_response=False):
    site_id = request.data.get('site_id')
    page_urls = request.data.get('page_urls')
    user = request.user
    account = Member.objects.get(user=user).account
    site = Site.objects.get(id=site_id)
    pages = Page.objects.filter(site=site)

    account_is_active = check_account(request=request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    if pages.count() >= account.max_pages:
        data = {'reason': 'maximum number of pages reached',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    count = len(page_urls)
    num_succeeded = 0
    succeeded = []
    num_failed = 0
    failed = []
    this_status = True

    for url in page_urls:

        if url.endswith('/'):
            url = url.rstrip('/')

        if not Page.objects.filter(page_url=url, user=user).exists():
            
            # adding pages
            tags = request.data.get('tags', None)
            configs = request.data.get('configs', None)
            no_scan = request.data.get('no_scan', False)
            page = Page.objects.create(
                site=site,
                page_url=url,
                user=user,
                tags=tags,
                account=account
            )

            if not configs:
                configs = {
                    'window_size': '1920,1080',
                    'interval': 5,
                    'driver': 'selenium',
                    'device': 'desktop',
                    'mask_ids': None,
                    'min_wait_time': 10,
                    'max_wait_time': 60,
                    'timeout': 300,
                    'disable_animations': False
                }

            if no_scan == False:

                # create initial scan
                scan = Scan.objects.create(
                    site=site,
                    page=page, 
                    type=['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'],
                    configs=configs
                )
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

    data = {
        'success': this_status,
        'num_succeeded': num_succeeded,
        'succeeded': succeeded,
        'num_failed': num_failed,
        'failed': failed, 
    }
    if obj_response:
        record_api_call(request, data, '201')
        response = Response(data, status=status.HTTP_201_CREATED)
        return response
    return data





def get_pages(request):
    site_id = request.query_params.get('site_id')
    page_id = request.query_params.get('page_id')
    user = request.user
    account = Member.objects.get(user=user).account

    if page_id is None and site_id is None:
        data = {'reason': 'must provide a Site or Page id'}
        record_api_call(request, data, '400')
        return Response(data, status=status.HTTP_400_BAD_REQUEST)


    if site_id != None:
        
        try:
            site = Site.objects.get(id=site_id)
            print('got site')
        except:
            data = {'reason': 'cannot find a Site with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        
        if site.account != account:
            data = {'reason': 'cannot retrieve a Site you do not own',}
            return Response(data, status=status.HTTP_403_FORBIDDEN)


    if page_id != None:
        
        try:
            page = Page.objects.get(id=page_id)
        except:
            data = {'reason': 'cannot find a Page with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        
        if page.account != account:
            data = {'reason': 'cannot retrieve a Page you do not own',}
            return Response(data, status=status.HTTP_403_FORBIDDEN)

        serializer_context = {'request': request,}
        serialized = PageSerializer(page, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    
    pages = Page.objects.filter(site=site).order_by('-time_created')
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(pages, request)
    serializer_context = {'request': request,}
    serialized = PageSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def delete_page(request, id):
    user = request.user
    account = Member.objects.get(user=user).account
    
    try:
        page = Page.objects.get(id=id)
    except:
        data = {'reason': 'cannot find a Page with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)

    if page.account != account:
        data = {'reason': 'delete a Page you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    # remove s3 objects
    delete_page_s3_bg.delay(page_id=id, site_id=page.site.id)
    
    # remove page
    page.delete()

    data = {'message': 'Page has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def delete_many_pages(request):
    ids = request.data.get('ids')
    user = request.user
    account = Member.objects.get(user=user).account

    if ids is not None:
        count = len(ids)
        num_succeeded = 0
        succeeded = []
        num_failed = 0
        failed = []
        user = request.user
        this_status = True

        for id in ids:
            try:
                page = Page.objects.get(id=id)
                if page.account == account:
                    delete_page_s3_bg.delay(page_id=id, site_id=page.site.id)
                    page.delete()
                num_succeeded += 1
                succeeded.append(str(id))
            except:
                num_failed += 1
                failed.append(str(id))
                this_status = False

        data = {
            'success': this_status,
            'num_succeeded': num_succeeded,
            'succeeded': succeeded,
            'num_failed': num_failed,
            'failed': failed, 
        }
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    
    data = {
        'reason': 'you must provide an array of id\'s'
    }
    record_api_call(request, data, '400')
    response = Response(data, status=status.HTTP_400_BAD_REQUEST)
    return response









def create_scan(request=None, delay=False, *args, **kwargs):
    if request is not None:
        site_id = request.data.get('site_id')
        page_id = request.data.get('page_id')
        configs = request.data.get('configs')
        types = request.data.get('type', ['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'])
        tags = request.data.get('tags')
        user = request.user
    if request is None:
        site_id = kwargs.get('site_id')
        page_id = kwargs.get('page_id')
        configs = kwargs.get('configs')
        types = kwargs.get('type', ['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'])
        tags = kwargs.get('tags')
        user_id = kwargs.get('user_id')
        user = User.objects.get(id=user_id)
    account = Member.objects.get(user=user).account

    account_is_active = check_account(user=user)
    if not account_is_active:
        data = {'reason': 'account not funded', 'success': False}
        if request is not None:
            record_api_call(request, data, '402')
            return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)
        return data

    if len(types) == 0:
        types = ['html', 'logs', 'vrt', 'lighthouse', 'yellowlab']
        
    
    if site_id is not None:
        try:
            site = Site.objects.get(id=site_id)
        except:
            data = {'reason': 'cannot find a Site with that id', 'success': False,}
            if request is not None:
                record_api_call(request, data, '404')
                return Response(data, status=status.HTTP_404_NOT_FOUND)
            return data

        if site.account != account:
            data = {'reason': 'create a Scan of a Site you do not own', 'success': False,}
            if request is not None:
                record_api_call(request, data, '403')
                return Response(data, status=status.HTTP_403_FORBIDDEN)
            return data
    
    if page_id is not None:
        try:
            page = Page.objects.get(id=page_id)
        except:
            data = {'reason': 'cannot find a Page with that id', 'success': False,}
            if request is not None:
                record_api_call(request, data, '404')
                return Response(data, status=status.HTTP_404_NOT_FOUND)
            return data

        if page.account != account:
            data = {'reason': 'create a Scan of a Page you do not own', 'success': False,}
            if request is not None:
                record_api_call(request, data, '403')
                return Response(data, status=status.HTTP_403_FORBIDDEN)
            return data

    if not configs:
        configs = {
            'window_size': '1920,1080',
            'interval': 5,
            'driver': 'selenium',
            'device': 'desktop',
            'mask_ids': None,
            'min_wait_time': 10,
            'max_wait_time': 60,
            'timeout': 300,
            'disable_animations': False
        }

    if site_id is not None and page_id is None:
        pages = Page.objects.filter(site=site)
    
    if site_id is None and page_id is not None:
        pages = [page,]

    created_scans = []
    for p in pages:
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

        if delay == True:
            # running scans in parallel 
            if 'html' in types or 'logs' in types or 'full' in types:
                run_html_and_logs_bg.delay(scan_id=created_scan.id)
            if 'lighthouse' in types or 'full' in types:
                run_lighthouse_bg.delay(scan_id=created_scan.id)
            if 'yellowlab' in types or 'full' in types:
                run_yellowlab_bg.delay(scan_id=created_scan.id)
            if 'vrt' in types or 'full' in types:
                run_vrt_bg.delay(scan_id=created_scan.id)
        else:
            updated_scan = S(scan=created_scan, configs=configs).first_scan()
            message = 'Scans have completed running'

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




def create_many_scans(request):
    site_ids = request.data.get('site_ids')
    page_ids = request.data.get('page_ids')
    configs = request.data.get('configs')
    type = request.data.get('type', ['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'])
    tags = request.data.get('tags')
    user = request.user

    num_succeeded = 0
    succeeded = []
    num_failed = 0
    failed = []
    this_status = True

    if site_ids:
        for id in site_ids:
            data = {
                'site_id': str(id), 
                'configs': configs,
                'type': type,
                'tags': tags,
                'user_id': str(user.id)
            }
            try:
                res = create_scan(delay=True, **data)
                if res['success']:
                    num_succeeded += 1
                    succeeded.append(str(id))
                else:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))
            except Exception as e:
                print(e)
                num_failed += 1
                this_status = False
                failed.append(str(id))

    if page_ids:
        for id in page_ids:
            data = {
                'page_id': str(id), 
                'configs': configs,
                'type': type,
                'tags': tags,
                'user_id': str(user.id)
            }
            try:
                res = create_scan(delay=True, **data)
                if res['success']:
                    num_succeeded += 1
                    succeeded.append(str(id))
                else:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))
            except Exception as e:
                print(e)
                num_failed += 1
                this_status = False
                failed.append(str(id))

    data = {
        'success': this_status,
        'num_succeeded': num_succeeded,
        'succeeded': succeeded,
        'num_failed': num_failed,
        'failed': failed, 
    }
    
    record_api_call(request, data, '201')
    return Response(data, status=status.HTTP_201_CREATED)



def get_scans(request):

    user = request.user
    account = Member.objects.get(user=user).account
    scan_id = request.query_params.get('scan_id')
    page_id = request.query_params.get('page_id')
    time_begin = request.query_params.get('time_begin')
    time_end = request.query_params.get('time_end')
    lean = request.query_params.get('lean')

    if scan_id != None:
        try:
            scan = Scan.objects.get(id=scan_id)
        except:
            data = {'reason': 'cannot find a Scan with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)

        if scan.site.account != account:
            data = {'reason': 'retrieve Scans of a Site you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = ScanSerializer(scan, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    
    try:
        page = Page.objects.get(id=page_id)
    except:
        data = {'reason': 'cannot find a Page with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)
    

    if page.account != account:
        data = {'reason': 'retrieve Scans of a Site you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    
    if time_begin == None and page != None and time_end != None:
        scans = Scan.objects.filter(page=page).filter(time_created__lte=time_end).order_by('-time_created')
    elif time_end == None and page != None and time_begin != None:  
        scans = Scan.objects.filter(page=page).filter(time_created__gte=time_begin).order_by('-time_created')
    elif time_end == None and time_begin == None and page != None:
        scans = Scan.objects.filter(page=page).order_by('-time_created')
    elif time_end != None and time_begin != None and page != None:
        scans = Scan.objects.filter(page=page).filter(time_created__gte=time_begin).filter(time_created__lte=time_end).order_by('-time_created')

        
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(scans, request)
    serializer_context = {'request': request,}
    serialized = ScanSerializer(result_page, many=True, context=serializer_context)
    if lean is not None:
        serialized = SmallScanSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def get_scan_lean(request, id):
    user = request.user
    account = Member.objects.get(user=user).account

    try:
        scan = Scan.objects.get(id=id)
    except:
        data = {'reason': 'cannot find a Scan with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)

    if scan.site.account != account:
        data = {'reason': 'retrieve Scans of a Site you do not own'}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    # get lighthouse scores if exists
    try:
        lighthouse = {"scores": scan.lighthouse.get('scores')}
    except:
        lighthouse = None
    
    # get yellowlab scores if exists
    try:
        yellowlab = {"scores": scan.yellowlab.get('scores')}
    except:
        yellowlab = None

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

    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def delete_scan(request, id):
    try:
        scan = Scan.objects.get(id=id)
    except Exception as e:
        data = {'reason': 'cannot find a Scan with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)
        
    site = scan.site
    user = request.user
    account = Member.objects.get(user=user).account


    if site.account != account:
        data = {'reason': 'delete Scans of a Site you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    delete_scan_s3_bg.delay(scan.id, scan.site.id, scan.page.id)
    scan.delete()

    data = {'message': 'Scan has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def delete_many_scans(request):
    ids = request.data.get('ids')
    user = request.user
    account = Member.objects.get(user=user).account

    if ids is not None:
        count = len(ids)
        num_succeeded = 0
        succeeded = []
        num_failed = 0
        failed = []
        user = request.user
        this_status = True

        for id in ids:
            try:
                scan = Scan.objects.get(id=id)
                if scan.site.account == account:
                    delete_scan_s3_bg.delay(scan.id, scan.site.id, scan.page.id)
                    scan.delete()
                num_succeeded += 1
                succeeded.append(str(id))
            except Exception as e:
                print(e)
                num_failed += 1
                failed.append(str(id))
                this_status = False

        data = {
            'success': this_status,
            'num_succeeded': num_succeeded,
            'succeeded': succeeded,
            'num_failed': num_failed,
            'failed': failed, 
        }
        
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response

    data = {
        'reason': 'you must provide an array of id\'s'
    }
    record_api_call(request, data, '400')
    response = Response(data, status=status.HTTP_400_BAD_REQUEST)
    return response









def create_test(request=None, delay=False, *args, **kwargs):
    if request is not None:
        # get data from request
        configs = request.data.get('configs')
        pre_scan_id = request.data.get('pre_scan')
        post_scan_id = request.data.get('post_scan')
        index = request.data.get('index')
        test_type = request.data.get('type', ['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'])
        tags = request.data.get('tags')
        pre_scan = None
        post_scan = None
        site_id = request.data.get('site_id')
        page_id = request.data.get('page_id')
        user = request.user
    if request is None:
        configs = kwargs.get('configs')
        pre_scan_id = kwargs.get('pre_scan')
        post_scan_id = kwargs.get('post_scan')
        index = kwargs.get('index')
        test_type = kwargs.get('type', ['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'])
        tags = kwargs.get('tags')
        pre_scan = None
        post_scan = None
        site_id = kwargs.get('site_id')
        page_id = kwargs.get('page_id')
        user_id = kwargs.get('user_id')
        user = User.objects.get(id=user_id)
        # get data from kwargs
    account = Member.objects.get(user=user).account

    account_is_active = check_account(user=user)
    if not account_is_active:
        data = {'reason': 'account not funded', 'success': False,}
        if request is not None:
            record_api_call(request, data, '402')
            return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)
        return data

    if site_id is not None:
        try:
            site = Site.objects.get(id=site_id)
        except:
            data = {'reason': 'cannot find a Site with that id', 'success': False,}
            if request is not None:
                record_api_call(request, data, '404')
                return Response(data, status=status.HTTP_404_NOT_FOUND)
            return data

        if site.account != account:
            data = {'reason': 'create a Test of a Site you do not own', 'success': False,}
            if request is not None:
                record_api_call(request, data, '403')
                return Response(data, status=status.HTTP_403_FORBIDDEN)
            return data
    
    if page_id is not None:
        try:
            page = Page.objects.get(id=page_id)
        except:
            data = {'reason': 'cannot find a Page with that id', 'success': False,}
            if request is not None:
                record_api_call(request, data, '404')
                return Response(data, status=status.HTTP_404_NOT_FOUND)
            return data
        if page.account != account:
            data = {'reason': 'create a Test of a Page you do not own', 'success': False,}
            if request is not None:
                record_api_call(request, data, '403')
                return Response(data, status=status.HTTP_403_FORBIDDEN)
            return data
        

    if len(test_type) == 0:
        test_type = ['html', 'logs', 'vrt', 'lighthouse', 'yellowlab']
    
    if not configs:
        configs = {
            'window_size': '1920,1080',
            'interval': 5,
            'driver': 'selenium',
            'device': 'desktop',
            'mask_ids': None,
            'min_wait_time': 10,
            'max_wait_time': 60,
            'timeout': 300,
            'disable_animations': False
        }


    if site_id is not None and page_id is None:
        pages = Page.objects.filter(site=site)
    
    if site_id is None and page_id is not None:
        pages = [page]

    created_tests = []
    for p in pages:

        if not Scan.objects.filter(page=p).exists():
            data = {'reason': 'Page not yet onboarded', 'success': False,}
            record_api_call(request, data, '400')
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        
        if pre_scan_id:
            try:
                pre_scan = Scan.objects.get(id=pre_scan_id)
            except:
                data = {'reason': 'cannot find a Scan with that id - pre_scan', 'success': False,}
                if request is not None:
                    record_api_call(request, data, '404')
                    return Response(data, status=status.HTTP_404_NOT_FOUND)
                return data
        if post_scan_id:
            try:
                post_scan = Scan.objects.get(id=post_scan_id)
            except:
                data = {'reason': 'cannot find a Scan with that id - post_scan', 'success': False,}
                if request is not None:
                    record_api_call(request, data, '404')
                    return Response(data, status=status.HTTP_404_NOT_FOUND)
                return data

        # grabbing most recent Scan 
        if pre_scan_id is None:
            pre_scan = Scan.objects.filter(page=p).order_by('-time_created')[0]

        if pre_scan:
            if pre_scan.time_completed == None:
                data = {'reason': 'pre_scan still running', 'success': False,}
                if request is not None:
                    record_api_call(request, data, '400')
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)
                return data
        
        if post_scan:
            if post_scan.time_completed == None:
                data = {'reason': 'post_scan still running', 'success': False,}
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
        )
        created_tests.append(str(test.id))

        if delay == True:
            create_test_bg.delay(
                page_id=p.id,
                test_id=test.id,
                configs=configs,
                type=test_type,
                index=index,
                pre_scan=pre_scan_id, 
                post_scan=post_scan_id,
                tags=tags,
            )
            message = 'Tests are being created in the background'
            
        else:
            if not pre_scan and not post_scan:
                new_scan = S(site=p.site, page=p, configs=configs, type=test_type)
                post_scan = new_scan.second_scan()
                pre_scan = post_scan.paired_scan

            if not post_scan and pre_scan:
                post_scan = S(site=p.site, page=p, scan=pre_scan, configs=configs, type=test_type).second_scan()

            # updating parired scans
            pre_scan.paired_scan = post_scan
            post_scan.paried_scan = pre_scan
            pre_scan.save()
            post_scan.save()

            # updating test object
            test.type = test_type
            test.type = test_type
            test.pre_scan = pre_scan
            test.post_scan = post_scan
            test.save()

            # running tester
            updated_test = T(test=test).run_test(index=index)
            message = 'Tests have completed running'

    
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




def create_many_tests(request):
    site_ids = request.data.get('site_ids')
    page_ids = request.data.get('page_ids')
    configs = request.data.get('configs')
    type = request.data.get('type', ['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'])
    tags = request.data.get('tags')
    user = request.user

    num_succeeded = 0
    succeeded = []
    num_failed = 0
    failed = []
    this_status = True

    if site_ids:
        for id in site_ids:
            data = {
                'site_id': str(id), 
                'configs': configs,
                'type': type,
                'tags': tags,
                'user_id': str(user.id)
            }
            try:
                res = create_test(delay=True, **data)
                if res['success']:
                    num_succeeded += 1
                    succeeded.append(str(id))
                else:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))
            except Exception as e:
                print(e)
                num_failed += 1
                this_status = False
                failed.append(str(id))

    if page_ids:
        for id in page_ids:
            data = {
                'page_id': str(id), 
                'configs': configs,
                'type': type,
                'tags': tags,
                'user_id': str(user.id)
            }
            try:
                res = create_test(delay=True, **data)
                if res['success']:
                    num_succeeded += 1
                    succeeded.append(str(id))
                else:
                    num_failed += 1
                    this_status = False
                    failed.append(str(id))
            except Exception as e:
                print(e)
                num_failed += 1
                this_status = False
                failed.append(str(id))

    data = {
        'success': this_status,
        'num_succeeded': num_succeeded,
        'succeeded': succeeded,
        'num_failed': num_failed,
        'failed': failed, 
    }

    record_api_call(request, data, '201')
    return Response(data, status=status.HTTP_201_CREATED)
    



def get_tests(request):
    user = request.user
    account = Member.objects.get(user=user).account
    test_id = request.query_params.get('test_id')
    page_id = request.query_params.get('page_id')
    time_begin = request.query_params.get('time_begin')
    time_end = request.query_params.get('time_end')
    lean = request.query_params.get('lean')
    

    if test_id != None:

        try:
            test = Test.objects.get(id=test_id)
        except:
            data = {'reason': 'cannot find a Test with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)

        if test.site.account != account:
            data = {'reason': 'retrieve Tests of a Site you do not own'}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = TestSerializer(test, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)


    try:
        page = Page.objects.get(id=page_id)
    except:
        if page_id != None:
            data = {'reason': 'cannot find a Page with that id',}
            this_status = status.HTTP_404_NOT_FOUND
            status_code = '404'
        else:
            data = {'reason': 'you did not provide the page_id'}
            this_status = status.HTTP_400_BAD_REQUEST
            status_code = '400'
        record_api_call(request, data, status_code)
        return Response(data, status=this_status)

    if page.site.account != account:
        data = {'reason': 'retrieve Tests of a Site you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)
    
    if time_begin == None and page != None and time_end != None:
        tests = Test.objects.filter(page=page).filter(time_completed__lte=time_end).order_by('-time_created')
    elif time_end == None and page != None and time_begin != None:  
        tests = Test.objects.filter(page=page).filter(time_completed__gte=time_begin).order_by('-time_created')
    elif time_end != None and time_begin != None and page != None:
        tests = Test.objects.filter(page=page).filter(time_completed__gte=time_begin).filter(time_completed__lte=time_end).order_by('-time_created')
    elif time_end == None and time_begin == None and Site != None:
        tests = Test.objects.filter(page=page).order_by('-time_created')
    else:
        data = {'reason': 'you did not provide the right params',}
        record_api_call(request, data, '400')
        return Response(data, status=status.HTTP_400_BAD_REQUEST)
        
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(tests, request)
    serializer_context = {'request': request,}
    serialized = TestSerializer(result_page, many=True, context=serializer_context)
    if lean is not None:
        serialized = SmallTestSerializer(result_page, many=True, context=serializer_context)
        
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')

    return response




def get_test_lean(request, id):
    user = request.user
    account = Member.objects.get(user=user).account

    try:
        test = Test.objects.get(id=id)
    except:
        data = {'reason': 'cannot find a Test with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)

    if test.site.account != account:
        data = {'reason': 'retrieve Tests of a Site you do not own'}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    # get images_delta if exists
    try:
        images_delta = {"average_score": test.images_delta.get('average_score')}
    except:
        images_delta = None

    # get lighthouse_delta if exists
    try:
        lighthouse_delta = {"scores": test.lighthouse_delta.get('scores')}
    except:
        lighthouse_delta = None

     # get lighthouse_delta if exists
    try:
        yellowlab_delta = {"scores": test.yellowlab_delta['scores']}
    except:
        yellowlab_delta = None

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

    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def delete_test(request, id):
    try:
        test = Test.objects.get(id=id)
    except:
        data = {'reason': 'cannot find a Test with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)
        
    site = test.site
    user = request.user
    account = Member.objects.get(user=user).account

    if site.account != account:
        data = {'reason': 'delete Tests of a Site you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)
    
    delete_test_s3_bg.delay(test.id, test.site.id, test.page.id)
    test.delete()

    data = {'message': 'Test has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def delete_many_tests(request):
    ids = request.data.get('ids')
    user = request.user
    account = Member.objects.get(user=user).account

    if ids is not None:
        count = len(ids)
        num_succeeded = 0
        succeeded = []
        num_failed = 0
        failed = []
        user = request.user
        this_status = True

        for id in ids:
            try:
                test = Test.objects.get(id=id)
                if test.site.account == account:
                    delete_test_s3_bg.delay(test.id, test.site.id, test.page.id)
                    test.delete()
                num_succeeded += 1
                succeeded.append(str(id))
            except:
                num_failed += 1
                failed.append(str(id))
                this_status = False

        data = {
            'success': this_status,
            'num_succeeded': num_succeeded,
            'succeeded': succeeded,
            'num_failed': num_failed,
            'failed': failed, 
        }
        record_api_call(request, data, '200')
        response = Response(data, status=status.HTTP_200_OK)
        return response
    
    data = {
        'reason': 'you must provide an array of id\'s'
    }
    record_api_call(request, data, '400')
    response = Response(data, status=status.HTTP_400_BAD_REQUEST)
    return response








def create_or_update_schedule(request):
    user = request.user
    account = Member.objects.get(user=user).account

    account_is_active = check_account(request=request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)
    try:
        site = Site.objects.get(id=request.data.get('site_id'))
        if site.account != account and site.account != None:
            data = {'reason': 'cannot create a Schedule for a Site you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
    except:
        site = None
    try:
        page = Page.objects.get(id=request.data.get('page_id'))
        if page.account != account and page.account != None:
            data = {'reason': 'cannot create a Schedule for a Page you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
    except:
        page = None
    try:
        schedule = Schedule.objects.get(id=request.data.get('schedule_id'))
        if schedule.account != account and schedule.account != None:
            data = {'reason': 'update a Schedule you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
    except:
        schedule = None


    schedule_status = request.data.get('status', None)
    begin_date_raw = request.data.get('begin_date', None)
    time = request.data.get('time', None)
    timezone = request.data.get('timezone', None)
    freq = request.data.get('frequency', None)
    task_type = request.data.get('task_type', None)
    test_type = request.data.get('test_type', ['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'])
    scan_type = request.data.get('scan_type', ['html', 'logs', 'vrt', 'lighthouse', 'yellowlab'])
    configs = request.data.get('configs', None)
    schedule_id = request.data.get('schedule_id', None)
    site_id = request.data.get('site_id', None)
    page_id = request.data.get('page_id', None)
    case_id = request.data.get('case_id', None)
    updates = request.data.get('updates', None)

    # converting to str for **kwargs
    if site_id is not None:
        site_id = str(site_id)
    if page_id is not None:
        page_id = str(page_id)

    if configs is None:
        configs = {
            'window_size': '1920,1080',
            'driver': 'selenium',
            'device': 'desktop',
            'mask_ids': None,
            'interval': 5,
            'min_wait_time': 10,
            'max_wait_time': 30,
            'timeout': 300,
            'disable_animations': False
        }

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
        # retriving object again to avoid cacheing issues
        schedule_new = Schedule.objects.get(id=request.data.get('schedule_id'))
    
    # if not status change, updating data
    else:
        if Automation.objects.filter(schedule=schedule).exists():
            automation = Automation.objects.filter(schedule=schedule)[0]
            auto_id = str(automation.id)
        else:
            auto_id = None

        if task_type == 'test':
            task = 'api.tasks.create_test_bg'
            arguments = {
                'site_id': site_id,
                'page_id': page_id,
                'configs': configs, 
                'type': test_type,
                'automation_id': auto_id
            }

        if task_type == 'scan':
            task = 'api.tasks.create_scan_bg'
            arguments = {
                'site_id': site_id,
                'page_id': page_id,
                'configs': configs,
                'type': scan_type,
                'automation_id': auto_id
            }

        if task_type == 'report':
            task = 'api.tasks.create_report_bg'
            arguments = {
                'site_id': site_id,
                'page_id': page_id,
                'automation_id': auto_id
            }


        if task_type == 'testcase':
            task = 'api.tasks.create_testcase_bg'
            arguments = {
                'site_id': site_id,
                'page_id': page_id,
                'updates': updates,
                'configs': configs,
                'automation_id': auto_id,
            }

        format_str = '%m/%d/%Y'
        
        try:
            begin_date = datetime.strptime(begin_date_raw, format_str)
        except:
            begin_date = datetime.now()

        num_day_of_week = begin_date.weekday()
        day = begin_date.strftime("%d")
        minute = time[3:5]
        hour = time[0:2]

        if freq == 'daily':
            day_of_week = '*'
            day_of_month = '*'
        elif freq == 'weekly':
            day_of_week = num_day_of_week
            day_of_month = '*'
        elif freq == 'monthly':
            day_of_week = '*'
            day_of_month = day

        
        if site is not None:
            url = site.site_url
            level = 'site'
        if page is not None:
            url = page.page_url
            level = 'page'


        task_name = str(task_type) + '_' + str(level) + '_' + str(url) + '_' + str(freq) + '_@' + str(time) + '_' + str(account.user.id)

        crontab, _ = CrontabSchedule.objects.get_or_create(
            timezone=timezone, 
            minute=minute, 
            hour=hour,
            day_of_week=day_of_week, 
            day_of_month=day_of_month,
        )

        if schedule:
            if PeriodicTask.objects.filter(id=schedule.periodic_task_id).exists():
                periodic_task = PeriodicTask.objects.filter(id=schedule.periodic_task_id)
                periodic_task.update(
                    crontab=crontab,
                    name=task_name, 
                    task=task,
                    kwargs=json.dumps(arguments),
                )
                periodic_task = PeriodicTask.objects.get(id=schedule.periodic_task_id)
            else:
                periodic_task = PeriodicTask.objects.create(
                    crontab=crontab,
                    name=task_name, 
                    task=task,
                    kwargs=json.dumps(arguments),
                )

        else:
            if PeriodicTask.objects.filter(name=task_name).exists():
                data = {'reason': 'Task has already be created',}
                record_api_call(request, data, '401')
                return Response(data, status=status.HTTP_401_UNAUTHORIZED)
                
            periodic_task = PeriodicTask.objects.create(
                crontab=crontab, 
                name=task_name, 
                task=task,
                kwargs=json.dumps(arguments),
            )

        extras = {
            "configs": configs,
            "test_type": test_type,
            "scan_type": scan_type, 
            "case_id": case_id, 
            "updates": updates
        }
        
        if schedule:
            schedule_query = Schedule.objects.filter(id=schedule_id)
            if schedule_query.exists():
                schedule_query.update(
                    user=request.user, 
                    timezone=timezone,
                    begin_date=begin_date, 
                    time=time, 
                    frequency=freq,
                    task=task, 
                    crontab_id=crontab.id, 
                    task_type=task_type,
                    extras=extras, 
                    account=account
                )
                schedule_new = Schedule.objects.get(id=schedule_id)
        else:
            schedule_new = Schedule.objects.create(
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

    serializer_context = {'request': request,}
    data = ScheduleSerializer(schedule_new, context=serializer_context).data
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def get_schedules(request):
    user = request.user
    account = Member.objects.get(user=user).account
    schedule_id = request.query_params.get('schedule_id')
    site_id = request.query_params.get('site_id')
    page_id = request.query_params.get('page_id')

    if schedule_id != None:
        try:
            schedule = Schedule.objects.get(id=schedule_id)
        except:
            data = {'reason': 'cannot find a Schedule with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        if schedule.site.account != user or schedule.account != account:
            data = {'reason': 'cannot retrieve Schedules of a Site you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = ScheduleSerializer(schedule, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    if site_id is not None:
        try:
            site = Site.objects.get(id=site_id)
        except:
            data = {'reason': 'cannot find a Site with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        if site.account != account:
            data = {'reason': 'cannot retrieve Schedules of a Site you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        schedules = Schedule.objects.filter(site=site).order_by('-time_created')
    
    if page_id is not None:
        try:
            page = Page.objects.get(id=page_id)
        except:
            data = {'reason': 'cannot find a Page with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        if page.account != account:
            data = {'reason': 'cannot retrieve Schedules of a Page you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        schedules = Schedule.objects.filter(page=page).order_by('-time_created')
        
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(schedules, request)
    serializer_context = {'request': request,}
    serialized = ScheduleSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def delete_schedule(request, id):

    try:
        schedule = Schedule.objects.get(id=id)
    except:
        data = {'reason': 'cannot find a Schedule with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)

    task = PeriodicTask.objects.get(id=schedule.periodic_task_id)
    user = request.user
    account = Member.objects.get(user=user).account

    if schedule.account != account:
        data = {'reason': 'delete Schedules you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    schedule.delete()
    task.delete()

    data = {'message': 'Schedule has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response








def create_or_update_automation(request):
    user = request.user
    account = Member.objects.get(user=user).account

    account_is_active = check_account(request=request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    try:
        schedule = Schedule.objects.get(id=request.data.get('schedule_id'))
        try:
            automation = Automation.objects.get(id=schedule.automation.id)
            if automation.account != account and automation.account != None:
                data = {'reason': 'update a Automation you do not own',}
                record_api_call(request, data, '403')
                return Response(data, status=status.HTTP_403_FORBIDDEN)
        except:
            automation = None
        if schedule.account != account and schedule.account != None:
            data = {'reason': 'create a Automation of a Schedule you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
    except:
        schedule = None
        automation = None

    # get data 
    name = request.data.get('name')
    expressions = request.data.get('expressions')
    actions = request.data.get('actions')
    site_id = request.data.get('site_id')
    page_id = request.data.get('page_id')

    if automation:
        automation.name = name
        automation.expressions = expressions
        automation.actions = actions
        automation.schedule = schedule
        automation.save()

    if not automation:
        automation = Automation.objects.create(
            name=name, 
            expressions=expressions, 
            actions=actions,
            schedule=schedule, 
            user=request.user, 
            account=account
        )

    if schedule:
        schedule.automation = automation
        schedule.save()
        # update associated periodicTask
        task = PeriodicTask.objects.get(id=schedule.periodic_task_id)
        
        site_id = None
        if schedule.site is not None:
            site_id = str(schedule.site.id)
        page_id = None
        if schedule.page is not None:
            page_id = str(schedule.page.id)

        arguments = {
            'site_id': site_id,
            'page_id': page_id,
            'automation_id': str(automation.id),
            'configs': json.loads(task.kwargs).get('configs', None), 
            'type': json.loads(task.kwargs).get('type', None),
            'case_id': json.loads(task.kwargs).get('case_id', None),
            'updates': json.loads(task.kwargs).get('updates', None)
        }
        task.kwargs=json.dumps(arguments)
        task.save()

    serializer_context = {'request': request,}
    data = AutomationSerializer(automation, context=serializer_context).data
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response

    

def get_automations(request):
    automation_id = request.query_params.get('automation_id')
    user = request.user
    account = Member.objects.get(user=user).account

    if automation_id != None:        
        try:
            automation = Automation.objects.get(id=automation_id)
        except:
            data = {'reason': 'cannot find a Automation with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)

        if automation.account != account:
            data = {'reason': 'retrieve an Automation you do not own',}
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        serializer_context = {'request': request,}
        serialized = AutomationSerializer(automation, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)
    
    automations = Automation.objects.filter(user=user).order_by('-time_created')
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(automations, request)
    serializer_context = {'request': request,}
    serialized = AutomationSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response



def delete_automation(request, id):
    user = request.user
    account = Member.objects.get(user=user).account

    try:
        automation = Automation.objects.get(id=id)
    except:
        data = {'reason': 'cannot find a Automation with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)
    
    if automation.account != account:
        data = {'reason': 'delete an automation you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    automation.delete()

    data = {'message': 'Automation has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response









def create_or_update_report(request):

    user = request.user
    account = Member.objects.get(user=user).account

    report_id = request.data.get('report_id', None)
    page_id = request.data.get('page_id', None)
    report_type = request.data.get('type', ['lighthouse', 'yellowlab'])
    text_color = request.data.get('text_color', '#24262d')
    background_color = request.data.get('background_color', '#e1effd')
    highlight_color = request.data.get('highlight_color', '#4283f8')
    page = Page.objects.get(id=page_id)

    info = {
        "text_color": text_color,
        "background_color": background_color,
        "highlight_color": highlight_color,
    }
    
    if report_id:
        try:
            report = Report.objects.get(id=report_id)
        except:
            data = {'reason': 'cannot find a Report with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)

        if report.account != account:
            data = {'reason': 'update a Report you do not own'}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
    
    else:
        report = Report.objects.create(
            user=request.user, 
            page=page, 
            account=account
        )

    # update report data
    report.info = info
    report.type = report_type
    report.save()
    un_cached_report = Report.objects.get(id=report.id)


    # generate report
    updated_report = R(report=un_cached_report).make_test_report()


    serializer_context = {'request': request,}
    data = ReportSerializer(updated_report, context=serializer_context).data
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response





def get_reports(request):
    page_id = request.query_params.get('page_id', None)
    report_id = request.query_params.get('report_id', None)
    user = request.user 
    account = Member.objects.get(user=user).account

    if page_id:
        try:
            page = Page.objects.get(id=page_id)
            reports = Report.objects.filter(page=page, account=account).order_by('-time_created')
        except:
            data = {'reason': 'cannot find a Page with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        

    if report_id:
        try:
            report = Report.objects.get(id=report_id)
        except:
            data = {'reason': 'cannot find a Report with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)

    if page_id is None and report_id is None:
        reports = Report.objects.filter(user=request.user).order_by('-time_created')

    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(reports, request)
    serializer_context = {'request': request,}
    serialized = ReportSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response
    
    



def delete_report(request, id):
    user = request.user
    account = Member.objects.get(user=user).account

    try:
        report = Report.objects.get(id=id)
    except:
        data = {'reason': 'cannot find a Report with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)

    if report.account != account:
        data = {'reason': 'delete Reports you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    # remove s3 objects
    delete_report_s3_bg.delay(report_id=id)
    
    # remove report
    report.delete()

    data = {'message': 'Report has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def get_processes(request):
    site_id = request.query_params.get('site_id', None)
    process_id = request.query_params.get('process_id', None)

    if site_id:
        try:
            site = Site.objects.get(id=site_id)
        except:
            data = {'reason': 'cannot find a Site with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        processes = Process.objects.filter(site=site).order_by('-time_created')

    if process_id:
        try:
            process = Process.objects.get(id=process_id)
            serializer_context = {'request': request,}
            data = ProcessSerializer(process, context=serializer_context).data
            record_api_call(request, data, '200')
            response = Response(data, status=status.HTTP_200_OK)
            return response
        except:
            data = {'reason': 'cannot find a Process with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)

    if site_id is None and report_id is None:
        processes = Process.objects.all().order_by('-time_created')

    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(processes, request)
    serializer_context = {'request': request,}
    serialized = ProcessSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response













def create_or_update_case(request):
    case_id = request.data.get('case_id')
    steps = request.data.get('steps')
    name = request.data.get('name')
    tags = request.data.get('tags')
    user = request.user
    account = Member.objects.get(user=user).account

    account_is_active = check_account(request=request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    if case_id:
        try:
            case = Case.objects.get(id=case_id)
        except:
            data = {'reason': 'cannot find a Case with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        
        if case.account != account:
            data = {'reason': 'retrieve Cases you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        else:
            case.steps = steps
            case.name = name
            case.tags = tags
            case.save()
    
    else:
        case = Case.objects.create(
            user = request.user,
            name = name, 
            tags = tags,
            steps = steps,
            account = account
        )


    serializer_context = {'request': request,}
    data = CaseSerializer(case, context=serializer_context).data
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response




def get_cases(request):
    case_id = request.query_params.get('case_id')
    user = request.user
    account = Member.objects.get(user=user).account

    if case_id != None:        
        try:
            case = Case.objects.get(id=case_id)
        except:
            data = {'reason': 'cannot find a Case with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)

        if case.account != account:
            data = {'reason': 'retrieve an Case you do not own',}
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = CaseSerializer(case, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)
    
    cases = Case.objects.filter(account=account).order_by('-time_created')
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(cases, request)
    serializer_context = {'request': request,}
    serialized = CaseSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def search_cases(request):
    user = request.user
    account = Member.objects.get(user=user).account
    query = request.query_params.get('query')
    cases = Case.objects.filter(account=account, name__icontains=query).order_by('-time_created')
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(cases, request)
    serializer_context = {'request': request,}
    serialized = CaseSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response 



def delete_case(request, id):
    user = request.user
    account = Member.objects.get(user=user).account

    try:
        case = Case.objects.get(id=id)
    except:
        data = {'reason': 'cannot find a Case with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)
    
    if case.account != account:
        data = {'reason': 'delete an Case you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    case.delete()

    data = {'message': 'Case has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response








def create_testcase(request, delay=False):
    case_id = request.data.get('case_id')
    site_id = request.data.get('site_id')
    updates = request.data.get('updates')
    configs = request.data.get('configs')
    user = request.user
    account = Member.objects.get(user=user).account


    account_is_active = check_account(request=request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    if case_id and site_id:
        try:
            case = Case.objects.get(id=case_id, account=account)
        except:
            data = {'reason': 'cannot find a Case with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)

        try:
            site = Site.objects.get(id=site_id, account=account)
        except:
            data = {'reason': 'cannot find a Site with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)
    
    else:
        data = {'reason': 'you must provide both site_id and case_id'}
        record_api_call(request, data, '409')
        return Response(data, status=status.HTTP_409_CONFLICT)

    steps = case.steps
    for step in steps:
        if step['action']['type'] != None:
            step['action']['time_created'] = None
            step['action']['time_completed'] = None
            step['action']['exception'] = None
            step['action']['passed'] = None

        if step['assertion']['type'] != None:
            step['assertion']['time_created'] = None
            step['assertion']['time_completed'] = None
            step['assertion']['exception'] = None
            step['assertion']['passed'] = None

    if updates != None:
        for update in updates:
            steps[int(update['index'])]['action']['value'] = update['value']

    if configs is None:
        configs = {
            'window_size': '1920,1080',
            'device': 'desktop',
            'interval': 5,
            'min_wait_time': 10,
            'max_wait_time': 30,
        }
        
    testcase = Testcase.objects.create(
        case = case,
        case_name = case.name,
        site = site,
        user = request.user,
        configs = configs, 
        steps = steps,
        account = account
    )

    if delay:
        # pass the newly created Testcase to the backgroud task to run
        create_testcase_bg.delay(testcase_id=testcase.id)
    else:
        # running testcase
        asyncio.run(
            Caser(testcase=testcase).run()
        )
        testcase = Testcase.objects.get(id=testcase.id)

    serializer_context = {'request': request,}
    data = TestcaseSerializer(testcase, context=serializer_context).data
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response




def get_testcases(request):
    testcase_id = request.query_params.get('testcase_id')
    site_id = request.query_params.get('site_id')
    lean = request.query_params.get('lean')
    user = request.user
    account = Member.objects.get(user=user).account

    if testcase_id != None:        
        try:
            testcase = Testcase.objects.get(id=testcase_id)
        except:
            data = {'reason': 'cannot find a Testcase with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)

        if testcase.account != account:
            data = {'reason': 'retrieve an Testcase you do not own',}
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = TestcaseSerializer(testcase, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    if site_id != None:
        try:
            site = Site.objects.get(id=site_id, account=account)
        except:
            data = {'reason': 'cannot find a Site with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        testcases = Testcase.objects.filter(site=site).order_by('-time_created')
    
    else:
        testcases = Testcase.objects.filter(account=account).order_by('-time_created')

    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(testcases, request)
    serializer_context = {'request': request,}
    serialized = TestcaseSerializer(result_page, many=True, context=serializer_context)
    if lean is not None:
        serialized = SmallTestcaseSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response



def delete_testcase(request, id):
    user = request.user
    account = Member.objects.get(user=user).account

    try:
        testcase = Testcase.objects.get(id=id)
    except:
        data = {'reason': 'cannot find a Testcase with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)
    
    if testcase.account != account:
        data = {'reason': 'delete an Testcase you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    # remove s3 objects
    delete_testcase_s3_bg.delay(testcase_id=id)

    testcase.delete()

    data = {'message': 'Testcase has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response











def get_logs(request):

    log_id = request.query_params.get('log_id')
    request_status = request.query_params.get('success')
    request_type = request.query_params.get('request_type')

    if log_id != None:
        log = Log.objects.get(id=log_id)
        if log.user != request.user:
            data = {'reason': 'retrieve Logs you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = LogSerializer(log, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    if request_status != None and request_type != None:
        logs = Log.objects.filter(status=request_status, request_type=request_type, user=request.user).order_by('-time_created')
    elif request_status == None and request_type != None:
        logs = Log.objects.filter(request_type=request_type, user=request.user).order_by('-time_created')
    elif request_status != None and request_type == None:
        logs = Log.objects.filter(status=request_status, user=request.user).order_by('-time_created')
    else:
        logs = Log.objects.filter(user=request.user).order_by('-time_created')

    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(logs, request)
    serializer_context = {'request': request,}
    serialized = LogSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    return response








def migrate_site(request, delay=False):
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
    driver = request.data.get('driver', 'puppeteer')

    site = Site.objects.get(id=site_id)
    process = Process.objects.create(
        site=site,
        type='migration'
    )
    process_id = process.id

    if delay:
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
            process_id, 
            driver
        )
        
        serializer_context = {'request': request,}
        data = ProcessSerializer(process, context=serializer_context).data
        record_api_call(request, data, '201')
        response = Response(data, status=status.HTTP_201_CREATED)
        return response



    if driver == 'selenium':

        # init wordpress
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
            process_id=process.id
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

        if wp_status: 
            data = {
                'success': 'success',
                'message': 'site migration succeeded'
            }
        else:
            data = {
                'success': 'failed',
                'message': 'site migration failed'
            }

        response = Response(data, status=status.HTTP_200_OK)
        record_api_call(request, data, '200')
        return response

    else:

        # init wordpress for puppeteer
        wp_status = asyncio.run(
            W_P(
                login_url=login_url, 
                admin_url=admin_url,
                username=username,
                password=password, 
                wait_time=wait_time,
            ).run_full(plugin_name=plugin_name)
        )

        if wp_status: 
            data = {
                'success': 'success',
                'message': 'site migration succeeded'
            }
        else:
            data = {
                'success': 'failed',
                'message': 'site migration failed'
            }

        response = Response(data, status=status.HTTP_200_OK)
        record_api_call(request, data, '200')
        return response










def create_site_screenshot(request):
    user = request.user
    site_id = request.data.get('site_id', None)
    url = request.data.get('url', None)
    configs = request.data.get('configs', None)
    site = None

    if site_id is not None:
        site = Site.objects.get(id=site_id)

    if configs is not None:
        if configs['driver'] == 'puppeteer':
            data = asyncio.run(I().screenshot_p(site=site, url=url, configs=configs))
        elif configs['driver'] == 'selenium':
            data = I().screenshot(site=site, url=url, configs=configs)
    else:
        data = I().screenshot(site=site, url=url, configs=configs)
    record_api_call(request, data, '201')
    response = Response(data, status=status.HTTP_201_CREATED)
    return response







def get_home_stats(request):
    user = request.user
    account = Member.objects.get(user=user).account
    sites = Site.objects.filter(account=account)
    site_count = sites.count()
    test_count = 0
    scan_count = 0
    schedule_count = 0
    for site in sites:
        tests = Test.objects.filter(site=site)
        scans = Scan.objects.filter(site=site)
        schedules = Schedule.objects.filter(site=site)
        test_count = test_count + tests.count()
        scan_count = scan_count + scans.count()
        schedule_count = schedule_count + schedules.count()

    data = {
        "sites": site_count, 
        "tests": test_count,
        "scans": scan_count,
        "schedules": schedule_count,
    }
    response = Response(data, status=status.HTTP_200_OK)
    return response





def get_site_stats(request):
    user = request.user
    account = Member.objects.get(user=user).account
    site_id = request.query_params.get('site_id')
    site = Site.objects.get(id=site_id)
    pages = Page.objects.filter(site=site)
    page_count = pages.count()
    test_count = 0
    scan_count = 0
    schedule_count = 0
    for page in pages:
        tests = Test.objects.filter(page=page)
        scans = Scan.objects.filter(page=page)
        schedules = Schedule.objects.filter(page=page)
        test_count = test_count + tests.count()
        scan_count = scan_count + scans.count()
        schedule_count = schedule_count + schedules.count()

    data = {
        "pages": page_count, 
        "tests": test_count,
        "scans": scan_count,
        "schedules": schedule_count,
    }
    response = Response(data, status=status.HTTP_200_OK)
    return response





def get_celery_metrics(request):

    # Inspect all nodes.
    i = celery.app.control.inspect()
    # Tasks received, but are still waiting to be executed.
    reserved = i.reserved()
    # Active tasks
    active = i.active()
    
    # init task & replica counters
    # & ratio 
    num_tasks = 0
    num_replicas = 0
    ratio = 0

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

    # return response
    data = {
        "num_tasks": num_tasks,
        "num_replicas": num_replicas,
        "ratio": ratio
    }
    response = Response(data, status=status.HTTP_200_OK)
    return response