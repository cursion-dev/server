from ...utils.driver import driver_test
from django.core.management.base import BaseCommand

# testing selenium, chromedriver, and chromium installation and configs

class Command(BaseCommand):

    def handle(self, *args, **options):
        driver_test()
        

