from .driver_s import driver_init as driver_s_init, quit_driver
from .driver_s import driver_wait
from .driver_p import get_data
from ..models import Site, Scan, Test
from django.forms.models import model_to_dict
from django.core.serializers.json import DjangoJSONEncoder
from .lighthouse import Lighthouse
from .yellowlab import Yellowlab
from .image import Image
from datetime import datetime
import time, os, sys, json, asyncio



class Scanner():

    def __init__(
            self, 
            site=None, 
            scan=None, 
            configs=None,
            type=['html', 'logs', 'vrt', 'lighthouse', 'yellowlab']
        ):

        if site == None and scan != None:
            site = scan.site
        
        if configs is None:
            configs = {
                'window_size': '1920,1080',
                'driver': 'selenium',
                'device': 'desktop',
                'mask_ids': None,
                'interval': 5,
                'min_wait_time': 10,
                'max_wait_time': 60,
                'timeout': 300,
                'disable_animations': False
            }
        
        self.site = site
        
        if configs['driver'] == 'selenium':
            self.driver = driver_s_init(window_size=configs['window_size'], device=configs['device'])
        
        if scan is not None:
            self.scan = scan
        else:
            self.scan = None
        
        self.configs = configs
        self.type = type



    def first_scan(self):
        """
            Method to run a scan independently of an existing `scan` obj.

            returns -> `Scan` <obj>
        """

        html = None
        logs = None
        images = None
        lh_data = None
        yl_data = None

        if self.scan is None:
            self.scan = Scan.objects.create(site=self.site, type=self.type)
        
        if self.configs['driver'] == 'selenium':
            self.driver.get(self.site.site_url)
            if 'html' in self.scan.type or 'full' in self.scan.type:
                html = self.driver.page_source
            if 'logs' in self.scan.type or 'full' in self.scan.type:
                logs = self.driver.get_log('browser')
            if 'vrt' in self.scan.type or 'full' in self.scan.type:
                images = Image().scan(site=self.site, driver=self.driver, configs=self.configs)
            quit_driver(self.driver)
        else:
            driver_data = asyncio.run(
                get_data(
                    url=self.site.site_url, 
                    configs=self.configs
                )
            )
            if 'html' in self.scan.type or 'full' in self.scan.type:
                html = driver_data['html']
            if 'logs' in self.scan.type or 'full' in self.scan.type:
                logs = driver_data['logs']
            if 'vrt' in self.scan.type or 'full' in self.scan.type:
                images = asyncio.run(Image().scan_p(site=self.site, configs=self.configs))
        
        if 'lighthouse' in self.scan.type or 'full' in self.scan.type:
            lh_data = Lighthouse(site=self.site, configs=self.configs).get_data() 
        if 'yellowlab' in self.scan.type or 'full' in self.scan.type:
            yl_data = Yellowlab(site=self.site, configs=self.configs).get_data()

        if html is not None:
            self.scan.html = html
        if logs is not None:
            self.scan.logs = logs
        if images is not None:
            self.scan.images = images
        if lh_data is not None:
            self.scan.lighthouse = lh_data
        if yl_data is not None:
            self.scan.yellowlab = yl_data

        self.scan.configs = self.configs
        self.scan.time_completed = datetime.now()
        self.scan.save()
        first_scan = self.scan

        update_site_info(first_scan)

        return first_scan





    def second_scan(self):
        """
            Method to run a scan and attach existing `Scan` obj to it.

            returns -> `Scan` <obj>
        """
        if not self.scan:
            first_scan = Scan.objects.filter(
                site=self.site, 
                time_completed__isnull=False
            ).order_by('-time_created').first()
        
        else:
            first_scan = self.scan

        # create second scan obj 
        second_scan = Scan.objects.create(site=self.site, type=self.type)

        html = None
        logs = None
        images = None
        lh_data = None
        yl_data = None
        
        if self.configs['driver'] == 'selenium':
            self.driver.get(self.site.site_url)
            if 'html' in second_scan.type or 'full' in second_scan.type:
                html = self.driver.page_source
            if 'logs' in second_scan.type or 'full' in second_scan.type:
                logs = self.driver.get_log('browser')
            if 'vrt' in second_scan.type or 'full' in second_scan.type:
                images = Image().scan(site=self.site, driver=self.driver, configs=self.configs)
            quit_driver(self.driver)
        else:
            driver_data = asyncio.run(
                get_data(
                    url=self.site.site_url, 
                    configs=self.configs
                )
            )
            if 'html' in second_scan.type or 'full' in second_scan.type:
                html = driver_data['html']
            if 'logs' in second_scan.type or 'full' in second_scan.type:
                logs = driver_data['logs']
            if 'vrt' in second_scan.type or 'full' in second_scan.type:
                images = asyncio.run(Image().scan_p(site=self.site, configs=self.configs))
        
        if 'lighthouse' in second_scan.type or 'full' in second_scan.type:
            lh_data = Lighthouse(site=self.site, configs=self.configs).get_data() 
        if 'yellowlab' in second_scan.type or 'full' in second_scan.type:
            yl_data = Yellowlab(site=self.site, configs=self.configs).get_data()

        if html is not None:
            second_scan.html = html
        if logs is not None:
            second_scan.logs = logs
        if images is not None:
            second_scan.images = images
        if lh_data is not None:
            second_scan.lighthouse = lh_data
        if yl_data is not None:
            second_scan.yellowlab = yl_data

        second_scan.configs = self.configs

        second_scan.time_completed = datetime.now()
        second_scan.paired_scan = first_scan
        second_scan.save()
        
        first_scan.paried_scan = second_scan
        first_scan.save()

        update_site_info(second_scan)
        
        return second_scan







def update_site_info(scan):
    """ 
        Method to update associated Site with the new Scan data

        returns -> `Site` <obj>
    """
        
    health = 'No Data'
    badge = 'neutral'
    d = 0
    score = 0
    site = scan.site

    if scan.lighthouse['scores']['average'] is not None:
        score += float(scan.lighthouse['scores']['average'])
        d += 1
    if scan.yellowlab['scores']['globalScore'] is not None:
        score += float(scan.yellowlab['scores']['globalScore'])
        d += 1
    
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
        if scan.site.info['status']['score'] is not None:
            score = float(site.info['status']['score'])
            health = site.info['status']['health']
            badge = site.info['status']['badge']
        else:
            score = None

    site.info['latest_scan']['id'] = str(scan.id)
    site.info['latest_scan']['time_created'] = str(scan.time_created)
    site.info['latest_scan']['time_completed'] = str(scan.time_completed)
    site.info['lighthouse'] = scan.lighthouse.get('scores')
    site.info['yellowlab'] = scan.yellowlab.get('scores')
    site.info['status']['health'] = str(health)
    site.info['status']['badge'] = str(badge)
    site.info['status']['score'] = score

    site.save()

    return site










def check_scan_completion(scan):
    """
        Method that checks if the scan has finished all 
        components. If so, method also updates scan and site 
        info.

        returns -> `Scan` <obj>
    """

    finished = True

    if 'html' or 'full' in scan.type:
        if scan.html == None or scan.html == '':
            finished = False

    if 'logs' or 'full' in scan.type:
        if scan.logs == None or scan.logs == '':
            finished = False

    if 'lighthouse' or 'full' in scan.type:
        if scan.lighthouse.get('scores').get('average') == None and scan.lighthouse.get('failed') == None:
            finished = False
            
    if 'yellowlab' or 'full' in scan.type:
        if scan.yellowlab.get('scores').get('globalScore') == None and scan.yellowlab.get('failed') == None:
            finished = False

    if 'vrt' or 'full' in scan.type:
        if scan.images == None or scan.images == '':
            finished = False

    # deciding if done
    if finished is True:
        time_completed = datetime.now()
        update_site_info(scan)
        scan.time_completed = time_completed
        scan.save()

    return scan






def _html_and_logs(scan_id):
    """
        Method to run the 'html' and 'logs' component of the scan 
        allowing for multi-threading.

        returns -> `Scan` <obj>
    """
    scan = Scan.objects.get(id=scan_id)

    if scan.configs['driver'] == 'selenium':

        driver = driver_s_init(
            window_size=scan.configs['window_size'], 
            device=scan.configs['device']
        )
        driver.get(scan.site.site_url)
        if 'html' in scan.type or 'full' in scan.type:
            html = driver.page_source
            scan = Scan.objects.get(id=scan_id)
            scan.html = html
            scan.save()
        if 'logs' in scan.type or 'full' in scan.type:
            logs = driver.get_log('browser')
            scan = Scan.objects.get(id=scan_id)
            scan.logs = logs
            scan.save()
        quit_driver(driver)


    if scan.configs['driver'] == 'puppeteer':
        
        driver_data = asyncio.run(
            get_data(
                url=scan.site.site_url, 
                configs=scan.configs
            )
        )
        if 'html' in scan.type or 'full' in scan.type:
            html = driver_data['html']
            scan = Scan.objects.get(id=scan_id)
            scan.html = html
            scan.save()
        if 'logs' in scan.type or 'full' in scan.type:
            logs = driver_data['logs']
            scan = Scan.objects.get(id=scan_id)
            scan.logs = logs
            scan.save()


    # checking if scan is done
    scan = check_scan_completion(scan)

    return scan





def _vrt(scan_id):
    """
        Method to run the visual regression (vrt) component of the scan 
        allowing for multi-threading.

        returns -> `Scan` <obj>
    """
    scan = Scan.objects.get(id=scan_id)
    if scan.configs['driver'] == 'selenium':
        driver = driver_s_init(window_size=scan.configs['window_size'], device=scan.configs['device'])
        images = Image().scan(site=scan.site, driver=driver, configs=scan.configs)
        quit_driver(driver)

    if scan.configs['driver'] == 'puppeteer':
        images = asyncio.run(Image().scan_p(site=scan.site, configs=scan.configs))
    
    # updating Scan object
    scan = Scan.objects.get(id=scan_id)
    scan.images = images
    scan.save()

    # checking if scan is done
    scan = check_scan_completion(scan)

    return scan





def _lighthouse(scan_id):
    """
        Method to run the lighthouse component of the scan 
        allowing for multi-threading.

        returns -> `Scan` <obj>
    """
    scan = Scan.objects.get(id=scan_id)

    # running lighthouse
    lh_data = Lighthouse(site=scan.site, configs=scan.configs).get_data() 
    
    # updating Scan object
    scan = Scan.objects.get(id=scan_id)
    scan.lighthouse = lh_data
    scan.save()

    # checking if scan is done
    scan = check_scan_completion(scan)

    return scan






def _yellowlab(scan_id):
    """
        Method to run the yellowlab component of the scan 
        allowing for multi-threading.

        returns -> `Scan` <obj>
    """ 
    scan = Scan.objects.get(id=scan_id)

    # running yellowlab
    yl_data = Yellowlab(site=scan.site, configs=scan.configs).get_data()
    
    # updating Scan object
    scan = Scan.objects.get(id=scan_id)
    scan.yellowlab = yl_data
    scan.save()

    # checking if scan is done
    scan = check_scan_completion(scan)

    return scan
