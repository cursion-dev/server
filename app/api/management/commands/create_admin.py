from django.core.management.base import BaseCommand
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from ...models import Account, Member, get_permissions_default
from ...utils.verify import verify
import os, secrets






# creates a new Admin user if None exists
class Command(BaseCommand):

    def handle(self, *args, **options):
        username = os.environ.get('ADMIN_USER')
        email = os.environ.get('ADMIN_EMAIL')
        password = os.environ.get('ADMIN_PASS')
        mode = os.environ.get('MODE')
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

            # default usage
            usage = {
                'sites': 0,
                'schedules': 0,
                'scans': 0,
                'tests': 0,
                'caseruns': 0,
                'flowruns': 0,
                'sites_allowed': 1000, 
                'pages_allowed': 10, 
                'schedules_allowed': 50, 
                'scans_allowed': 100000, 
                'tests_allowed': 100000, 
                'caseruns_allowed': 100000,
                'flowruns_allowed': 100000,
                'nodes_allowed': 50,
                'conditions_allowed': 25,
                'retention_days': 1000,
            }

            code = secrets.token_urlsafe(16)

            account = Account.objects.create(
                name='Admin',
                user=user,
                active=True,
                type='selfhost' if mode == 'selfhost' else 'admin',
                usage=usage,
                code=code,
            )

            # get permissonions or default
            permissions = get_permissions_default()

            member = Member.objects.create(
                user=user,
                email=email,
                status='active',
                type='admin',
                account=account,
                permissions=permissions
            )

        else:
            print('Accounts can only be initialized if no Accounts exist')

        if not Token.objects.filter(user=user).exists():
            Token.objects.create(user=user)