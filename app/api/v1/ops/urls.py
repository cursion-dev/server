from django.urls import path
from . import views as views


urlpatterns = [
    path('site', views.Sites.as_view(), name='site'),
    path('site/<uuid:id>', views.SiteDetail.as_view(), name='site-detail'),
    path('site/delay', views.SiteDelay.as_view(), name='site-delay'),
    path('sites/delete', views.SitesDelete.as_view(), name='sites-delete'),
    path('scan', views.Scans.as_view(), name='scan'),
    path('scan/<uuid:id>', views.ScanDetail.as_view(), name='scan-detail'),
    path('scan/<uuid:id>/lean', views.ScanLean.as_view(), name='scan-lean'),
    path('scan/delay', views.ScanDelay.as_view(), name='scan-delay'),
    path('scans/delete', views.ScansDelete.as_view(), name='scans-delete'),
    path('test', views.Tests.as_view(), name='test'),
    path('test/<uuid:id>', views.TestDetail.as_view(), name='test-detail'),
    path('test/<uuid:id>/lean', views.TestLean.as_view(), name='test-lean'),
    path('test/delay', views.TestDelay.as_view(), name='test-delay'),
    path('tests/delete', views.TestsDelete.as_view(), name='tests-delete'),
    path('log', views.Logs.as_view(), name='log'),
    path('log/<uuid:id>', views.LogDetail.as_view(), name='log-detail'),
    path('schedule', views.Schedules.as_view(), name='schedule'),
    path('schedule/<uuid:id>', views.ScheduleDetail.as_view(), name='schedule-detail'),
    path('automation', views.Automations.as_view(), name='automation'),
    path('automation/<uuid:id>', views.AutomationDetail.as_view(), name='automation-detail'),
    path('report', views.Reports.as_view(), name='report'),
    path('report/<uuid:id>', views.ReportDetail.as_view(), name='report-detail'),
    path('home-stats', views.HomeStats.as_view(), name='home-stats'),
    path('process', views.Processes.as_view(), name='process'),
    path('process/<uuid:id>', views.ProcessDetail.as_view(), name='process-detail'),
    path('beta/wordpress/migrate', views.WordPressMigrateSite.as_view(), name='migrate-site'),
    path('beta/wordpress/migrate/delay', views.WordPressMigrateSiteDelay.as_view(), name='migrate-site-delay'),
    path('beta/site/screenshot', views.SiteScreenshot.as_view(), name='site-screenshot'),
]