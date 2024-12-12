from django.core.management.base import BaseCommand
from ...utils.verify import verify






# verifies deployment
class Command(BaseCommand):

    def handle(self, *args, **options):
        verify()