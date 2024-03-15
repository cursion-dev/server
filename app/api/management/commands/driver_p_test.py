from ...utils.driver_p import driver_test
from django.core.management.base import BaseCommand
import asyncio

# testing puppeteer, pyppeteer, and chromium installation and configs

class Command(BaseCommand):

    def handle(self, *args, **options):
        asyncio.run(driver_test())

    


