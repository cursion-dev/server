from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from ...models import *
from django.urls import path, include
from rest_framework import routers, serializers, viewsets
from rest_framework.viewsets import ViewSet
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.pagination import LimitOffsetPagination
from django.urls import resolve
from .serializers import *
from .services import *



class Sites(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post', 'get']
    pagination_class = LimitOffsetPagination

    def post(self, request):
        response = create_site(request)
        return response

    def get(self, request):
        response = get_sites(request)
        return response
    


class SiteDetail(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        site = get_object_or_404(Site, pk=id)
        user = request.user
        account = Member.objects.get(user=user).account
        if site.account != account:
            data = {'reason': 'you cannot retrieve a Site you do not own',}
            record_api_call(request, data, '401')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        serializer_context = {'request': request,}
        serialized = SiteSerializer(site, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK) 

    def delete(self, request, id):
        response = delete_site(request, id)
        return response



class SiteDelay(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]

    def post(self, request):
        response = create_site(request, delay=True)
        return response



class SitesDelete(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]

    def post(self, request):
        response = delete_many_sites(request)
        return response




class Scans(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post', 'get',]
    pagination_class = LimitOffsetPagination

    def post(self, request):
        response = create_scan(request)
        return response

    def get(self, request):
        response = get_scans(request)
        return response


class ScanDetail(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get', 'delete',]

    def get(self, request, id):
        scan = get_object_or_404(Scan, pk=id)
        user = request.user
        account = Member.objects.get(user=user).account

        if scan.site.account != account:
            data = {'reason': 'you cannot retrieve Scans of a Site you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = ScanSerializer(scan, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)


    def delete(self, request, id):
        response = delete_scan(request, id)
        return response


class ScanLean(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get', ]

    def get(self, request, id):
        response = get_scan_lean(request, id)
        return response


class ScanDelay(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]

    def post(self, request):
        response = create_scan(request, delay=True)
        return response


class ScansDelete(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]

    def post(self, request):
        response = delete_many_scans(request)
        return response





class Tests(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post', 'get',]
    pagination_class = LimitOffsetPagination

    def post(self, request):
        response = create_test(request)
        return response
    
    def get(self, request):
        response = get_tests(request)
        return response


class TestDetail(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get', 'delete',]

    def get(self, request, id):
        test = get_object_or_404(Test, pk=id)
        user = request.user
        account = Member.objects.get(user=user).account

        if test.site.account != account:
            data = {'reason': 'you cannot retrieve Tests of a Site you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = TestSerializer(test, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    def delete(self, request, id):
        response = delete_test(request, id)
        return response


class TestLean(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get',]

    def get(self, request, id):
        response = get_test_lean(request, id)
        return response


class TestDelay(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]

    def post(self, request):
        response = create_test(request, delay=True)
        return response


class TestsDelete(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]

    def post(self, request):
        response = delete_many_tests(request)
        return response






class Schedules(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post', 'get']

    def post(self, request):
        response = create_or_update_schedule(request)        
        return response
    
    def get(self, request):
        response = get_schedules(request)
        return response


class ScheduleDetail(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        schedule = get_object_or_404(Schedule, pk=id)
        user = request.user
        account = Member.objects.get(user=user).account

        if schedule.site.account != account:
            data = {'reason': 'you cannot retrieve Schedules of a Site you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = ScheduleSerializer(schedule, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    def delete(self, request, id):
        response = delete_schedule(request, id)        
        return response





class Automations(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get', 'post']
    pagination_class = LimitOffsetPagination

    def post(self, request):
        response = create_or_update_automation(request)
        return response
    
    def get(self, request):
        response = get_automations(request)
        return response


class AutomationDetail(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        automation = get_object_or_404(Automation, pk=id)
        user = request.user
        account = Member.objects.get(user=user).account

        if automation.user != request.user:
            data = {'reason': 'you cannot retrieve Automations you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = AutomationSerializer(automation, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    def delete(self, request, id):
        response = delete_automation(request, id)        
        return response





class Reports(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post', 'get']

    def post(self, request):
        response = create_or_update_report(request)        
        return response
    
    def get(self, request):
        response = get_reports(request)
        return response



class ReportDetail(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        report = get_object_or_404(Report, pk=id)
        user = request.user
        account = Member.objects.get(user=user).account
        
        if report.account != account:
            data = {'reason': 'you cannot retrieve Reports you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = ReportSerializer(report, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    def delete(self, request, id):
        response = delete_report(request, id)        
        return response








class Cases(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post', 'get']

    def post(self, request):
        response = create_or_update_case(request)        
        return response
    
    def get(self, request):
        response = get_cases(request)
        return response



class CasesSearch(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get']

    def get(self, request):
        response = search_cases(request)
        return response



class CaseDetail(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        case = get_object_or_404(Case, pk=id)
        user = request.user
        account = Member.objects.get(user=user).account
        
        if case.account != account:
            data = {'reason': 'you cannot retrieve Cases you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = CaseSerializer(case, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    def delete(self, request, id):
        response = delete_case(request, id)        
        return response



class Testcases(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post', 'get']

    def post(self, request):
        response = create_testcase(request)        
        return response
    
    def get(self, request):
        response = get_testcases(request)
        return response



class TestcaseDelay(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]

    def post(self, request):
        response = create_testcase(request, delay=True)
        return response



class TestcaseDetail(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        testcase = get_object_or_404(Testcase, pk=id)
        user = request.user
        account = Member.objects.get(user=user).account
        
        if testcase.account != account:
            data = {'reason': 'you cannot retrieve Testcases you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = TestcaseSerializer(testcase, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)

    def delete(self, request, id):
        response = delete_testcase(request, id)        
        return response





class Logs(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get',]
    pagination_class = LimitOffsetPagination
    
    def get(self, request):
        response = get_logs(request)
        return response 


class LogDetail(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get',]

    def get(self, request, id):
        log = get_object_or_404(Log, pk=id)
        if log.user != request.user:
            data = {'reason': 'you cannot retrieve Logs you do not own',}
            record_api_call(request, data, '403')
            return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        serializer_context = {'request': request,}
        serialized = LogSerializer(log, context=serializer_context)
        data = serialized.data
        return Response(data, status=status.HTTP_200_OK)



class HomeStats(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get',]

    def get(self, request):
        response = get_home_stats(request)
        return response




class Processes(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get']
    
    def get(self, request):
        response = get_processes(request)
        return response


class ProcessDetail(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get',]

    def get(self, request, id):
        if not Process.objects.filter(id=id).exists():
            data = {'reason': 'process with that id does not exist',}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        
        proc = Process.objects.get(id=id)
        serializer_context = {'request': request,}
        serialized = ProcessSerializer(proc, context=serializer_context)
        data = serialized.data
        record_api_call(request, data, '200')
        return Response(data, status=status.HTTP_200_OK)



class WordPressMigrateSite(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]
    
    def post(self, request):
        response = migrate_site(request, delay=False)
        return response


class WordPressMigrateSiteDelay(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]
    
    def post(self, request):
        response = migrate_site(request, delay=True)
        return response


class SiteScreenshot(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]
    
    def post(self, request):
        response = create_site_screenshot(request)
        return response