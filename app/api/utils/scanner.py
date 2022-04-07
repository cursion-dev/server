from .driver_s import driver_init as driver_s_init, quit_driver
from .driver_s import driver_wait
from .driver_p import get_data
from ..models import Site, Scan, Test
from django.forms.models import model_to_dict
from django.core.serializers.json import DjangoJSONEncoder
from .lighthouse import Lighthouse
from .yellowlab import Yellowlab
from .image import Image
import time, os, sys, json, asyncio



class Scanner():

    def __init__(
            self, 
            site=None, 
            scan=None, 
            configs=None,
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
        self.scan = scan
        self.configs = configs



    def first_scan(self):
        """
            Method to run a scan independently of an existing `scan` obj.

            returns -> `Scan` <obj>
        """
        
        if self.configs['driver'] == 'selenium':
            self.driver.get(self.site.site_url)
            html = self.driver.page_source
            logs = self.driver.get_log('browser')
            images = Image().scan(site=self.site, driver=self.driver, configs=self.configs)
            quit_driver(self.driver)
        else:
            driver_data = asyncio.run(
                get_data(
                    url=self.site.site_url, 
                    configs=self.configs
                )
            )
            html = driver_data['html']
            logs = driver_data['logs']
            images = asyncio.run(Image().scan_p(site=self.site, configs=self.configs))
        
        lh_data = Lighthouse(site=self.site, configs=self.configs).get_data()
        yl_data = Yellowlab(site=self.site, configs=self.configs).get_data()


        if self.scan:
            self.scan.html = html
            self.scan.logs = logs
            self.scan.images = images
            self.scan.lighthouse = lh_data
            self.scan.yellowlab = yl_data
            self.scan.configs = self.configs
            self.scan.save()
            first_scan = self.scan
        else:
            first_scan = Scan.objects.create(
                site=self.site, html=html, 
                logs=logs, lighthouse=lh_data,
                images=images, yellowlab=yl_data,
                configs=self.configs
            )

        self.update_site_info(first_scan)

        return first_scan





    def second_scan(self):
        """
            Method to run a scan and attach existing `scan` obj to it.

            returns -> `Scan` <obj>
        """
        if not self.scan:
            first_scan = Scan.objects.filter(
                site=self.site
            ).order_by('-time_created').first()
        
        else:
            first_scan = self.scan

        if self.configs['driver'] == 'selenium':
            self.driver.get(self.site.site_url)
            html = self.driver.page_source
            logs = self.driver.get_log('browser')
            images = Image().scan(site=self.site, driver=self.driver, configs=self.configs)
            quit_driver(self.driver)
        else:
            driver_data = asyncio.run(
                get_data(
                    url=self.site.site_url, 
                    configs=self.configs
                )
            )
            html = driver_data['html']
            logs = driver_data['logs']
            images = asyncio.run(Image().scan_p(site=self.site, configs=self.configs))
            
        lh_data = Lighthouse(site=self.site, configs=self.configs).get_data()
        yl_data = Yellowlab(site=self.site, configs=self.configs).get_data()

        second_scan = Scan.objects.create(
            site=self.site, paired_scan=first_scan,
            html=html, logs=logs, lighthouse=lh_data,
            images=images, yellowlab=yl_data, 
            configs=self.configs
        )
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
            else:
                score = None

        self.site.info['latest_scan']['id'] = str(scan.id)
        self.site.info['latest_scan']['time_created'] = str(scan.time_created)
        self.site.info['lighthouse'] = scan.lighthouse['scores']
        self.site.info['yellowlab'] = scan.yellowlab['scores']
        self.site.info['status']['health'] = str(health)
        self.site.info['status']['badge'] = str(badge)
        self.site.info['status']['score'] = score

        self.site.save()

        return self.site