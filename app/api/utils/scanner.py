from .driver_s import driver_init as driver_s_init, quit_driver
from .driver_s import driver_wait, get_data as get_s_driver_data
from .driver_p import get_data
from ..models import *
from .automater import Automater
from .tester import Tester
from .lighthouse import Lighthouse
from .yellowlab import Yellowlab
from .imager import Imager
from datetime import datetime
from scanerr import settings
import os, asyncio, uuid, boto3






class Scanner():
    """ 
    Used to run and build all the 
    components of a new `Scan`

    Expects -> {
        'site'    : object,
        'page'    : object,
        'scan'    : object,
        'configs' : dict,
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
            configs: dict=settings.CONFIGS,
            type: list=['html', 'logs', 'vrt', 'lighthouse', 'yellowlab']
        ):

        self.site = site
        self.page = page
        self.scan = scan
        self.configs = configs
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

        # creating Scan obj if None was passed
        if self.scan is None:
            self.scan = Scan.objects.create(site=self.site, page=self.page, type=self.type)
        
        # running scan steps with selenium driver
        if self.configs['driver'] == 'selenium':
            driver = driver_s_init(
                window_size=self.configs['window_size'], 
                device=self.configs['device']
            )
            driver.get(self.page.page_url)
            s_driver_data = get_s_driver_data(
                driver=self.driver, 
                max_wait_time=self.configs['max_wait_time']
            )
            if 'html' in self.scan.type or 'full' in self.scan.type:
                html = s_driver_data['html']
            if 'logs' in self.scan.type or 'full' in self.scan.type:
                logs = s_driver_data['logs']
            if 'vrt' in self.scan.type or 'full' in self.scan.type:
                images = Imager(scan=self.scan, configs=self.configs).scan_s(driver=driver)
            quit_driver(driver)
        
        # running scan steps with puppeteer driver
        if self.configs['driver'] == 'puppeteer':
            p_driver_data = asyncio.run(
                get_data(
                    url=self.page.page_url, 
                    configs=self.configs
                )
            )
            if 'html' in self.scan.type or 'full' in self.scan.type:
                html = p_driver_data['html']
            if 'logs' in self.scan.type or 'full' in self.scan.type:
                logs = p_driver_data['logs']
            if 'vrt' in self.scan.type or 'full' in self.scan.type:
                images = asyncio.run(Imager(scan=self.scan, configs=self.configs).scan_p())
        
        # running LH & YL if requested
        if 'lighthouse' in self.scan.type or 'full' in self.scan.type:
            lh_data = Lighthouse(scan=self.scan, configs=self.configs).get_data() 
        if 'yellowlab' in self.scan.type or 'full' in self.scan.type:
            yl_data = Yellowlab(scan=self.scan, configs=self.configs).get_data()

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
        self.scan.configs = self.configs
        self.scan.time_completed = datetime.now()
        self.scan.save()

        # updating Site and Page objects
        update_page_info(self.scan)
        update_site_info(self.scan)

        # return updated scan obj
        return self.scan




def update_site_info(scan: object) -> object:
    """ 
    Method to update associated Site with the new Scan data

    Expects: {
        'scan': object
    }

    Returns -> `Site` <obj>
    """
    
    # setting defaults
    health = 'No Data'
    badge = 'neutral'
    score = 0
    site = scan.site
    pages = Page.objects.filter(site=site)

    # get latest scan of pages
    scans = []
    for page in pages:
        if Scan.objects.filter(page=page).exists():
            _scan = Scan.objects.filter(page=page).order_by('-time_completed')[0]
            if _scan.lighthouse['scores']['average'] is not None:
                scans.append(_scan.lighthouse['scores']['average'])
            if _scan.yellowlab['scores']['globalScore'] is not None:
                scans.append(_scan.yellowlab['scores']['globalScore'])
    
    # calc average score
    if len(scans) > 0:
        score = sum(scans)/len(scans)  
    if score != 0:
        if score >= 75:
            health = 'Good'
            badge = 'success'
        elif 75 > score >= 60:
            health = 'Okay'
            badge = 'warning'
        elif 60 > score:
            health = 'Poor'
            badge = 'danger'
    else:
        if site.info['status']['score'] is not None:
            score = float(site.info['status']['score'])
            health = site.info['status']['health']
            badge = site.info['status']['badge']
        else:
            score = None

    # saving new info to site
    site.info['latest_scan']['id'] = str(scan.id)
    site.info['latest_scan']['time_created'] = str(scan.time_created)
    site.info['latest_scan']['time_completed'] = str(scan.time_completed)
    site.info['status']['health'] = str(health)
    site.info['status']['badge'] = str(badge)
    site.info['status']['score'] = score
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
    
    # setting defaults
    health = 'No Data'
    badge = 'neutral'
    d = 0
    score = 0
    page = scan.page

    # selecting LH & YL scores if present
    if scan.lighthouse['scores']['average'] is not None:
        score += float(scan.lighthouse['scores']['average'])
        d += 1
    if scan.yellowlab['scores']['globalScore'] is not None:
        score += float(scan.yellowlab['scores']['globalScore'])
        d += 1
    
    # calc average health score
    if score != 0:
        score = score / d
        if score >= 75:
            health = 'Good'
            badge = 'success'
        elif 75 > score >= 60:
            health = 'Okay'
            badge = 'warning'
        elif 60 > score:
            health = 'Poor'
            badge = 'danger'
    else:
        if scan.page.info['status']['score'] is not None:
            score = float(page.info['status']['score'])
            health = page.info['status']['health']
            badge = page.info['status']['badge']
        else:
            score = None

    # saving new info to page
    page.info['latest_scan']['id'] = str(scan.id)
    page.info['latest_scan']['time_created'] = str(scan.time_created)
    page.info['latest_scan']['time_completed'] = str(scan.time_completed)
    page.info['lighthouse'] = scan.lighthouse.get('scores')
    page.info['yellowlab'] = scan.yellowlab.get('scores')
    page.info['status']['health'] = str(health)
    page.info['status']['badge'] = str(badge)
    page.info['status']['score'] = score
    page.save()

    # returning page
    return page




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
        update_page_info(scan)
        update_site_info(scan)

        # start Test if test_id present
        if test_id is not None:
            print('\n-\n---------------\nScan Complete\nStarting Test...\n---------------\n')
            test = Test.objects.get(id=test_id)
            Tester(test=test).run_test()
            if automation_id:
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
        # get html and logs if driver is selenium
        if scan.configs['driver'] == 'selenium':
            # init driver & get data
            driver = driver_s_init(
                window_size=scan.configs['window_size'], 
                device=scan.configs['device']
            )
            driver.get(scan.page.page_url)
            s_driver_data = get_s_driver_data(
                driver=driver, 
                max_wait_time=int(scan.configs['max_wait_time'])
            )
            if 'html' in scan.type or 'full' in scan.type:
                html = s_driver_data['html']
                scan = Scan.objects.get(id=scan_id)
                save_html(html, scan)
            if 'logs' in scan.type or 'full' in scan.type:
                logs = s_driver_data['logs']
                scan = Scan.objects.get(id=scan_id)
                scan.logs = logs
                scan.save()
            quit_driver(driver)

        # get html and logs if driver is puppeteer
        if scan.configs['driver'] == 'puppeteer':
            # init driver & get data
            p_driver_data = asyncio.run(
                get_data(
                    url=scan.page.page_url, 
                    configs=scan.configs
                )
            )
            if 'html' in scan.type or 'full' in scan.type:
                html = p_driver_data['html']
                scan = Scan.objects.get(id=scan_id)
                save_html(html, scan)
            if 'logs' in scan.type or 'full' in scan.type:
                logs = p_driver_data['logs']
                scan = Scan.objects.get(id=scan_id)
                scan.logs = logs
                scan.save()
    except Exception as e:
        print(e)

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
        if scan.configs['driver'] == 'selenium':
            driver = driver_s_init(window_size=scan.configs['window_size'], device=scan.configs['device'])
            images = Imager(scan=scan, configs=scan.configs).scan_s(driver=driver)
            quit_driver(driver)

        # run Imager using puppeteer
        if scan.configs['driver'] == 'puppeteer':
            images = asyncio.run(Imager(scan=scan, configs=scan.configs).scan_p())
        
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
        lh_data = Lighthouse(scan=scan, configs=scan.configs).get_data() 
        
        # updating Scan object
        scan = Scan.objects.get(id=scan_id)
        scan.lighthouse = lh_data
        scan.save()
    except Exception as e:
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
        yl_data = Yellowlab(scan=scan, configs=scan.configs).get_data()
        
        # updating Scan object
        scan = Scan.objects.get(id=scan_id)
        scan.yellowlab = yl_data
        scan.save()
    except Exception as e:
        print(e)

    # checking if scan is done
    scan = check_scan_completion(scan, test_id, automation_id)

    # returning updated scan
    return scan




