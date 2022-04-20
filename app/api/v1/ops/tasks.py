from ...models import *
from ...utils.scanner import Scanner as S
from ...utils.tester import Tester as T
from ...utils.reporter import Reporter as R
from ...utils.automations import automation
import boto3
from scanerr import settings



def create_site_task(site_id, scan_id):
    site = Site.objects.get(id=site_id)
    scan = Scan.objects.get(id=scan_id)
    S(site=site, scan=scan).first_scan()
    return site


def create_scan_task(
        scan_id=None,
        site_id=None, 
        automation_id=None, 
        configs=None,
    ):
    if scan_id is not None:
        created_scan = Scan.objects.get(id=scan_id)
    elif site_id is not None:
        site = Site.objects.get(id=site_id)
        created_scan = Scan.objects.create(
            site=site,
        )
    scan = S(scan=created_scan, configs=configs).first_scan()
    if automation_id:
        automation(automation_id, scan.id)
    return scan




def create_test_task(
        test_id=None, 
        site_id=None,
        automation_id=None, 
        configs=None, 
        type=['full'],
        index=None,
        pre_scan=None,
        post_scan=None,
    ):

    if test_id is not None:
        created_test = Test.objects.get(id=test_id)
        site = created_test.site
    elif site_id is not None:
        site = Site.objects.get(id=site_id)
        created_test = Test.objects.create(
            site=site,
            type=type,
        )

    if pre_scan is not None:
        pre_scan = Scan.objects.get(id=pre_scan)
    if post_scan is not None:
        post_scan = Scan.objects.get(id=post_scan)

    if post_scan is None and pre_scan is not None:
        post_scan = S(site=site, scan=pre_scan, configs=configs).second_scan()
        
    if pre_scan is None and post_scan is None:
        new_scan = S(site=site, configs=configs)
        post_scan = new_scan.second_scan()
        pre_scan = post_scan.paired_scan

    # updating parired scans
    pre_scan.paired_scan = post_scan
    post_scan.paried_scan = pre_scan
    pre_scan.save()
    post_scan.save()

    # updating test object
    created_test.type = type
    created_test.pre_scan = pre_scan
    created_test.post_scan = post_scan
    created_test.save()
    
    
    test = T(test=created_test).run_test(index=index)
    if automation_id:
        automation(automation_id, test.id)
    return test




def create_report_task(site_id, automation_id=None):
    site = Site.objects.get(id=site_id)
    if Report.objects.filter(site=site).exists():
       report = Report.objects.filter(site=site).order_by('-time_created')[0]
    else:
        info = {
            "text_color": '#24262d',
            "background_color": '#e1effd',
            "highlight_color": '#4283f8',
        }
        report = Report.objects.create(
            user=site.user,
            site=site,
            info=info,
        )

    
    report = R(report=report).make_test_report()
    if automation_id:
        automation(automation_id, report.id)
    return report
    





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



def delete_report_s3(report_id):
    # setup boto3 configurations
    s3 = boto3.resource('s3', 
        aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
        aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
        region_name=str(settings.AWS_S3_REGION_NAME), 
        endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
    )

    # get site
    site = Report.objects.get(id=report_id).site

    # deleting s3 objects
    bucket = s3.Bucket(settings.AWS_STORAGE_BUCKET_NAME)
    bucket.objects.filter(Prefix=str(f'static/sites/{site.id}/{report_id}.pdf')).delete()

    return
