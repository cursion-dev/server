from django.contrib import admin
from .models import *


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('site_url', 'user', 'time_created')
    search_fields = ('site_url',)

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'time_created', 'type')
    search_fields = ('site',)

@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'time_created')
    search_fields = ('site',)

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'time_created', 'type')
    search_fields = ('__str__',)

@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'brand', 'last_four')
    search_fields = ('last_four',)

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'time_created', 'user')

@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'time_created', 'status', 'user')

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'time_created', 'status', 'user')

@admin.register(Automation)
class AutomationAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'time_created', 'schedule', 'user')