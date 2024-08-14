from django.contrib import admin
from .models import *
from datetime import datetime
from .v1.ops.services import (
    create_scan, create_test, 
    delete_site, delete_page, 
    delete_scan, delete_test,
    delete_case, delete_testcase,
    crawl_site
)
from .tasks import reset_account_usage






@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'time_created', 'type')
    search_fields = ('__str__',)
    actions = ['reset_usage',]

    def reset_usage(self, request, queryset):
        for account in queryset:
            reset_account_usage.delay(
                account_id=account.id
            )




@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'account', 'time_created', 'type', 'status')
    search_fields = ('user__username', 'account__name')




@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'brand', 'last_four')
    search_fields = ('last_four',)





@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('site_url', 'account', 'time_created')
    search_fields = ('site_url',)
    actions = ['scan_sites', 'test_sites', 'delete_sites', 'crawl_sites']

    def crawl_sites(self, request, queryset):
        for site in queryset:
            crawl_site(
                id=site.id,
                account=site.account
            )

    def scan_sites(self, request, queryset):
        for site in queryset:
            create_scan(
                site_id=site.id,
                user_id=site.account.user.id
            )
    
    def test_sites(self, request, queryset):
        for site in queryset:
            create_test(
                site_id=site.id,
                user_id=site.account.user.id
            )
    
    def delete_sites(self, request, queryset):
        for site in queryset:
            delete_site(
                id=site.id,
                account=site.account
            )




@admin.register(Page)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('page_url', 'account', 'time_created')
    search_fields = ('page_url',)
    actions = ['scan_pages', 'test_pages', 'delete_pages',]

    def scan_pages(self, request, queryset):
        for page in queryset:
            create_scan(
                page_id=page.id,
                user_id=page.account.user.id
            )
    
    def test_pages(self, request, queryset):
        for page in queryset:
            create_test(
                page_id=page.id,
                user_id=page.account.user.id
            )
    
    def delete_pages(self, request, queryset):
        for page in queryset:
            delete_page(
                id=page.id,
                account=page.account
            )




@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('id', 'page', 'time_created', 'time_completed', 'type')
    search_fields = ('page',)
    actions = ['delete_tests',]

    def delete_tests(self, request, queryset):
        for test in queryset:
            delete_test(
                id=test.id,
                account=test.page.account
            )



@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ('id', 'page', 'time_created', 'time_completed')
    search_fields = ('page',)
    actions = ['delete_scans', 'mark_as_completed',]

    def delete_scans(self, request, queryset):
        for scan in queryset:
            delete_scan(
                id=scan.id,
                account=scan.page.account
            )

    def mark_as_completed(self, request, queryset):
        queryset.update(time_completed=datetime.now())




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
    list_display = ('__str__', 'time_created',  'time_completed', 'progress', 'success')




@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user', 'time_created',)
    actions = ['delete_cases',]

    def delete_cases(self, request, queryset):
        for case in queryset:
            delete_case(
                id=case.id,
                account=case.account
            )




@admin.register(Testcase)
class TestcaseAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user', 'time_created', 'time_completed',)
    actions = ['delete_testcases',]

    def delete_testcases(self, request, queryset):
        for testcase in queryset:
            delete_testcase(
                id=testcase.id,
                account=testcase.account
            )




@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'account', 'time_created', 'read',)




@admin.register(Mask)
class MaskAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'mask_id', 'active', 'time_created',)
    search_fields = ('mask_id',)
    actions = ['mark_as_inactive', 'mark_as_active',]
    
    def mark_as_inactive(self, request, queryset):
        queryset.update(active=False)
    
    def mark_as_active(self, request, queryset):
        queryset.update(active=True)



        