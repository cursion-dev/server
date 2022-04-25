from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from ...models import Account
from ...utils.verify import verify
import os

class Command(BaseCommand):

    def handle(self, *args, **options):
        username = os.environ.get('ADMIN_USER')
        email = os.environ.get('ADMIN_EMAIL')
        password = os.environ.get('ADMIN_PASS')
        if User.objects.filter(is_superuser=True).count() == 0:
            print('Creating Admin User for %s (%s)' % (username, email))
            admin = User.objects.create_superuser(email=email, username=username, password=password)
            admin.is_active = True
            admin.is_superuser = True
            admin.save()
        else:
            print('Admin Users can only be initialized if no Admin User exist')

        user = User.objects.get(username=username)
        if not Account.objects.filter(user=user).exists():
            print('Funding account for %s' % (username))
            Account.objects.create(
                user=user,
                active=True,
                type='enterprise',
                max_sites=10000, 
            )
        else:
            print('Accounts can only be initialized if no Accounts exist')

        verify()