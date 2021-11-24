import json, datetime
from django.contrib.auth.models import User
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from ...models import (Test, Site, Scan, Log, Automation)
from rest_framework.response import Response
from rest_framework import status
from ...models import (Test, Site, Scan, Log, Schedule, Account)
from .serializers import (
    SiteSerializer, TestSerializer, ScanSerializer, LogSerializer, 
    ScheduleSerializer, AutomationSerializer, SmallTestSerializer, 
    SmallScanSerializer,
    )
from rest_framework.pagination import LimitOffsetPagination
from django.urls import resolve
from ...scan_tests.scan_site import ScanSite
from ...scan_tests.lighthouse import Lighthouse
from ...scan_tests.tester import Test as T
from ...tasks import (create_site_bg, create_scan_bg, create_test_bg)





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
        return False



def create_site(request, delay=False):
    site_url = request.data['site_url']
    user = request.user
    sites = Site.objects.filter(user=user)

    account_is_active = check_account(request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

    account = Account.objects.get(user=user)
    if sites.count() >= account.max_sites:
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
            create_site_bg.delay(site.id)
        else:
            ScanSite(site=site).first_scan()

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
        site = Site.objects.get(id=site_id)
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
    site = Site.objects.get(id=id)

    if site.user != user:
        data = {'reason': 'you cannot delete Tests of a Site you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

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
        data = {'reason': 'you cannot create a Test of a Site you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)
    
    if delay == True:
        create_test_bg.delay(site.id)
        data = {'message': 'test is being created in the background'}
        record_api_call(request, data, '201')
        return Response(data, status=status.HTTP_201_CREATED)
    else:
        test = Test.objects.create(site=site)
        new_scan = ScanSite(site=site)
        post_scan = new_scan.second_scan()
        pre_scan = post_scan.paired_scan
        pre_scan.paired_scan = post_scan
        pre_scan.save()
        test.pre_scan = pre_scan
        test.post_scan = post_scan
        test.save()

        updated_test = T(test=test).run_full_test()

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
        test = Test.objects.get(id=test_id)

        if test.site.user != user:
            data = {'reason': 'you cannot retrieve Tests of a Site you do not own',}
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
    test = Test.objects.get(id=id)
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
    site = Site.objects.get(id=site_id)

    account_is_active = check_account(request)
    if not account_is_active:
        data = {'reason': 'account not funded',}
        record_api_call(request, data, '402')
        return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)
    
    if site.user != user:
        data = {'reason': 'you cannot create a Scan of a Site you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)
    
    if delay == True:
        create_scan_bg.delay(site.id)
        data = {'message': 'scan is being created in the background'}
        record_api_call(request, data, '201')
        return Response(data, status=status.HTTP_201_CREATED)
    else:
        created_scan = Scan.objects.create(site=site)
        updated_scan = ScanSite(scan=created_scan).first_scan()
        
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
        scan = Scan.objects.get(id=scan_id)

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
    scan = Scan.objects.get(id=id)
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

    try:
        schedule_status = request.data['status']
    except:
        schedule_status = None
    
    try:
        begin_date_raw = request.data['begin_date']
        time = request.data['time']
        timezone = request.data['timezone']
        freq = request.data['frequency']
        task_type = request.data['task_type']
    except:
        pass

    try:
        schedule_id = request.data['schedule_id']
    except:
        schedule_id = None
    

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
    else:
        if task_type == 'test':
            task = 'api.tasks.create_test_bg'
            arguments = {
                'site_id': str(site.id),
            }

        if task_type == 'scan':
            task = 'api.tasks.create_scan_bg'
            arguments = {
                'site_id': str(site.id),
            }

        format_str = '%m/%d/%Y'
        
        try:
            begin_date = datetime.datetime.strptime(begin_date_raw, format_str)
        except:
            begin_date = datetime.datetime.now()

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
                )
                periodic_task = PeriodicTask.objects.get(id=schedule.periodic_task_id)
            elif PeriodicTask.objects.filter(name=task_name).exists():
                data = {'reason': 'Task has already be created',}
                record_api_call(request, data, '401')
                return Response(data, status=status.HTTP_401_UNAUTHORIZED)
            else:
                periodic_task = PeriodicTask.objects.create(
                crontab=crontab, name=task_name, task=task,
                kwargs=json.dumps(arguments),
            )

        else:
            periodic_task = PeriodicTask.objects.create(
                crontab=crontab, name=task_name, task=task,
                kwargs=json.dumps(arguments),
            )

        
        if schedule:
            schedule_query = Schedule.objects.filter(id=schedule_id)
            if schedule_query.exists():
                schedule_query.update(
                    user=request.user, timezone=timezone,
                    begin_date=begin_date, time=time, frequency=freq,
                    task=task, crontab_id=crontab.id, task_type=task_type,
                )
                schedule_new = Schedule.objects.get(id=schedule_id)
        else:
            schedule_new = Schedule.objects.create(
                user=request.user, site=site, task_type=task_type, timezone=timezone,
                begin_date=begin_date, time=time, frequency=freq,
                task=task, crontab_id=crontab.id,
                periodic_task_id=periodic_task.id, 
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
        schedule = Schedule.objects.get(id=schedule_id)

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
    schedule = Schedule.objects.get(id=id)
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
        automation = Automation.objects.get(id=automation_id)
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
    automation = Automation.objects.get(id=id)
    
    if automation.user != request.user:
        data = {'reason': 'you cannot delete an automation you do not own',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    automation.delete()

    data = {'message': 'Automation has been deleted',}
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


