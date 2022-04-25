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
        if site.user != request.user:
            data = {'reason': 'you cannot retrieve a Site you do not own',}
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
        if scan.site.user != request.user:
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


class ScanDelay(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]

    def post(self, request):
        response = create_scan(request, delay=True)
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
        if test.site.user != request.user:
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


class TestDelay(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]

    def post(self, request):
        response = create_test(request, delay=True)
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
        if schedule.site.user != request.user:
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
        if report.user != request.user:
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




class WordPressPluginInstall(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]
    
    def post(self, request):
        response = install_wp_plugin(request)
        return response


class SiteScreenshot(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]
    
    def post(self, request):
        response = create_site_screenshot(request)
        return response