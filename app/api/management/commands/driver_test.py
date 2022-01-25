from ...utils.driver import driver_init
from django.core.management.base import BaseCommand
import time, os, sys

# testing selenium, chromedriver, and chromium installation and configs

class Command(BaseCommand):

    def handle(self, *args, **options):
        try:
            driver = driver_init()
            driver.get('https://google.com')
            title = driver.title
            if title == 'Google':
                status = 'Success'
            else:
                status = 'Failed'
        except:
            status = 'Failed'
            title = 'NO TITLE RETURNED'

        sys.stdout.write('Test results --> ' + status +'\n'
            + 'Returned title was --> ' + title +'\n'
            )
        sys.exit(0)

