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






### ------ Begin Task Views ------ ###




class TasksRetry(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get']

    def get(self, request):
        response = retry_failed_tasks(request)
        return response




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




class ScheduleRun(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post']

    def post(self, request):
        response = run_schedule(request)        
        return response




class SchedulesUpdate(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = update_many_schedules(request)
        return response




class SchedulesDelete(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = delete_many_schedules(request)
        return response




### ------ Begin Alert Views ------ ###




class Alerts(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'post']
    pagination_class = LimitOffsetPagination

    def post(self, request):
        response = create_or_update_alert(request)
        return response
    
    def get(self, request):
        response = get_alerts(request)
        return response




class AlertDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        response = get_alert(request, id)
        return response

    def delete(self, request, id):
        response = delete_alert(request, id)        
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




class CasePreRun(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post']

    def post(self, request):
        response = case_pre_run(request)  
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




class CasesDelete(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = delete_many_cases(request)
        return response




class CasesZapier(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = get_cases_zapier(request)
        return response




### ------ Begin CaseRun Views ------ ###




class CaseRuns(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post', 'get']

    def post(self, request):
        response = create_caserun(request)        
        return response
    
    def get(self, request):
        response = get_caseruns(request)
        return response




class CaseRunDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        response = get_caserun(request, id)
        return response

    def delete(self, request, id):
        response = delete_caserun(request, id)        
        return response




class CaseRunsZapier(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = get_caseruns_zapier(request)
        return response




### ------ Begin Flow Views ------ ###




class Flows(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post', 'get']

    def post(self, request):
        response = create_or_update_flow(request)        
        return response
    
    def get(self, request):
        response = get_flows(request)
        return response




class FlowsSearch(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = search_flows(request)
        return response




class FlowDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        response = get_flow(request, id)
        return response

    def delete(self, request, id):
        response = delete_flow(request, id)        
        return response




class CopyFlows(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post']

    def post(self, request):
        response = copy_flow(request)  
        return response




class FlowsDelete(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = delete_many_flows(request)
        return response




class FlowsZapier(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = get_flows_zapier(request)
        return response




### ------ Begin FlowRun Views ------ ###




class FlowRuns(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post', 'get']

    def post(self, request):
        response = create_flowrun(request)        
        return response
    
    def get(self, request):
        response = get_flowruns(request)
        return response




class FlowRunDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        response = get_flowrun(request, id)
        return response

    def delete(self, request, id):
        response = delete_flowrun(request, id)        
        return response




class FlowRunsZapier(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = get_flowruns_zapier(request)
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




class IssueGenerate(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = generate_issue(request)        
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




class IssuesUpdate(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = update_many_issues(request)
        return response




class IssuesDelete(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        response = delete_many_issues(request)
        return response




class IssuesZapier(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = get_issues_zapier(request)
        return response




### ------ Begin Secret Views ------ ###




class Secrets(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post', 'get']

    def post(self, request):
        response = create_or_update_secret(request)        
        return response
    
    def get(self, request):
        response = get_secrets(request)
        return response




class SecretDetail(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        response = get_secret(request, id)
        return response

    def delete(self, request, id):
        response = delete_secret(request, id)        
        return response





class SecretsAll(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get']

    def get(self, request):
        response = get_secrets_all(request)
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
    http_method_names = ['get', 'delete']

    def get(self, request, id):
        response = get_process(request, id)
        return response
    
    def delete(self, request, id):
        response = delete_process(request, id)
        return response




### ------ Begin Search Views ------ ###




class Search(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get',]

    def get(self, request):
        response = search_resources(request)
        return response




class Device(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get',]

    def get(self, request):
        response = get_devices(request)
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




