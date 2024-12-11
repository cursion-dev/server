from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import datetime, timezone as tz
from django.contrib.postgres.fields import JSONField
from cursion import settings
import uuid






def get_info_default():
    info_default = {
            'latest_scan': {
                'id': None,
                'time_created': None,
                'time_completed': None,
                'score': None,
            },
            'latest_test': {
                'id': None,
                'time_created': None,
                'time_completed': None,
                'score': None,
                'status': None
            },
            'lighthouse': {
                'average': None,
                'seo': None,
                'crux': None, 
                'performance': None, 
                'accessibility': None, 
                'best_practices': None,
            },
            'yellowlab': {
                'globalScore': None,
                'pageWeight': None,
                'images': None, 
                'domComplexity': None, 
                'javascriptComplexity': None,
                'badJavascript': None,
                'jQuery': None,
                'cssComplexity': None,
                'badCSS': None,
                'fonts': None,
                'serverConfig': None, 
            }
        }
    return info_default




def get_small_info_default():
    info_default = {
            'latest_scan': {
                'id': None,
                'time_created': None,
                'time_completed': None,
                'score': None,
            },
            'latest_test': {
                'id': None,
                'time_created': None,
                'time_completed': None,
                'score': None,
                'status': None
            }
        }
    return info_default




def get_lh_delta_default():
    lh_delta_default = {
        "scores": {
            "seo_delta": None, 
            "performance_delta": None, 
            "accessibility_delta": None, 
            "best-practices_delta": None,
            "crux_delta": None,
            "average_delta" : None,
            "current_average": None, 
        },
        "audits": None
    }
    return lh_delta_default




def get_yl_delta_default():
    yl_delta_default = {
        "scores": {
            "average_delta": None,
            "pageWeight_delta": None, 
            "images_delta": None, 
            "domComplexity_delta": None, 
            "javascriptComplexity_delta": None,
            "badJavascript_delta": None,
            "jQuery_delta": None,
            "cssComplexity_delta": None,
            "badCSS_delta": None,
            "fonts_delta": None,
            "serverConfig_delta": None, 
        },
        "audits": None
    }
    return yl_delta_default




def get_lh_default():
    lh_default = {
       "scores": {
            "seo": None, 
            "performance": None, 
            "accessibility": None, 
            "best_practices": None,
            "crux": None, 
            "average": None
       },
       "audits": None,
    }
    return lh_default




def get_yl_default():
    yl_default = {
       "scores": {
            "globalScore": None,
            "pageWeight": None, 
            "images": None, 
            "domComplexity": None, 
            "javascriptComplexity": None,
            "badJavascript": None,
            "jQuery": None,
            "cssComplexity": None,
            "badCSS": None,
            "fonts": None,
            "serverConfig": None,
       },
       "audits": None,
    }
    return yl_default




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




def get_steps_default():
    steps_default = [
            {
                'action': {
                    'type': None, 
                    'element': None,
                    'path': None,
                    'text': None,
                }, 
                'assertion': {
                    'type': None,
                    'element': None,
                    'text': None,
                }, 
            },
        ]
    return steps_default




def get_scores_default():
    scores_default = {
        'html': None,
        'logs': None,
        'lighthouse': None,
        'yellowlab': None,
        'vrt': None
    }
    return scores_default




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




def get_tags_default():
    tags_default = None,
    return tags_default




def get_default_configs():
    configs = settings.CONFIGS
    return configs




def get_usage_default():
    usage = {
        'sites': 0,
        'schedules': 0,
        'scans': 0,
        'tests': 0,
        'caseruns': 0,
        'flowruns': 0,
        'sites_allowed': 1, 
        'pages_allowed': 3, 
        'schedules_allowed': 1, 
        'scans_allowed': 30, 
        'tests_allowed': 30, 
        'caseruns_allowed': 15,
        'flowruns_allowed': 5,
        'nodes_allowed': 4,
        'conditions_allowed': 1,
        'retention_days': 15,
    }
    return usage




def get_meta_default():
    meta = {
        'last_usage_reset': datetime.now(tz.utc).strftime('%Y-%m-%d %H:%M:%S.%f'),
        'coupon': {
            'code': '', 
            'discount': 0
        }
    }
    return meta




def get_account_info_default():
    info = {'survey': []}
    return info




def get_permissions_default():
    permissions = {
        'actions': [
            'add', 'get', 'update', 'delete'
        ],
        'resources': [
            'site', 'page', 'issue', 'case', 'caserun',
            'flow', 'flowrun', 'test', 'scan', 'schedule', 
            'alert', 'secret', 'report', 'process', 'log'
        ], 
        'sites': []
    }
    return permissions




def get_system_default():
    system = {
        'tasks': [],
    }
    return system




def get_nodes_default():
    nodes = [
        {
            'id': '1',
            'position': {
                'x': 0,
                'y': 0
            },
            'type': 'basic',
            'parentId': None,
            'data': {
                'id': '1',         # duplicate for client support
                'position': {      # duplicate for client support
                    'x': 0,
                    'y': 0
                }, 
                'parentId': None,  # duplicate for client support
                'task_type': None,
                'configs': settings.CONFIGS,
                'conditions': None,
                'start_if': None,
            }
        },
    ]
    return nodes




def get_edges_default():
    edges = []
    return edges




def get_license_key():
    license_key = 'cursion-license-' + secrets.token_hex(32)
    return license_key






class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, serialize=True)
    # phone = models.CharField(max_length=50, serialize=True, null=True, blank=True) ## -> REMOVING !!!!
    active = models.BooleanField(default=False, serialize=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    type = models.CharField(max_length=1000, serialize=True, null=True, blank=True, default='free')
    code = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    license_key = models.CharField(max_length=100, serialize=True, null=True, blank=True, default=get_license_key) ## -> NEW!!!!!
    # sites_allowed = models.IntegerField(serialize=True, null=True, blank=True, default=1) ## -> REMOVING!!!!
    # max_pages = models.IntegerField(serialize=True, null=True, blank=True, default=3) ## -> REMOVING!!!!
    # max_schedules = models.IntegerField(serialize=True, null=True, blank=True, default=1) ## -> REMOVING!!!!
    # retention_days = models.IntegerField(serialize=True, null=True, blank=True, default=3) ## -> REMOVING!!!!
    cust_id = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    sub_id = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    product_id = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    price_id = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    price_amount = models.IntegerField(serialize=True, null=True, blank=True, default=0)
    interval = models.CharField(max_length=50, serialize=True, null=True, blank=True, default='month')
    usage = models.JSONField(serialize=True, null=True, blank=True, default=get_usage_default)
    slack = models.JSONField(serialize=True, null=True, blank=True, default=get_slack_default)
    configs = models.JSONField(serialize=True, null=True, blank=True, default=get_default_configs)
    info = models.JSONField(serialize=True, null=True, blank=True, default=get_account_info_default) ## -> NEW!!!!!
    meta = models.JSONField(serialize=True, null=True, blank=True, default=get_meta_default)
   

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




class Member(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, serialize=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    email = models.CharField(max_length=1000, serialize=True, null=True, blank=True) # created by Account admin
    phone = models.CharField(max_length=50, serialize=True, null=True, blank=True)
    status = models.CharField(max_length=1000, serialize=True, null=True, blank=True)  # pending, active
    type = models.CharField(max_length=1000, serialize=True, null=True, blank=True)  # admin, contributor, client
    permissions = models.JSONField(serialize=True, null=True, blank=True, default=get_permissions_default) ## NEW !!!!!!!!
    time_created = models.DateTimeField(default=timezone.now, serialize=True)

    def __str__(self):
        return f'{self.email}__{self.account.name}'




class Secret(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, serialize=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    name = models.CharField(max_length=500, serialize=True, null=True, blank=True)
    value = models.TextField(serialize=True, null=True, blank=True)
    
    def __str__(self):
        return f'{self.name}'




class Site(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_url = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    time_crawl_started = models.DateTimeField(serialize=True, null=True, blank=True)
    time_crawl_completed =  models.DateTimeField(serialize=True, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, serialize=True, null=True, blank=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    info = models.JSONField(serialize=True, null=True, blank=True, default=get_small_info_default)
    tags = models.JSONField(serialize=True, null=True, blank=True, default=get_tags_default)

    def __str__(self):
        return f'{self.site_url}'




class Page(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, serialize=True, blank=True)
    page_url = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, serialize=True, null=True, blank=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    info = models.JSONField(serialize=True, null=True, blank=True, default=get_info_default)
    tags = models.JSONField(serialize=True, null=True, blank=True, default=get_tags_default)

    def __str__(self):
        return f'{self.page_url}'




class Scan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, serialize=True, blank=True)
    page = models.ForeignKey(Page, on_delete=models.CASCADE, serialize=True, blank=True)
    paired_scan = models.ForeignKey('self', on_delete=models.SET_NULL, serialize=True, null=True, blank=True)
    type = models.JSONField(serialize=True, null=True, blank=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    time_completed = models.DateTimeField(serialize=True, null=True, blank=True)
    html = models.CharField(max_length=5000, serialize=True, null=True, blank=True)
    logs = models.JSONField(serialize=True, null=True, blank=True)
    images = models.JSONField(serialize=True, null=True, blank=True)
    score = models.FloatField(serialize=True, null=True, blank=True)
    lighthouse = models.JSONField(serialize=True, null=True, blank=True, default=get_lh_default)
    yellowlab = models.JSONField(serialize=True, null=True, blank=True, default=get_yl_default)
    configs = models.JSONField(serialize=True, null=True, blank=True)
    tags = models.JSONField(serialize=True, null=True, blank=True, default=get_tags_default)
    system = models.JSONField(serialize=True, null=True, blank=True, default=get_system_default)

    def __str__(self):
        return f'{self.id}__scan'




class Test(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, serialize=True)
    page = models.ForeignKey(Page, on_delete=models.CASCADE, serialize=True, blank=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    time_completed = models.DateTimeField(serialize=True, null=True, blank=True)
    type = models.JSONField(serialize=True, null=True, blank=True)
    pre_scan = models.ForeignKey(Scan, on_delete=models.SET_NULL, serialize=True, null=True, blank=True, related_name='pre_scan')
    post_scan = models.ForeignKey(Scan, on_delete=models.SET_NULL, serialize=True, null=True, blank=True, related_name='post_scan')
    score = models.FloatField(serialize=True, null=True, blank=True)
    threshold = models.FloatField(serialize=True, null=True, blank=True)
    status = models.CharField(max_length=500, serialize=True, null=True, blank=True)
    component_scores = models.JSONField(serialize=True, null=True, blank=True, default=get_scores_default)
    html_delta = models.CharField(max_length=5000, serialize=True, null=True, blank=True)
    logs_delta = models.JSONField(serialize=True, null=True, blank=True)
    lighthouse_delta = models.JSONField(serialize=True, null=True, blank=True, default=get_lh_delta_default)
    yellowlab_delta = models.JSONField(serialize=True, null=True, blank=True, default=get_yl_delta_default)
    images_delta = models.JSONField(serialize=True, null=True, blank=True)
    tags = models.JSONField(serialize=True, null=True, blank=True, default=get_tags_default)
    pre_scan_configs = models.JSONField(serialize=True, null=True, blank=True)
    post_scan_configs = models.JSONField(serialize=True, null=True, blank=True)

    def __str__(self):
        return f'{self.id}_test'




class Case(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=1000, serialize=True, null=True, blank=True)  ## RENAMED !!!! from name
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    site_url = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    steps = models.JSONField(serialize=True, null=True, blank=True, default=get_steps_default)
    type = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    processed = models.BooleanField(default=False, serialize=True)
    tags = models.JSONField(serialize=True, null=True, blank=True, default=get_tags_default)

    def __str__(self):
        return f'{self.title}' if len(self.title) > 0 else str(id)




class CaseRun(models.Model):  ## -> RENAME from Testcase !!!!!!!
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, serialize=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    title = models.CharField(max_length=500, null=True, blank=True, serialize=True)  ## RENAMED !!!! from case_name
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    time_completed = models.DateTimeField(null=True, blank=True, serialize=True)
    status = models.CharField(max_length=20, default='working', null=True, blank=True, serialize=True) 
    steps = models.JSONField(serialize=True, null=True, blank=True)
    configs = models.JSONField(serialize=True, null=True, blank=True)

    def __str__(self):
        return f'{self.title}_caserun'




class Report(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    page = models.ForeignKey(Page, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    path = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    type = models.JSONField(serialize=True, null=True, blank=True)
    info = models.JSONField(serialize=True, null=True, blank=True)

    def __str__(self):
        return f'{self.page.page_url}_report'




class Issue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    trigger = models.JSONField(serialize=True, null=True, blank=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    title = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    details = models.TextField(serialize=True, null=True, blank=True)
    status = models.CharField(max_length=500, serialize=True, default='open')
    affected = models.JSONField(serialize=True, null=True, blank=True)
    labels = models.JSONField(serialize=True, null=True, blank=True)
    read = models.BooleanField(default=False, serialize=True)

    def __str__(self):
        return f'{self.title if self.title is not None else self.id}_issue'




class Flow(models.Model): ## -> NEW !!!!!!!
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    time_last_run = models.DateTimeField(serialize=True, null=True, blank=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    title = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    nodes = models.JSONField(serialize=True, null=True, blank=True, default=get_nodes_default)
    edges = models.JSONField(serialize=True, null=True, blank=True, default=get_edges_default)

    def __str__(self):
        return f'{self.title if self.title is not None else self.id}_flow'




class FlowRun(models.Model): ## -> NEW !!!!!!!
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    time_completed = models.DateTimeField(serialize=True, null=True, blank=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    flow = models.ForeignKey(Flow, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    title = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    status = models.CharField(max_length=500, serialize=True, default='working')
    nodes = models.JSONField(serialize=True, null=True, blank=True)
    edges = models.JSONField(serialize=True, null=True, blank=True)
    logs = models.JSONField(serialize=True, null=True, blank=True)
    configs = models.JSONField(serialize=True, null=True, blank=True)

    def __str__(self):
        return f'{self.flow.title if self.flow.title is not None else self.id}_flowrun'




class Schedule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    scope = models.CharField(max_length=100, default='account', serialize=True)
    resources = models.JSONField(serialize=True, null=True, blank=True)
    alert = models.ForeignKey('Alert', on_delete=models.SET_NULL, null=True, blank=True, serialize=True, related_name='assoc_alert')
    time_created = models.DateTimeField(default=datetime.now, null=True, blank=True, serialize=True)
    time_last_run = models.DateTimeField(null=True, blank=True, serialize=True)
    task_type = models.CharField(max_length=100, default='test', serialize=True)
    timezone = models.CharField(max_length=100, null=True, blank=True, serialize=True)
    begin_date = models.DateTimeField(default=datetime.now, serialize=True)
    time = models.CharField(max_length=100, null=True, blank=True, serialize=True)
    frequency = models.CharField(default="monthly", max_length=100, serialize=True)
    task = models.CharField(max_length=500, null=True, blank=True, serialize=True)
    crontab_id = models.CharField(max_length=500, null=True, blank=True, serialize=True)
    periodic_task_id = models.CharField(max_length=500, null=True, blank=True, serialize=True)
    status = models.CharField(max_length=100, default='Active', null=True, blank=True, serialize=True)
    extras = models.JSONField(serialize=True, null=True, blank=True)

    def __str__(self):
        return f'{self.account.name}_{self.task_type}'




class Alert(models.Model):  ## -> RENAME from Automation !!!!!!!
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, serialize=True, null=True, blank=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, null=True, blank=True, serialize=True, related_name='assoc_sch')
    expressions = models.JSONField(serialize=True, null=True, blank=True, default=get_expressions_default)
    actions = models.JSONField(serialize=True, null=True, blank=True, default=get_actions_default)

    def __str__(self):
        return f'{self.id}'




class Mask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    active = models.BooleanField(serialize=True, default=True)
    mask_id = models.CharField(max_length=1000, serialize=True, null=True, blank=True)

    def __str__(self):
        return f'{self.id}_mask'




class Process(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, serialize=True)
    type = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    object_id = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    time_created = models.DateTimeField(default=timezone.now, serialize=True)
    time_completed = models.DateTimeField(serialize=True, null=True, blank=True)
    success = models.BooleanField(serialize=True, default=False)
    exception = models.TextField(serialize=True, null=True, blank=True)
    info = models.JSONField(serialize=True, null=True, blank=True)
    info_url = models.CharField(max_length=1000, serialize=True, null=True, blank=True)
    progress = models.FloatField(serialize=True, null=True, blank=True)

    def __str__(self):
        return f'{self.id}_process'




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
        return f'{self.status}_{self.request_type}_{self.path}'



