from ...models import (Test, Site, Scan, Log)
from ...utils.scanner import Scanner as S
from ...utils.tester import Tester as T
from ...utils.automations import automation
import boto3
from scanerr import settings



def create_site_task(site_id):
    site = Site.objects.get(id=site_id)
    S(site=site).first_scan()
    return site


def create_scan_task(
        site_id, 
        automation_id=None, 
        configs=None
    ):
    site = Site.objects.get(id=site_id)
    created_scan = Scan.objects.create(site=site)
    scan = S(scan=created_scan, configs=configs).first_scan()
    if automation_id:
        automation(automation_id, scan.id)
    return scan




def create_test_task(
        site_id, 
        automation_id=None, 
        configs=None, 
        type=['full'],
        index=None,
        pre_scan=None,
        post_scan=None,
    ):
    site = Site.objects.get(id=site_id)

    if not pre_scan and not post_scan:
        new_scan = S(site=site, configs=configs)
        post_scan = new_scan.second_scan()
        pre_scan = post_scan.paired_scan

    if not post_scan and pre_scan:
        pre_scan = Scan.objects.get(id=pre_scan)
        post_scan = S(site=site, scan=pre_scan, configs=configs).second_scan()

    # updating parired scans
    pre_scan.paired_scan = post_scan
    post_scan.paried_scan = pre_scan
    pre_scan.save()
    post_scan.save()

    # creating new test object
    created_test = Test.objects.create(
        site=site, 
        type=type,
        pre_scan=pre_scan,
        post_scan=post_scan,
    )
    
    test = T(test=created_test).run_test(index=index)
    if automation_id:
        automation(automation_id, test.id)
    return test




def delete_site_s3(site_id):
    # setup boto3 configurations
    s3 = boto3.resource('s3', 
        aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
        aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
        region_name=str(settings.AWS_S3_REGION_NAME), 
        endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
    )

    # deleting s3 objects
    bucket = s3.Bucket(settings.AWS_STORAGE_BUCKET_NAME)
    bucket.objects.filter(Prefix=str(f'static/sites/{site_id}/')).delete()

    return

