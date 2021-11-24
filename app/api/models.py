from django.db import models
from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import datetime
from django.contrib.postgres.fields import JSONField
import uuid


def get_info_default():
    info_default = {
            'latest_scan': {
                'id': '',
                'time_created': '',
            },
            'latest_test': {
                'id': '',
                'time_created': '',
                'score': ''
            },
            'lighthouse': {
                'average': '',
                'seo': '',  
                'performance': '', 
                'accessibility': '', 
                'best_practices': '',
            },
            'status': {
                'ping': '',
                'health': '',
                'badge': 'neutral',
            },
        }
    return info_default



def get_scores_delta_default():
    scores_delta_default = {
        "seo_delta": None, 
        "current_average": None, 
        "performance_delta": None, 
        "accessibility_delta": None, 
        "best_practices_delta": None
    }
    return scores_delta_default



def get_audits_default():
    audits_default = {
        "seo": [], 
        "performance": [], 
        "accessibility": [], 
        "best-practices": []
    }
    return audits_default



def get_expressions_default():
    expressions_default = {
       'list': [
            {
                'joiner': None, 
                'data_type': None, 
                'operator': None, 
                'value': None, 
            },
       ],
    }
    return expressions_default


def get_actions_default():
    actions_default = {
        'list': [
            {
                'action_type': None, 
                'url': None, 
                'request': None, 
                'json': None, 
                'email': None, 
                'phone': None,
            },
        ],
    }
    return actions_default


def get_slack_default():
    slack_default = {
        "slack_name": None, 
        "bot_user_id": None, 
        "slack_team_id": None, 
        "bot_access_token": None, 
        "slack_channel_id": None, 
        "slack_channel_name": None,
    }
    return slack_default



class Site(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_url = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, serialize=True, null=True, blank=True)
    info = models.JSONField(serialize=True, null=True, blank=True, default=get_info_default)

    def __str__(self):
        return f'{self.site_url}'



class Scan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, serialize=True, blank=True)
    paired_scan = models.ForeignKey('self', on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    html = models.TextField(serialize=True, null=True, blank=True)
    logs = models.JSONField(serialize=True, null=True, blank=True)
    scores = models.JSONField(serialize=True, null=True, blank=True)
    audits = models.JSONField(serialize=True, null=True, blank=True, default=get_audits_default)

    def __str__(self):
        return f'{self.site.site_url}__scan'



class Test(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, serialize=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    time_completed = models.DateTimeField(serialize=True, null=True, blank=True)
    type = models.CharField(max_length=1000, serialize=True, null=True, blank=True) # (1) html (2) error_logs TODO decide on this attr
    pre_scan = models.ForeignKey(Scan, on_delete=models.CASCADE, serialize=True, null=True, blank=True, related_name='pre_scan')
    post_scan = models.ForeignKey(Scan, on_delete=models.CASCADE, serialize=True, null=True, blank=True, related_name='post_scan')
    score = models.FloatField(serialize=True, null=True, blank=True)
    html_delta = models.JSONField(serialize=True, null=True, blank=True)
    logs_delta = models.JSONField(serialize=True, null=True, blank=True)
    scores_delta = models.JSONField(serialize=True, null=True, blank=True, default=get_scores_delta_default)

    def __str__(self):
        return f'{self.site.site_url}__test'




class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, serialize=True)
    active = models.BooleanField(default=False, serialize=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    type = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    max_sites = models.IntegerField(serialize=True, null=True, blank=True)
    cust_id = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    sub_id = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    product_id = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    price_id = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    slack = models.JSONField(serialize=True, null=True, blank=True, default=get_slack_default)

    def __str__(self):
        return self.user.email




class Card(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, serialize=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, serialize=True)
    pay_method_id = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    brand = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    exp_month = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    exp_year = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    last_four = models.CharField(max_length=1000, serialize=True, null=True, blank=True)

    def __str__(self):
        return self.user.email




class Schedule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    automation = models.ForeignKey('Automation', on_delete=models.SET_NULL, null=True, blank=True, serialize=True, related_name='assoc_auto')
    time_created = models.DateTimeField(default=datetime.now, null=True, blank=True, serialize=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    task_type = models.CharField(max_length=100, default='test', serialize=True) # report, scan, test
    timezone = models.CharField(max_length=100, null=True, blank=True, serialize=True)
    begin_date = models.DateTimeField(default=datetime.now, serialize=True)
    time = models.CharField(max_length=100, null=True, blank=True, serialize=True)
    frequency = models.CharField(default="monthly", max_length=100, serialize=True) # daily, weekly, monthly,
    task = models.CharField(max_length=500, null=True, blank=True, serialize=True) # assigning shared task
    crontab_id = models.CharField(max_length=500, null=True, blank=True, serialize=True)
    periodic_task_id = models.CharField(max_length=500, null=True, blank=True, serialize=True)
    status = models.CharField(max_length=100, default='Active', null=True, blank=True, serialize=True)

    def __str__(self):
        return f'{self.site.site_url}__{self.task_type}'




class Automation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, null=True, blank=True, serialize=True, related_name='assoc_sch')
    expressions = models.JSONField(serialize=True, null=True, blank=True, default=get_expressions_default)
    actions = models.JSONField(serialize=True, null=True, blank=True, default=get_actions_default)

    def __str__(self):
        return f'{self.name}'
    



class Log(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, serialize=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    path = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    request_type = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    status = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    request_payload = models.JSONField(serialize=True, null=True, blank=True)
    response_payload = models.JSONField(serialize=True, null=True, blank=True)

    def __str__(self):
        return f'{self.status}__{self.request_type}__{self.path}'
