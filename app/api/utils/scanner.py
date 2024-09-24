from .driver import (
    driver_init, quit_driver, 
    driver_wait , get_data
)
from ..models import *
from .automater import Automater
from .tester import Tester
from .lighthouse import Lighthouse
from .yellowlab import Yellowlab
from .imager import Imager
from datetime import datetime
from cursion import settings
import os, asyncio, uuid, boto3






class Scanner():
    """ 
    Used to run and build all the 
    components of a new `Scan`

    Expects -> {
        'site'    : object,
        'page'    : object,
        'scan'    : object,
        'type'    : list
    }

    Use self.build_scan() to create a new Scan

    Returns -> `Scan` object
    """




    def __init__(
            self, 
            site: object=None, 
            page: object=None,
            scan: object=None, 
            type: list=['html', 'logs', 'vrt', 'lighthouse', 'yellowlab']
        ):

        self.site = site
        self.page = page
        self.scan = scan
        self.type = type

        # getting page and site if None
        if site == None and scan != None:
            self.site = scan.site
        if page == None and scan != None:
            self.page = scan.page
        
    


    def build_scan(self) -> object:
        """
        Method to run a scan independently of an existing `scan` obj.

        Returns -> `Scan` <obj>
        """

        # setting defaults
        html = None
        logs = None
        images = None
        lh_data = None
        yl_data = None
        
        # running scan steps with selenium driver
        driver = driver_init(
            browser=self.scan.configs.get('browser', 'chrome'),
            window_size=self.scan.configs['window_size'], 
            device=self.scan.configs['device']
        )
        driver.get(self.page.page_url)
        driver_data = get_data(
            driver=driver,
            browser=self.scan.configs.get('browser', 'chrome'),
            max_wait_time=self.scan.configs['max_wait_time']
        )
        if 'html' in self.scan.type or 'full' in self.scan.type:
            html = driver_data['html']
        if 'logs' in self.scan.type or 'full' in self.scan.type:
            logs = driver_data['logs']
        if 'vrt' in self.scan.type or 'full' in self.scan.type:
            images = Imager(scan=self.scan).scan_vrt(driver=driver)
        if 'lighthouse' in self.scan.type or 'full' in self.scan.type:
            lh_data = Lighthouse(scan=self.scan).get_data() 
        if 'yellowlab' in self.scan.type or 'full' in self.scan.type:
            yl_data = Yellowlab(scan=self.scan).get_data()

        # quiting selenium instance
        quit_driver(driver)

        # updating Scan object
        if html is not None:
            save_html(html, self.scan)
        if logs is not None:
            self.scan.logs = logs
        if images is not None:
            self.scan.images = images
        if lh_data is not None:
            self.scan.lighthouse = lh_data
        if yl_data is not None:
            self.scan.yellowlab = yl_data

        # saving scan data
        self.scan.time_completed = datetime.now()
        self.scan.save()

        # update Scan.score
        update_scan_score(self.scan)

        # updating Site and Page objects
        update_page_info(self.scan)
        update_site_info(self.scan)

        # return updated scan obj
        return self.scan




def update_scan_score(scan: object) -> object:
    """ 
    Method to calculate the average health score and update 
    for the passed scan

    Expects: {
        'scan': object
    }

    Returns -> `Scan` <obj>
    """
    
    # setting defaults
    score = None
    scores = []

    # get latest scan scores
    if scan.lighthouse['scores']['average'] is not None:
        scores.append(scan.lighthouse['scores']['average'])
    if scan.yellowlab['scores']['globalScore'] is not None:
        scores.append(scan.yellowlab['scores']['globalScore'])
    
    # calc average score
    if len(scores) > 0:
        score = sum(scores)/len(scores)

    # save to scan
    scan.score = score
    scan.save()
        
    # returning scan
    return scan




def update_site_info(scan: object) -> object:
    """ 
    Method to update associated Site with the new Scan data

    Expects: {
        'scan': object
    }

    Returns -> `Site` <obj>
    """
    
    # setting defaults
    score = None
    scores = []
    site = scan.site
    pages = Page.objects.filter(site=site)

    # get latest scan of pages
    scans = []
    for page in pages:
        if Scan.objects.filter(page=page).exists():
            scan = Scan.objects.filter(page=page).order_by('-time_completed')[0]
            if scan.score:
                scores.append(scan.score)
    
    # calc average score
    if len(scores) > 0:
        score = sum(scores)/len(scores)
        
    # saving new info to site
    site.info['latest_scan']['id'] = str(scan.id)
    site.info['latest_scan']['time_created'] = str(scan.time_created)
    site.info['latest_scan']['time_completed'] = str(scan.time_completed)
    site.info['latest_scan']['score'] = score
    site.save()

    # returning site
    return site




def update_page_info(scan: object) -> object:
    """ 
    Method to update associated Page with the new Scan data

    Expects: {
        'scan': object
    }

    Returns -> `Page` <obj>
    """

    # saving new info to page
    scan.page.info['latest_scan']['id'] = str(scan.id)
    scan.page.info['latest_scan']['time_created'] = str(scan.time_created)
    scan.page.info['latest_scan']['time_completed'] = str(scan.time_completed)
    scan.page.info['latest_scan']['score'] = scan.score
    scan.page.info['lighthouse'] = scan.lighthouse.get('scores')
    scan.page.info['yellowlab'] = scan.yellowlab.get('scores')
    scan.page.save()

    # returning page
    return scan.page




def save_html(html: str, scan: object) -> object:
    """
    Saves html page source as a '.txt' file and uploads 
    to s3. Then saves the remote uri to the `scan` obj.

    Expects: {
        html: str, 
        scan: object
    }

    Returns -> `Scan` <obj>
    """

    # setup boto3 configuration
    s3 = boto3.client(
        's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
        aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
        region_name=str(settings.AWS_S3_REGION_NAME), 
        endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
    )
    
    # save html data as text file
    file_id = uuid.uuid4()
    with open(f'{file_id}.txt', 'w') as fp:
        fp.write(html)
    
    # upload to s3 and return url
    html_file = os.path.join(settings.BASE_DIR, f'{file_id}.txt')
    remote_path = f'static/sites/{scan.site.id}/{scan.page.id}/{scan.id}/{file_id}.txt'
    root_path = settings.AWS_S3_URL_PATH
    html_url = f'{root_path}/{remote_path}'

    # upload to s3
    with open(html_file, 'rb') as data:
        s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
            remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "text/plain"}
        )
    
    # save to scan obj
    scan.html = html_url
    scan.save()

    # remove local copy
    os.remove(html_file)

    # return scan
    return scan




def check_scan_completion(scan: object, test_id: str=None, automation_id: str=None) -> object:
    """
    Method that checks if the scan has finished all 
    components. If so, method also updates Scan, Site, 
    & Page info. If test_id is present, initiates a run_test()

    Expects: {
        scan: object, 
        test_id: str,
        automation_id: str
    }

    Returns -> `Scan` <obj>
    """

    # setting defaults
    finished = True

    # checking for each scan type completion
    if 'html' in scan.type or 'full' in scan.type:
        if scan.html == None or scan.html == '':
            finished = False

    if 'logs' in scan.type or 'full' in scan.type:
        if scan.logs == None or scan.logs == '':
            finished = False

    if 'lighthouse' in scan.type or 'full' in scan.type:
        if scan.lighthouse.get('scores').get('average') == None and scan.lighthouse.get('failed') == None:
            finished = False
            
    if 'yellowlab' in scan.type or 'full' in scan.type:
        if scan.yellowlab.get('scores').get('globalScore') == None and scan.yellowlab.get('failed') == None:
            finished = False

    if 'vrt' in scan.type or 'full' in scan.type:
        if scan.images == None or scan.images == '':
            finished = False

    # deciding if done
    if finished is True:
        time_completed = datetime.now()
        scan.time_completed = time_completed
        scan.save()
        update_scan_score(scan)
        update_page_info(scan)
        update_site_info(scan)

        # start Test if test_id present
        if test_id is not None:
            print('\n---------------\nScan Complete\nStarting Test...\n---------------\n')
            test = Test.objects.get(id=test_id)
            Tester(test=test).run_test()
            if automation_id is not None and automation_id != 'None':
                print('running automation from `cursion.check_scan_completion`')
                Automater(automation_id, test.id).run_automation()

    # returning scan
    return scan




def _html_and_logs(scan_id: str, test_id: str=None, automation_id: str=None) -> object:
    """
    Method to run the 'html' and 'logs' component of the scan 
    allowing for multi-threading.

    Expects: {
        scan_id: str, 
        test_id: str, 
        automation_id: str
    }

    Returns -> `Scan` <obj>
    """

    # retrieve scan
    scan = Scan.objects.get(id=scan_id)

    try:
        # get html and logs using selenium
        # init driver & get data
        driver = driver_init(
            browser=scan.configs.get('browser', 'chrome'),
            window_size=scan.configs['window_size'], 
            device=scan.configs['device']
        )
        driver.get(scan.page.page_url)
        driver_data = get_data(
            driver=driver,
            browser=scan.configs.get('browser', 'chrome'),
            max_wait_time=int(scan.configs['max_wait_time']),
            min_wait_time=int(scan.configs['min_wait_time']),
            interval=int(scan.configs['interval'])
        )
        if 'html' in scan.type or 'full' in scan.type:
            html = driver_data['html']
            scan = Scan.objects.get(id=scan_id)
            save_html(html, scan)
        if 'logs' in scan.type or 'full' in scan.type:
            logs = driver_data['logs']
            scan = Scan.objects.get(id=scan_id)
            scan.logs = logs
            scan.save()
        quit_driver(driver)

    except Exception as e:
        print(e)
        # try to quit selenium session
        try:
            quit_driver(driver)
        except:
            pass

    # checking if scan is done
    scan = check_scan_completion(scan, test_id, automation_id)

    # return udpated scan
    return scan




def _vrt(scan_id: str, test_id: str=None, automation_id: str=None) -> object:
    """
    Method to run the visual regression (vrt) component of the scan 
    allowing for multi-threading.

    Expects: {
        scan_id: str, 
        test_id: str, 
        automation_id: str
    }

    Returns -> `Scan` <obj>
    """
    
    # retrieve scan
    scan = Scan.objects.get(id=scan_id)
    
    try:
        # run Imager using selenium
        driver = driver_init(
            window_size=scan.configs.get('window_size', '1920,1080'), 
            device=scan.configs.get('device', 'desktop'),
            browser=scan.configs.get('browser', 'chrome')
        )
        images = Imager(scan=scan).scan_vrt(driver=driver)
        quit_driver(driver)
        
        # updating Scan object
        scan = Scan.objects.get(id=scan_id)
        scan.images = images
        scan.save()
    except Exception as e:
        print(e)

    # checking if scan is done
    scan = check_scan_completion(scan, test_id, automation_id)

    # returning updated scan
    return scan




def _lighthouse(scan_id: str, test_id: str=None, automation_id: str=None) -> object:
    """
    Method to run the lighthouse component of the scan 
    allowing for multi-threading.

    Expects: {
        scan_id: str, 
        test_id: str, 
        automation_id: str
    }

    Returns -> `Scan` <obj>
    """
    
    # retrieve scan
    scan = Scan.objects.get(id=scan_id)

    try:
        # running lighthouse
        lh_data = Lighthouse(scan=scan).get_data() 
        print(f'LIGHTHOUSE failure_status -> {lh_data.get('failed')}')
        
        # updating Scan object
        scan = Scan.objects.get(id=scan_id)
        scan.lighthouse = lh_data
        scan.save()
    except Exception as e:
        scan.yellowlab['failed'] = True
        scan.save()
        print(e)

    # checking if scan is done
    scan = check_scan_completion(scan, test_id, automation_id)

    # returning updated scan
    return scan




def _yellowlab(scan_id: str, test_id: str=None, automation_id: str=None) -> object:
    """
    Method to run the yellowlab component of the scan 
    allowing for multi-threading.

    Expects: {
        scan_id: str, 
        test_id: str, 
        automation_id: str
    }

    Returns -> `Scan` <obj>
    """ 
    
    # retrieve scan
    scan = Scan.objects.get(id=scan_id)
    
    try:
        # running yellowlab
        yl_data = Yellowlab(scan=scan).get_data()
        print(f'YELLOWLAB failure_status -> {yl_data.get('failed')}')
        
        # updating Scan object
        scan = Scan.objects.get(id=scan_id)
        scan.yellowlab = yl_data
        scan.save()
    except Exception as e:
        scan.yellowlab['failed'] = True
        scan.save()
        print(e)

    # checking if scan is done
    scan = check_scan_completion(scan, test_id, automation_id)

    # returning updated scan
    return scan




