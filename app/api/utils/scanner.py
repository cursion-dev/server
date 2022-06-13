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
            type=['full']
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

        self.update_site_info(first_scan)

        return first_scan





    def second_scan(self):
        """
            Method to run a scan and attach existing `Scan` obj to it.

            returns -> `Scan` <obj>
        """
        if not self.scan:
            first_scan = Scan.objects.filter(
                site=self.site
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

        self.update_site_info(second_scan)
        
        return second_scan


    
    def update_site_info(self, scan):
        
        health = 'No Data'
        badge = 'neutral'
        d = 0
        score = 0

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
            if self.site.info['status']['score'] is not None:
                score = float(self.site.info['status']['score'])
                health = self.site.info['status']['health']
                badge = self.site.info['status']['badge']
            else:
                score = None

        self.site.info['latest_scan']['id'] = str(scan.id)
        self.site.info['latest_scan']['time_created'] = str(scan.time_created)
        self.site.info['latest_scan']['time_completed'] = str(scan.time_completed)
        self.site.info['lighthouse'] = scan.lighthouse.get('scores')
        self.site.info['yellowlab'] = scan.yellowlab.get('scores')
        self.site.info['status']['health'] = str(health)
        self.site.info['status']['badge'] = str(badge)
        self.site.info['status']['score'] = score

        self.site.save()

        return self.site