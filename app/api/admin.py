from django.contrib import admin
from .models import *
from datetime import datetime


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('site_url', 'user', 'time_created')
    search_fields = ('site_url',)


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('id', 'site', 'time_created', 'time_completed', 'type')
    search_fields = ('site',)


@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ('id', 'site', 'time_created', 'time_completed')
    search_fields = ('site',)
    actions = ['mark_as_completed',]

    def mark_as_completed(self, request, queryset):
        queryset.update(time_completed=datetime.now())


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'time_created', 'type')
    search_fields = ('__str__',)


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'account', 'time_created', 'type', 'status')
    search_fields = ('user__username', 'account__name')
    # list_display = ('__str__', 'time_created')
    # search_fields = ('__str__',)


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


@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'time_created',  'time_completed', 'progress', 'successful')


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user', 'time_created',)


@admin.register(Testcase)
class TestcaseAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user', 'time_created', 'time_completed',)


@admin.register(Mask)
class MaskAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'mask_id', 'active', 'time_created',)
    search_fields = ('mask_id',)
    actions = ['mark_as_inactive', 'mark_as_active',]
    
    def mark_as_inactive(self, request, queryset):
        queryset.update(active=False)
    
    def mark_as_active(self, request, queryset):
        queryset.update(active=True)