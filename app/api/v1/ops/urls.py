from django.urls import path
from . import views as views


urlpatterns = [
    path('search', views.Search.as_view(), name='search'),
    path('site', views.Sites.as_view(), name='site'),
    path('site/<uuid:id>', views.SiteDetail.as_view(), name='site-detail'),
    path('site/<uuid:id>/crawl', views.SiteCrawl.as_view(), name='site-crawl'),
    path('site/delay', views.SiteDelay.as_view(), name='site-delay'),
    path('sites/delete', views.SitesDelete.as_view(), name='sites-delete'),
    path('page', views.Pages.as_view(), name='page'),
    path('page/<uuid:id>', views.PageDetail.as_view(), name='page-detail'),
    path('page/delay', views.PageDelay.as_view(), name='page-delay'),
    path('pages/delete', views.PagesDelete.as_view(), name='pages-delete'),
    path('scan', views.Scans.as_view(), name='scan'),
    path('scan/<uuid:id>', views.ScanDetail.as_view(), name='scan-detail'),
    path('scan/<uuid:id>/lean', views.ScanLean.as_view(), name='scan-lean'),
    path('scan/delay', views.ScanDelay.as_view(), name='scan-delay'),
    path('scans/delete', views.ScansDelete.as_view(), name='scans-delete'),
    path('scans/create', views.ScansCreate.as_view(), name='scans-create'),
    path('test', views.Tests.as_view(), name='test'),
    path('test/<uuid:id>', views.TestDetail.as_view(), name='test-detail'),
    path('test/<uuid:id>/lean', views.TestLean.as_view(), name='test-lean'),
    path('test/delay', views.TestDelay.as_view(), name='test-delay'),
    path('tests/delete', views.TestsDelete.as_view(), name='tests-delete'),
    path('tests/create', views.TestsCreate.as_view(), name='tests-create'),
    path('log', views.Logs.as_view(), name='log'),
    path('log/<uuid:id>', views.LogDetail.as_view(), name='log-detail'),
    path('schedule', views.Schedules.as_view(), name='schedule'),
    path('schedule/<uuid:id>', views.ScheduleDetail.as_view(), name='schedule-detail'),
    path('automation', views.Automations.as_view(), name='automation'),
    path('automation/<uuid:id>', views.AutomationDetail.as_view(), name='automation-detail'),
    path('report', views.Reports.as_view(), name='report'),
    path('report/<uuid:id>', views.ReportDetail.as_view(), name='report-detail'),
    path('home-stats', views.HomeStats.as_view(), name='home-stats'),
    path('site-stats', views.SiteStats.as_view(), name='site-stats'),
    path('process', views.Processes.as_view(), name='process'),
    path('process/<uuid:id>', views.ProcessDetail.as_view(), name='process-detail'),
    path('case', views.Cases.as_view(), name='case'),
    path('case/<uuid:id>', views.CaseDetail.as_view(), name='case-detail'),
    path('case/search', views.CasesSearch.as_view(), name='case-search'),
    path('testcase', views.Testcases.as_view(), name='testcase'),
    path('testcase/delay', views.TestcaseDelay.as_view(), name='testcase-delay'),
    path('testcase/<uuid:id>', views.TestcaseDetail.as_view(), name='testcase-detail'),
    path('beta/wordpress/migrate', views.WordPressMigrateSite.as_view(), name='migrate-site'),
    path('beta/wordpress/migrate/delay', views.WordPressMigrateSiteDelay.as_view(), name='migrate-site-delay'),
    path('beta/site/screenshot', views.SiteScreenshot.as_view(), name='site-screenshot'), 
    path('beta/report/export', views.ExportReport.as_view(), name='export-report'), 
    path('metrics/celery', views.CeleryMetrics.as_view(), name='celery-metrics'),
]