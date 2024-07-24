from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from ...models import *
from django.urls import path, include
from rest_framework import routers, serializers, viewsets
from rest_framework.viewsets import ViewSet
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.pagination import LimitOffsetPagination
from django.urls import resolve
from .serializers import *
from .services import *






### ------ Begin Site Views ------ ###




class Sites(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post', 'get']
    pagination_class = LimitOffsetPagination

    def post(self, request):
        response = create_site(request)
        return response

    def get(self, request):
        response = get_sites(request)
        return response




class SiteDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        response = get_site(request, id)
        return response

    def delete(self, request, id):
        response = delete_site(request, id)
        return response




class SiteDelay(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = create_site(request, delay=True)
        return response




class SiteCrawl(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request, id):
        response = crawl_site(request, id)
        return response




class SitesDelete(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = delete_many_sites(request)
        return response




class SitesZapier(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = get_sites_zapier(request)
        return response




### ------ Begin Page Views ------ ###




class Pages(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post', 'get']
    pagination_class = LimitOffsetPagination

    def post(self, request):
        response = create_page(request)
        return response

    def get(self, request):
        response = get_pages(request)
        return response
    



class PageDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        response = get_page(request, id)
        return response 

    def delete(self, request, id):
        response = delete_page(request, id)
        return response




class PageDelay(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = create_page(request, delay=True)
        return response




class PagesDelete(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = delete_many_pages(request)
        return response




class PagesZapier(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = get_pages_zapier(request)
        return response




### ------ Begin Scan Views ------ ###




class Scans(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post', 'get',]
    pagination_class = LimitOffsetPagination

    def post(self, request):
        response = create_scan(request)
        return response

    def get(self, request):
        response = get_scans(request)
        return response




class ScanDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete',]

    def get(self, request, id):
        response = get_scan(request, id)
        return response


    def delete(self, request, id):
        response = delete_scan(request, id)
        return response




class ScanLean(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', ]

    def get(self, request, id):
        response = get_scan_lean(request, id)
        return response




class ScanDelay(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = create_scan(request, delay=True)
        return response




class ScansCreate(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = create_many_scans(request)
        return response




class ScansDelete(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = delete_many_scans(request)
        return response




class ScansZapier(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = get_scans_zapier(request)
        return response




### ------ Begin Test Views ------ ###




class Tests(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post', 'get',]
    pagination_class = LimitOffsetPagination

    def post(self, request):
        response = create_test(request)
        return response
    
    def get(self, request):
        response = get_tests(request)
        return response




class TestDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete',]

    def get(self, request, id):
        response = get_test(request, id)
        return response

    def delete(self, request, id):
        response = delete_test(request, id)
        return response




class TestLean(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get',]

    def get(self, request, id):
        response = get_test_lean(request, id)
        return response




class TestDelay(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = create_test(request, delay=True)
        return response




class TestsCreate(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = create_many_tests(request)
        return response




class TestsDelete(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = delete_many_tests(request)
        return response




class TestsZapier(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = get_tests_zapier(request)
        return response




### ------ Begin Schedule Views ------ ###




class Schedules(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post', 'get']

    def post(self, request):
        response = create_or_update_schedule(request)        
        return response
    
    def get(self, request):
        response = get_schedules(request)
        return response




class ScheduleDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        response = get_schedule(request, id)
        return response

    def delete(self, request, id):
        response = delete_schedule(request, id)        
        return response




### ------ Begin Automation Views ------ ###




class Automations(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'post']
    pagination_class = LimitOffsetPagination

    def post(self, request):
        response = create_or_update_automation(request)
        return response
    
    def get(self, request):
        response = get_automations(request)
        return response




class AutomationDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        response = get_automation(request, id)
        return response

    def delete(self, request, id):
        response = delete_automation(request, id)        
        return response




### ------ Begin Report Views ------ ###




class Reports(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post', 'get']

    def post(self, request):
        response = create_or_update_report(request)        
        return response
    
    def get(self, request):
        response = get_reports(request)
        return response




class ReportDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        response = get_report(request, id)
        return response

    def delete(self, request, id):
        response = delete_report(request, id)        
        return response




class ExportReport(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = export_report(request) 
        return response




### ------ Begin Case Views ------ ###



class Cases(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post', 'get']

    def post(self, request):
        response = create_or_update_case(request)        
        return response
    
    def get(self, request):
        response = get_cases(request)
        return response




class CasesSearch(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = search_cases(request)
        return response




class CaseDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        response = get_case(request, id)
        return response

    def delete(self, request, id):
        response = delete_case(request, id)        
        return response




class AutoCases(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post']

    def post(self, request):
        response = create_auto_cases(request)  
        return response




class CopyCases(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post']

    def post(self, request):
        response = copy_case(request)  
        return response




### ------ Begin Testcase Views ------ ###




class Testcases(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post', 'get']

    def post(self, request):
        response = create_testcase(request)        
        return response
    
    def get(self, request):
        response = get_testcases(request)
        return response




class TestcaseDelay(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = create_testcase(request, delay=True)
        return response




class TestcaseDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        response = get_testcase(request, id)
        return response

    def delete(self, request, id):
        response = delete_testcase(request, id)        
        return response




class TestcasesZapier(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = get_testcases_zapier(request)
        return response




### ------ Begin Issue Views ------ ###




class Issues(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post', 'get']

    def post(self, request):
        response = create_or_update_issue(request)        
        return response
    
    def get(self, request):
        response = get_issues(request)
        return response




class IssuesSearch(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = search_issues(request)
        return response




class IssueDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        response = get_issue(request, id)
        return response

    def delete(self, request, id):
        response = delete_issue(request, id)        
        return response




class IssuesZapier(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = get_issues_zapier(request)
        return response




### ------ Begin Log Views ------ ###




class Logs(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get',]
    pagination_class = LimitOffsetPagination
    
    def get(self, request):
        response = get_logs(request)
        return response 




class LogDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get',]

    def get(self, request, id):
        response = get_log(request, id)
        return response




### ------ Begin Process Views ------ ###




class Processes(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']
    
    def get(self, request):
        response = get_processes(request)
        return response




class ProcessDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get',]

    def get(self, request, id):
        response = get_process(request, id)
        return response




### ------ Begin Search Views ------ ###




class Search(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get',]

    def get(self, request):
        response = search_resources(request)
        return response





### ------ Begin Metrics Views ------ ###




class HomeMetrics(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get',]

    def get(self, request):
        response = get_home_metrics(request)
        return response




class SiteMetrics(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get',]

    def get(self, request):
        response = get_site_metrics(request)
        return response




class CeleryMetrics(APIView):
    authentication_classes = []
    permission_classes = (AllowAny,)
    http_method_names = ['get',]
    
    def get(self, request):
        response = get_celery_metrics(request)
        return response




### ------ Begin Beta Views ------ ###




class WordPressMigrateSite(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]
    
    def post(self, request):
        response = migrate_site(request)
        return response




class SiteScreenshot(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]
    
    def post(self, request):
        response = create_site_screenshot(request)
        return response




