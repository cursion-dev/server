from django.contrib import admin
from .models import *
from datetime import datetime
from .v1.ops.services import (
    create_scan, create_test, 
    delete_site, delete_page, 
    delete_scan, delete_test,
    delete_case, delete_caserun,
    crawl_site
)
from .tasks import (
    reset_account_usage, 
    update_scan_score
)






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
    list_display = ('email', 'account', 'time_created', 'type', 'status')
    search_fields = ('user__username', 'account__name')




@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'brand', 'last_four')
    search_fields = ('last_four',)





@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('site_url', 'account', 'time_created')
    search_fields = ('site_url', 'account')
    actions = ['scan_sites', 'test_sites', 'delete_sites', 'crawl_sites']

    def crawl_sites(self, request, queryset):
        for site in queryset:
            crawl_site(
                id=site.id,
                user=site.account.user
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
                user=site.account.user
            )




@admin.register(Page)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('page_url', 'account', 'time_created')
    search_fields = ('page_url', 'account')
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
                user=page.user
            )




@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('id', 'page', 'time_created', 'time_completed', 'type')
    search_fields = ('page__page_url',)
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
    search_fields = ('page__page_url',)
    actions = ['delete_scans', 'mark_as_completed', 'add_scan_score' ]

    def delete_scans(self, request, queryset):
        for scan in queryset:
            delete_scan(
                id=scan.id,
                account=scan.page.account
            )
    
    def add_scan_score(self, request, queryset):
        for scan in queryset:
            update_scan_score.delay(
                scan_id=scan.id
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
    list_display = ('__str__', 'time_last_run', 'status', 'user', 'time_created')




@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'time_created', 'schedule', 'user')




@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'time_created',  'time_completed', 'progress', 'success')




@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'site', 'time_created',)
    search_fields = ('title', 'site__site_url')
    actions = ['delete_cases',]

    def delete_cases(self, request, queryset):
        for case in queryset:
            delete_case(
                id=case.id,
                user=case.user
            )




@admin.register(CaseRun)
class CaseRunAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'time_created', 'time_completed',)
    search_fields = ('title', 'site__site_url')

    actions = ['delete_caseruns',]

    def delete_caseruns(self, request, queryset):
        for caserun in queryset:
            delete_caserun(
                id=caserun.id,
                user=caserun.user
            )




@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ('title', 'account', 'time_created', 'status',)
    search_fields = ('title', 'affected')




@admin.register(Flow)
class FlowAdmin(admin.ModelAdmin):
    list_display = ('title', 'account', 'time_created',)
    search_fields = ('title',)




@admin.register(FlowRun)
class FlowRunAdmin(admin.ModelAdmin):
    list_display = ('title', 'account', 'site', 'time_created', 'time_completed', 'status')
    search_fields = ('title', 'site__site_url',)




@admin.register(Secret)
class SecretAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'account', 'time_created',)




@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'discount', 'time_created', 'status',)
    search_fields = ('code',)




@admin.register(Mask)
class MaskAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'mask_id', 'active', 'time_created',)
    search_fields = ('mask_id',)
    actions = ['mark_as_inactive', 'mark_as_active',]
    
    def mark_as_inactive(self, request, queryset):
        queryset.update(active=False)
    
    def mark_as_active(self, request, queryset):
        queryset.update(active=True)



        