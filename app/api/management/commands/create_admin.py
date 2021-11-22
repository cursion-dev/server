from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os

class Command(BaseCommand):

    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True).count() == 0:
            username = os.environ.get('ADMIN_USER')
            email = os.environ.get('ADMIN_EMAIL')
            password = os.environ.get('ADMIN_PASS')
            print('Creating account for %s (%s)' % (username, email))
            admin = User.objects.create_superuser(email=email, username=username, password=password)
            admin.is_active = True
            admin.is_superuser = True
            admin.save()
        else:
            print('Admin accounts can only be initialized if no Accounts exist')