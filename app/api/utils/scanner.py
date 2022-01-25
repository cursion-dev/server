from .driver import driver_init
from ..models import Site, Scan, Test
from django.forms.models import model_to_dict
from django.core.serializers.json import DjangoJSONEncoder
from .lighthouse import Lighthouse
from .image import Image
import time, os, sys, json



class Scanner():

    def __init__(self, site=None, scan=None):
        if site == None and scan != None:
            site = scan.site
        self.site = site
        self.driver = driver_init()
        self.scan = scan


    def first_scan(self):
        self.driver.get(self.site.site_url)
        time.sleep(5)
        html = self.driver.page_source
        logs = self.driver.get_log('browser')
        images = Image().scan(site=self.site, driver=self.driver)
        self.driver.quit()
        lh_data = Lighthouse(self.site).get_data()


        if self.scan:
            self.scan.html = html
            self.scan.logs = logs
            self.scan.images = images
            self.scan.scores = lh_data["scores"]
            self.scan.audits = lh_data["audits"]
            self.scan.save()
            first_scan = self.scan
        else:
            first_scan = Scan.objects.create(
                site=self.site, html=html, 
                logs=logs, scores=lh_data["scores"],
                audits=lh_data["audits"], images=images
            )

        self.update_site_info(first_scan)

        return first_scan


    def second_scan(self):
        first_scan = Scan.objects.filter(
            site=self.site
        ).order_by('-time_created').first()

        self.driver.get(self.site.site_url)
        time.sleep(5)
        html = self.driver.page_source
        logs = self.driver.get_log('browser')
        images = Image().scan(site=self.site, driver=self.driver)
        self.driver.quit()
        lh_data = Lighthouse(self.site).get_data()

        second_scan = Scan.objects.create(
            site=self.site, paired_scan=first_scan,
            html=html, logs=logs, scores=lh_data['scores'],
            audits=lh_data['audits'], images=images
        )
        second_scan.save()

        first_scan.paried_scan = second_scan
        first_scan.save()

        self.update_site_info(second_scan)
        
        return second_scan


    
    def update_site_info(self, scan):
        if scan.scores['average'] == None:
            health = 'No Data'
            badge = 'neutral'
        elif float(scan.scores['average']) >= 75:
            health = 'Good'
            badge = 'success'
        elif 75 > float(scan.scores['average']) >= 60:
            health = 'Okay'
            badge = 'warning'
        elif 60 > float(scan.scores['average']):
            health = 'Poor'
            badge = 'danger'

        self.site.info['latest_scan']['id'] = str(scan.id)
        self.site.info['latest_scan']['time_created'] = str(scan.time_created)
        self.site.info['lighthouse'] = scan.scores
        self.site.info['status']['health'] = str(health)
        self.site.info['status']['badge'] = str(badge)

        self.site.save()

        return self.site