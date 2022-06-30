from ...models import *
from ...utils.scanner import Scanner as S
from ...utils.tester import Tester as T
from ...utils.reporter import Reporter as R
from ...utils.wordpress import Wordpress as W
from ...utils.wordpress_p import Wordpress as W_P
from ...utils.automations import automation
from ...utils.caser import Caser
import boto3, asyncio
from scanerr import settings



def create_site_task(site_id, scan_id, configs):
    site = Site.objects.get(id=site_id)
    scan = Scan.objects.get(id=scan_id)
    S(site=site, scan=scan, configs=configs).first_scan()
    return site


def create_scan_task(
        scan_id=None,
        site_id=None, 
        type=['full'],
        automation_id=None, 
        configs=None,
        tags=None,
    ):
    if scan_id is not None:
        created_scan = Scan.objects.get(id=scan_id)
    elif site_id is not None:
        site = Site.objects.get(id=site_id)
        created_scan = Scan.objects.create(
            site=site,
            type=type,
            configs=configs,
            tags=tags, 
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
        tags=None,
    ):

    if test_id is not None:
        created_test = Test.objects.get(id=test_id)
        site = created_test.site
    elif site_id is not None:
        site = Site.objects.get(id=site_id)
        created_test = Test.objects.create(
            site=site,
            type=type,
            tags=tags,
        )

    if pre_scan is not None:
        pre_scan = Scan.objects.get(id=pre_scan)
    if post_scan is not None:
        post_scan = Scan.objects.get(id=post_scan)

    if post_scan is None and pre_scan is not None:
        post_scan = S(site=site, scan=pre_scan, configs=configs, type=type).second_scan()
        
    if pre_scan is None and post_scan is None:
        new_scan = S(site=site, configs=configs, type=type)
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
    try:
        bucket = s3.Bucket(settings.AWS_STORAGE_BUCKET_NAME)
        bucket.objects.filter(Prefix=str(f'static/sites/{site_id}/')).delete()
    except:
        pass

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




def create_testcase_task(
        testcase_id=None, 
        site_id=None, 
        case_id=None, 
        updates=None,
        configs=None,
        automation_id=None
    ):

    if testcase_id != None:
        testcase = Testcase.objects.get(id=testcase_id)
    
    else:
        case = Case.objects.get(id=case_id)
        site = Site.objects.get(id=site_id)
        steps = case.steps
        for step in steps:
            if step['action']['type'] != None:
                step['action']['time_created'] = None
                step['action']['time_completed'] = None
                step['action']['exception'] = None
                step['action']['passed'] = None

            if step['assertion']['type'] != None:
                step['assertion']['time_created'] = None
                step['assertion']['time_completed'] = None
                step['assertion']['exception'] = None
                step['assertion']['passed'] = None

        if updates != None:
            for update in updates:
                steps[int(update['index'])]['action']['value'] = update['value']

        if configs is None:
            configs = {
                'window_size': '1920,1080',
                'device': 'desktop',
                'interval': 5,
                'min_wait_time': 10,
                'max_wait_time': 30,
            }
            
        testcase = Testcase.objects.create(
            case = case,
            case_name = case.name,
            site = site,
            user = site.user,
            configs = configs,
            steps = steps
        )

    
    # running testcase
    testresult = asyncio.run(
        Caser(testcase=testcase).run()
    )

    if automation_id:
        automation(automation_id, testcase.id)

    return




def migrate_site_task(
        login_url, 
        admin_url,
        username,
        password,
        email_address,
        destination_url,
        sftp_address,
        dbname,
        sftp_username,
        sftp_password, 
        plugin_name,
        wait_time,
        process_id,
        driver, 
        
    ):

    if driver == 'selenium':
        # init wordpress
        wp = W(
            login_url=login_url, 
            admin_url=admin_url,
            username=username,
            password=password,
            email_address=email_address,
            destination_url=destination_url,
            sftp_address=sftp_address,
            dbname=dbname,
            sftp_username=sftp_username,
            sftp_password=sftp_password, 
            wait_time=wait_time,
            process_id=process_id,

        )

        # login
        wp_status = wp.login()
        # adjust lang
        wp_status = wp.begin_lang_check()
        # install plugin
        wp_status = wp.install_plugin(plugin_name=plugin_name)
        # launch migration
        wp_status = wp.launch_migration()
        # run migration
        wp_status = wp.run_migration()
        # re adjust lang
        # wp_status = wp.end_lang_check()
    
    else:
        # init wordpress for puppeteer
        wp_status = asyncio.run(
            W_P(
                login_url=login_url, 
                admin_url=admin_url,
                username=username,
                password=password,
                email_address=email_address,
                destination_url=destination_url,
                sftp_address=sftp_address,
                dbname=dbname,
                sftp_username=sftp_username,
                sftp_password=sftp_password, 
                wait_time=wait_time,
                process_id=process_id,
            ).run_full(plugin_name=plugin_name)
        )

    return





    