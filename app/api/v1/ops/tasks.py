from ...models import (Test, Site, Scan, Log)
from ...scan_tests.scan_site import ScanSite
from ...scan_tests.tester import Test as T
from ...scan_tests.automations import automation


def create_site_task(site_id):
    site = Site.objects.get(id=site_id)
    ScanSite(site=site).first_scan()
    return site


def create_scan_task(site_id, automation_id=None):
    site = Site.objects.get(id=site_id)
    created_scan = Scan.objects.create(site=site)
    scan = ScanSite(scan=created_scan).first_scan()
    if automation_id:
        automation(automation_id, scan.id)
    return scan


def create_test_task(site_id, automation_id=None):
    site = Site.objects.get(id=site_id)
    created_test = Test.objects.create(site=site)
    new_scan = ScanSite(site=site)
    post_scan = new_scan.second_scan()
    pre_scan = post_scan.paired_scan
    pre_scan.paired_scan = post_scan
    pre_scan.save()
    created_test.pre_scan = pre_scan
    created_test.post_scan = post_scan
    created_test.save()
    test = T(test=created_test).run_full_test()
    if automation_id:
        automation(automation_id, test.id)
    return test


