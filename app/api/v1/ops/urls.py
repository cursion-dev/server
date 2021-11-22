from django.urls import path
from . import views as views


urlpatterns = [
    path('site', views.Sites.as_view(), name='site'),
    path('site/<uuid:id>', views.SiteDetail.as_view(), name='site-detail'),
    path('site/delay', views.SiteDelay.as_view(), name='site-delay'),
    path('scan', views.Scans.as_view(), name='scan'),
    path('scan/<uuid:id>', views.ScanDetail.as_view(), name='scan-detail'),
    path('scan/delay', views.ScanDelay.as_view(), name='scan-delay'),
    path('test', views.Tests.as_view(), name='test'),
    path('test/<uuid:id>', views.TestDetail.as_view(), name='test-detail'),
    path('test/delay', views.TestDelay.as_view(), name='test-delay'),
    path('log', views.Logs.as_view(), name='log'),
    path('log/<uuid:id>', views.LogDetail.as_view(), name='log-detail'),
    path('schedule', views.Schedules.as_view(), name='schedule'),
    path('schedule/<uuid:id>', views.ScheduleDetail.as_view(), name='schedule-detail'),
    path('automation', views.Automations.as_view(), name='automation'),
    path('automation/<uuid:id>', views.AutomationDetail.as_view(), name='automation-detail'),
    path('home-stats', views.HomeStats.as_view(), name='home-stats'),
]