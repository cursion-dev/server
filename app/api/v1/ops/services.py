import json, boto3, asyncio
from datetime import datetime
from django.contrib.auth.models import User
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from ...models import *
from rest_framework.response import Response
from rest_framework import status
from .serializers import *
from ...tasks import *
from rest_framework.pagination import LimitOffsetPagination
from ...utils.scanner import Scanner as S
from ...utils.tester import Tester as T
from ...utils.image import Image as I
from ...utils.reporter import Reporter as R
from ...utils.wordpress import Wordpress as W
from ...utils.wordpress_p import Wordpress as W_P






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



def check_account(request):
    if Account.objects.filter(user=request.user).exists():
        account = Account.objects.get(user=request.user)
        if account.active == True:
            return True
        else:
            return False
    else:
        return True



def create_site(request, delay=False):
    site_url = request.data['site_url']
    user = request.user
    sites = Site.objects.filter(user=user)

    account_is_active = check_account(request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    try:
        max_sites = Account.objects.get(user=user).max_sites
    except:
        max_sites = 1

    if sites.count() >= max_sites:
        data = {'reason': 'maximum number of sites reached',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    if Site.objects.filter(site_url=site_url).exists():
        data = {'reason': 'site already exists',}
        record_api_call(request, data, '409')
        return Response(data, status=status.HTTP_409_CONFLICT)
    else:
        site = Site.objects.create(
            site_url=site_url,
            user=user
        )

        if delay == True:
            scan = Scan.objects.create(site=site)
            create_site_bg.delay(site.id, scan.id)
            site.info["latest_scan"]["id"] = str(scan.id)
            site.info["latest_scan"]["time_created"] = str(scan.time_created)
            site.save()
        else:
            S(site=site).first_scan()

        serializer_context = {'request': request,}
        serialized = SiteSerializer(site, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '201')
        response = Response(data, status=status.HTTP_201_CREATED)
        return response







def get_sites(request):
    site_id = request.query_params.get('site_id')
    user = request.user

    if site_id != None:
        
        try:
            site = Site.objects.get(id=site_id)
        except:
            data = {'reason': 'cannot find a Site with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        
        if site.user != user:
            data = {'reason': 'you cannot retrieve a Site you do not own',}
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        serializer_context = {'request': request,}
        serialized = SiteSerializer(site, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)
    
    sites = Site.objects.filter(user=user).order_by('-time_created')
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(sites, request)
    serializer_context = {'request': request,}
    serialized = SiteSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response



def delete_site(request, id):
    user = request.user
    
    try:
        site = Site.objects.get(id=id)
    except:
        data = {'reason': 'cannot find a Site with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)

    if site.user != user:
        data = {'reason': 'you cannot delete Tests of a Site you do not own',}
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




def create_test(request, delay=False):

    account_is_active = check_account(request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    site_id = request.data['site_id']
    user = request.user
    site = Site.objects.get(id=site_id, )
    if site.user != user:
        data = {'reason': 'you cannot create a Test of a Site you do not own'}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)


    # get data from request
    configs = request.data.get('configs', None)
    pre_scan_id = request.data.get('pre_scan', None)
    post_scan_id = request.data.get('post_scan', None)
    index = request.data.get('index', None)
    test_type = request.data.get('type', ['full'])
    pre_scan = None
    post_scan = None
    
    if not configs:
        configs = {
            'window_size': '1920,1080',
            'interval': 5,
            'driver': 'selenium',
            'device': 'desktop',
            'mask_ids': None,
            'min_wait_time': 10,
            'max_wait_time': 60,
        }

    
    if pre_scan_id:
        pre_scan = Scan.objects.get(id=pre_scan_id)
    if post_scan_id:
        post_scan = Scan.objects.get(id=post_scan_id)


    if not Scan.objects.filter(site=site).exists() or Scan.objects.filter(site=site)[0].html == None:
        data = {'reason': 'Site not yet onboarded'}
        record_api_call(request, data, '400')
        return Response(data, status=status.HTTP_400_BAD_REQUEST)


    # creating test object
    test = Test.objects.create(
        site=site,
        type=test_type,
    )

    
    if delay == True:
        create_test_bg.delay(
            test_id=test.id,
            configs=configs,
            type=test_type,
            index=index,
            pre_scan=pre_scan_id, 
            post_scan=post_scan_id
        )
        data = {
            'message': 'test is being created in the background',
            'id': str(test.id),
        }
        record_api_call(request, data, '201')
        return Response(data, status=status.HTTP_201_CREATED)
    
    else:
        if not pre_scan and not post_scan:
            new_scan = S(site=site, configs=configs)
            post_scan = new_scan.second_scan()
            pre_scan = post_scan.paired_scan

        if not post_scan and pre_scan:
            post_scan = S(site=site, scan=pre_scan, configs=configs).second_scan()

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

        serializer_context = {'request': request,}
        serialized = TestSerializer(updated_test, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '201')
        response = Response(data, status=status.HTTP_201_CREATED)
        return response 








def get_tests(request):
    user = request.user
    test_id = request.query_params.get('test_id')
    site_id = request.query_params.get('site_id')
    time_begin = request.query_params.get('time_begin')
    time_end = request.query_params.get('time_end')
    small = request.query_params.get('small')

    if test_id != None:

        try:
            test = Test.objects.get(id=test_id)
        except:
            data = {'reason': 'cannot find a Test with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)

        if test.site.user != user:
            data = {'reason': 'you cannot retrieve Tests of a Site you do not own'}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = TestSerializer(test, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)


    try:
        site = Site.objects.get(id=site_id)
    except:
        if site_id != None:
            data = {'reason': 'cannot find a site with that id',}
            this_status = status.HTTP_404_NOT_FOUND
            status_code = '404'
        else:
            data = {'reason': 'you did not provide the site_id'}
            this_status = status.HTTP_400_BAD_REQUEST
            status_code = '400'
        record_api_call(request, data, status_code)
        return Response(data, status=this_status)

    if site.user != user:
        data = {'reason': 'you cannot retrieve Tests of a Site you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)
    
    if time_begin == None and site != None and time_end != None:
        tests = Test.objects.filter(site=site).filter(time_completed__lte=time_end).order_by('-time_created')
    elif time_end == None and site != None and time_begin != None:  
        tests = Test.objects.filter(site=site).filter(time_completed__gte=time_begin).order_by('-time_created')
    elif time_end != None and time_begin != None and site != None:
        tests = Test.objects.filter(site=site).filter(time_completed__gte=time_begin).filter(time_completed__lte=time_end).order_by('-time_created')
    elif time_end == None and time_begin == None and Site != None:
        tests = Test.objects.filter(site=site).order_by('-time_created')
    else:
        data = {'reason': 'you did not provide the right params',}
        record_api_call(request, data, '400')
        return Response(data, status=status.HTTP_400_BAD_REQUEST)
        
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(tests, request)
    serializer_context = {'request': request,}
    if small != None:
        serialized = SmallTestSerializer(result_page, many=True, context=serializer_context)
    else:
        serialized = TestSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')

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

    if site.user != user:
        data = {'reason': 'you cannot delete Tests of a Site you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    test.delete()

    data = {'message': 'Test has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response





def create_scan(request, delay=False):

    site_id = request.data['site_id']
    user = request.user
    
    try:
        site = Site.objects.get(id=site_id)
    except:
        data = {'reason': 'cannot find a Site with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)

    account_is_active = check_account(request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)
    
    if site.user != user:
        data = {'reason': 'you cannot create a Scan of a Site you do not own',}
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
        }

    # creating scan obj
    created_scan = Scan.objects.create(site=site)

    if delay == True:
        create_scan_bg.delay(scan_id=created_scan.id, configs=configs)
        data = {
            'message': 'scan is being created in the background',
            'id': str(created_scan.id),
        }
        record_api_call(request, data, '201')
        return Response(data, status=status.HTTP_201_CREATED)
    else:
        updated_scan = S(scan=created_scan, configs=configs).first_scan()
        serializer_context = {'request': request,}
        serialized = ScanSerializer(updated_scan, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '201')
        response = Response(data, status=status.HTTP_201_CREATED)
        return response





def get_scans(request):

    user = request.user
    scan_id = request.query_params.get('scan_id')
    site_id = request.query_params.get('site_id')
    time_begin = request.query_params.get('time_begin')
    time_end = request.query_params.get('time_end')
    small = request.query_params.get('small')

    if scan_id != None:
        try:
            scan = Scan.objects.get(id=scan_id)
        except:
            data = {'reason': 'cannot find a Scan with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)

        if scan.site.user != user:
            data = {'reason': 'you cannot retrieve Scans of a Site you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = ScanSerializer(scan, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    
    try:
        site = Site.objects.get(id=site_id)
    except:
        data = {'reason': 'cannot find a Site with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)
    

    if site.user != user:
        data = {'reason': 'you cannot retrieve Scans of a Site you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    
    if time_begin == None and site != None and time_end != None:
        scans = Scan.objects.filter(site=site).filter(time_created__lte=time_end).order_by('-time_created')
    elif time_end == None and site != None and time_begin != None:  
        scans = Scan.objects.filter(site=site).filter(time_created__gte=time_begin).order_by('-time_created')
    elif time_end == None and time_begin == None and site != None:
        scans = Scan.objects.filter(site=site).order_by('-time_created')
    elif time_end != None and time_begin != None and site != None:
        scans = Scan.objects.filter(site=site).filter(time_created__gte=time_begin).filter(time_created__lte=time_end).order_by('-time_created')

        
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(scans, request)
    serializer_context = {'request': request,}
    if small != None:
        serialized = SmallScanSerializer(result_page, many=True, context=serializer_context)
    else:
        serialized = ScanSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response



def delete_scan(request, id):
    try:
        scan = Scan.objects.get(id=scan_id)
    except:
        data = {'reason': 'cannot find a Scan with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)
        
    site = scan.site
    user = request.user

    if site.user != user:
        data = {'reason': 'you cannot delete Scans of a Site you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    scan.delete()

    data = {'message': 'Scan has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response



def create_or_update_schedule(request):

    account_is_active = check_account(request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    try:
        site = Site.objects.get(id=request.data['site_id'])
        if site.user != request.user and site.user != None:
            data = {'reason': 'you cannot create a Schedule of a Site you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
    except:
        site = None
    try:
        schedule = Schedule.objects.get(id=request.data['schedule_id'])
        if schedule.user != request.user and schedule.user != None:
            data = {'reason': 'you cannot update a Schedule you do not own',}
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
    test_type = request.data.get('test_type', None)
    configs = request.data.get('configs', None)
    schedule_id = request.data.get('schedule_id', None)

    

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
        schedule_new = Schedule.objects.get(id=request.data['schedule_id'])
    
    # if not status change, updating data
    else:

        if Automation.objects.filter(schedule=schedule).exists():
            automation = Automation.objects.filter(schedule=schedule)[0]
            auto_id = automation.id
        else:
            auto_id = None

        if task_type == 'test':
            task = 'api.tasks.create_test_bg'
            arguments = {
                'site_id': str(site.id),
                'configs': configs, 
                'type': test_type,
                'automation_id': str(auto_id)
            }

        if task_type == 'scan':
            task = 'api.tasks.create_scan_bg'
            arguments = {
                'site_id': str(site.id),
                'configs': configs,
                'automation_id': str(auto_id)
            }

        if task_type == 'report':
            task = 'api.tasks.create_report_bg'
            arguments = {
                'site_id': str(site.id),
                'automation_id': str(auto_id)
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


        task_name = str(task_type) + '_' + str(site.site_url) + '_' + str(freq) + '_@' + str(time)

        crontab, _ = CrontabSchedule.objects.get_or_create(
            timezone=timezone, minute=minute, hour=hour,
            day_of_week=day_of_week, day_of_month=day_of_month,
        )

        if schedule:
            if PeriodicTask.objects.filter(id=schedule.periodic_task_id).exists():
                periodic_task = PeriodicTask.objects.filter(id=schedule.periodic_task_id)
                periodic_task.update(
                    crontab=crontab,
                    name=task_name, task=task,
                    kwargs=json.dumps(arguments),
                )
                periodic_task = PeriodicTask.objects.get(id=schedule.periodic_task_id)
            else:
                periodic_task = PeriodicTask.objects.create(
                crontab=crontab, name=task_name, task=task,
                kwargs=json.dumps(arguments),
            )

        else:
            if PeriodicTask.objects.filter(name=task_name).exists():
                data = {'reason': 'Task has already be created',}
                record_api_call(request, data, '401')
                return Response(data, status=status.HTTP_401_UNAUTHORIZED)
                
            periodic_task = PeriodicTask.objects.create(
                crontab=crontab, name=task_name, task=task,
                kwargs=json.dumps(arguments),
            )

        extras = {
            "configs": configs,
            "test_type": test_type,
        }
        
        if schedule:
            schedule_query = Schedule.objects.filter(id=schedule_id)
            if schedule_query.exists():
                schedule_query.update(
                    user=request.user, timezone=timezone,
                    begin_date=begin_date, time=time, frequency=freq,
                    task=task, crontab_id=crontab.id, task_type=task_type,
                    extras=extras
                )
                schedule_new = Schedule.objects.get(id=schedule_id)
        else:
            schedule_new = Schedule.objects.create(
                user=request.user, site=site, task_type=task_type, timezone=timezone,
                begin_date=begin_date, time=time, frequency=freq,
                task=task, crontab_id=crontab.id,
                periodic_task_id=periodic_task.id,
                extras=extras 
            )

    serializer_context = {'request': request,}
    data = ScheduleSerializer(schedule_new, context=serializer_context).data
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response




def get_schedules(request):
    user = request.user
    schedule_id = request.query_params.get('schedule_id')
    site_id = request.query_params.get('site_id')


    if schedule_id != None:
        try:
            schedule = Schedule.objects.get(id=schedule_id)
        except:
            data = {'reason': 'cannot find a Schedule with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)

        if schedule.site.user != user or schedule.user != user:
            data = {'reason': 'you cannot retrieve Schedules of a Site you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = ScheduleSerializer(schedule, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)


    try:
        site = Site.objects.get(id=site_id)
    except:
        data = {'reason': 'cannot find a Site with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)

    if site.user != user:
        data = {'reason': 'you cannot retrieve Schedules of a Site you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)
    
    schedules = Schedule.objects.filter(site=site).order_by('-time_created')
        
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(schedules, request)
    serializer_context = {'request': request,}
    serialized = ScheduleSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    record_api_call(request, response.data, '200')
    return response




def delete_schedule(request, id):
    try:
        schedule = Schedule.objects.get(id=schedule_id)
    except:
        data = {'reason': 'cannot find a Schedule with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)

    task = PeriodicTask.objects.get(id=schedule.periodic_task_id)
    site = schedule.site
    user = request.user

    if site.user != user:
        data = {'reason': 'you cannot delete Schedules you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    schedule.delete()
    task.delete()

    data = {'message': 'Schedule has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response







def create_or_update_automation(request):

    account_is_active = check_account(request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    try:
        schedule = Schedule.objects.get(id=request.data['schedule_id'])
        try:
            automation = Automation.objects.get(id=schedule.automation.id)
            if automation.user != request.user and automation.user != None:
                data = {'reason': 'you cannot update a Automation you do not own',}
                record_api_call(request, data, '403')
                return Response(data, status=status.HTTP_403_FORBIDDEN)
        except:
            automation = None
        if schedule.user != request.user and schedule.user != None:
            data = {'reason': 'you cannot create a Automation of a Schedule you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
    except:
        schedule = None
        automation = None

    # get data 
    name = request.data['name']
    expressions = request.data['expressions']
    actions = request.data['actions']

    if automation:
        automation.name = name
        automation.expressions = expressions
        automation.actions = actions
        automation.schedule = schedule
        automation.save()

    if not automation:
        automation = Automation.objects.create(
            name=name, expressions=expressions, actions=actions,
            schedule=schedule, user=request.user,
        )

    if schedule:
        schedule.automation = automation
        schedule.save()
        # update associated periodicTask
        task = PeriodicTask.objects.get(id=schedule.periodic_task_id)
        arguments = {
            'site_id': str(schedule.site.id),
            'automation_id': str(automation.id),
            'configs': json.loads(task.kwargs).get('configs', None), 
            'type': json.loads(task.kwargs).get('type', None),
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
    if automation_id != None:        
        try:
            automation = Automation.objects.get(id=automation_id)
        except:
            data = {'reason': 'cannot find a Automation with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)

        if automation.user != user:
            data = {'reason': 'you cannot retrieve an Automation you do not own',}
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
    try:
        automation = Automation.objects.get(id=automation_id)
    except:
        data = {'reason': 'cannot find a Automation with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)
    
    if automation.user != request.user:
        data = {'reason': 'you cannot delete an automation you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    automation.delete()

    data = {'message': 'Automation has been deleted',}
    record_api_call(request, data, '200')
    response = Response(data, status=status.HTTP_200_OK)
    return response









def create_or_update_report(request):

    report_id = request.data.get('report_id', None)
    site_id = request.data.get('site_id', None)
    report_type = request.data.get('type', ['full'])
    text_color = request.data.get('text_color', '#24262d')
    background_color = request.data.get('background_color', '#e1effd')
    highlight_color = request.data.get('highlight_color', '#4283f8')
    site = Site.objects.get(id=site_id)

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
    else:
        report = Report.objects.create(
            user=request.user, site=site
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
    site_id = request.query_params.get('site_id', None)
    report_id = request.query_params.get('report_id', None)

    if site_id:
        try:
            site = Site.objects.get(id=site_id)
        except:
            data = {'reason': 'cannot find a Site with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        reports = Report.objects.filter(site=site, user=request.user).order_by('-time_created')

    if report_id:
        try:
            report = Report.objects.get(id=report_id)
        except:
            data = {'reason': 'cannot find a Report with that id'}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)

    if site_id is None and report_id is None:
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
    try:
        report = Report.objects.get(id=report_id)
    except:
        data = {'reason': 'cannot find a Report with that id'}
        record_api_call(request, data, '404')
        return Response(data, status=status.HTTP_404_NOT_FOUND)

    if report.user != user:
        data = {'reason': 'you cannot delete Reports you do not own',}
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





def get_logs(request):

    log_id = request.query_params.get('log_id')
    request_status = request.query_params.get('status')
    request_type = request.query_params.get('request_type')

    if log_id != None:
        log = Log.objects.get(id=log_id)
        if log.user != request.user:
            data = {'reason': 'you cannot retrieve Logs you do not own',}
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





def install_wp_plugin(request):
    login_url = request.data.get('login_url', None)
    admin_url = request.data.get('admin_url', None)
    plugin_name = request.data.get('plugin_name', None)
    username = request.data.get('username', None)
    password = request.data.get('password', None)
    wait_time = request.data.get('wait_time', 30)
    driver = request.data.get('driver', 'selenium')

    if driver == 'selenium':

        # init wordpress
        wp = W(
            login_url=login_url, 
            admin_url=admin_url,
            username=username,
            password=password, 
            wait_time=wait_time,
        )

        # login
        wp_status = wp.login()

        # adjust lang
        wp_status = wp.begin_lang_check()

        # install plugin
        wp_status = wp.install_plugin(plugin_name=plugin_name)

        # re adjust lang
        wp_status = wp.end_lang_check()

        if wp_status: 
            data = {
                'status': 'success',
                'message': 'plugin installed successfully'
            }
        else:
            data = {
                'status': 'failed',
                'message': 'plugin installation failed'
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
                'status': 'success',
                'message': 'plugin installed successfully'
            }
        else:
            data = {
                'status': 'failed',
                'message': 'plugin installation failed'
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
    sites = Site.objects.filter(user=request.user)
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


