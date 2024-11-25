from ...models import *
from rest_framework import serializers
from rest_framework.fields import UUIDField






kwargs = {
    'allow_null': False, 
    'read_only': True, 
    'pk_field': UUIDField(format='hex_verbose')
}




class LogSerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    id = serializers.PrimaryKeyRelatedField(**kwargs)

    class Meta:
        model = Log
        fields = ['id', 'user', 'path', 'time_created', 'request_type',
        'status', 'request_payload', 'response_payload'
        ]




class ProcessSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    site = serializers.PrimaryKeyRelatedField(source='site.id',**kwargs)

    class Meta:
        model = Process
        fields = ['id', 'site', 'type', 'time_created', 'time_completed',
        'success', 'info_url', 'progress', 'info', 'exception', 'object_id'
        ]




class SecretSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    user = serializers.ReadOnlyField(source='user.username')
    account = serializers.PrimaryKeyRelatedField(source='account.id', **kwargs)

    class Meta:
        model = Secret
        fields = ['id', 'account', 'user', 'time_created', 'name',
        ]




class SiteSerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    account = serializers.PrimaryKeyRelatedField(source='account.id', **kwargs)

    class Meta:
        model = Site
        fields = ['id', 'user', 'site_url', 'time_created', 'info',
        'tags', 'account', 'time_crawl_started', 'time_crawl_completed',
        ]




class PageSerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    account = serializers.PrimaryKeyRelatedField(source='account.id', **kwargs)
    site = serializers.PrimaryKeyRelatedField(source='site.id', **kwargs)

    class Meta:
        model = Page
        fields = ['id', 'user', 'site', 'page_url', 'time_created', 'info',
        'tags', 'account',
        ]




class ScanSerializer(serializers.HyperlinkedModelSerializer):
    site = serializers.PrimaryKeyRelatedField(source='site.id',**kwargs)
    page = serializers.PrimaryKeyRelatedField(source='page.id',**kwargs)
    paired_scan = serializers.PrimaryKeyRelatedField(source='paired_scan.id',**kwargs)
    id = serializers.PrimaryKeyRelatedField(**kwargs)

    class Meta:
        model = Scan
        fields = ['id', 'site', 'page', 'paired_scan', 'time_created',
        'time_completed', 'html', 'logs', 'lighthouse', 'yellowlab', 
        'images', 'configs', 'tags', 'type', 'score',
        ]




class SmallScanSerializer(serializers.HyperlinkedModelSerializer):
    site = serializers.PrimaryKeyRelatedField(source='site.id',**kwargs)
    page = serializers.PrimaryKeyRelatedField(source='page.id',**kwargs)
    paired_scan = serializers.PrimaryKeyRelatedField(source='paired_scan.id',**kwargs)
    lighthouse = serializers.SerializerMethodField()
    yellowlab = serializers.SerializerMethodField()
    id = serializers.PrimaryKeyRelatedField(**kwargs)

    def get_lighthouse(self, obj):
        return {'scores': obj.lighthouse['scores']}
    
    def get_yellowlab(self, obj):
        return {'scores': obj.yellowlab['scores']}

    class Meta:
        model = Scan
        fields = ['id', 'site', 'page', 'paired_scan', 'time_created', 'logs', 
        'time_completed', 'lighthouse', 'yellowlab', 'configs', 'tags', 'score',
        ]



        
class TestSerializer(serializers.HyperlinkedModelSerializer):
    site = serializers.PrimaryKeyRelatedField(source='site.id', **kwargs)
    page = serializers.PrimaryKeyRelatedField(source='page.id', **kwargs)
    pre_scan = serializers.PrimaryKeyRelatedField(source='pre_scan.id', **kwargs)
    post_scan = serializers.PrimaryKeyRelatedField(source='post_scan.id',**kwargs)
    id = serializers.PrimaryKeyRelatedField(**kwargs)

    class Meta:
        model = Test
        fields = ['id', 'site', 'page', 'time_created', 'time_completed',
        'pre_scan', 'post_scan', 'score', 'html_delta', 'logs_delta',
        'lighthouse_delta', 'yellowlab_delta', 'images_delta', 'type', 'threshold',
        'tags', 'pre_scan_configs', 'post_scan_configs', 'component_scores', 'status',
        ]




class SmallTestSerializer(serializers.HyperlinkedModelSerializer):
    site = serializers.PrimaryKeyRelatedField(source='site.id', **kwargs)
    page = serializers.PrimaryKeyRelatedField(source='page.id', **kwargs)
    pre_scan = serializers.PrimaryKeyRelatedField(source='pre_scan.id', **kwargs)
    post_scan = serializers.PrimaryKeyRelatedField(source='post_scan.id',**kwargs)
    id = serializers.PrimaryKeyRelatedField(**kwargs)

    class Meta:
        model = Test
        fields = ['id', 'site', 'page', 'time_created', 'time_completed',
        'pre_scan', 'post_scan', 'score', 'lighthouse_delta', 
        'yellowlab_delta', 'tags', 'component_scores', 'threshold', 'status',
        ]




class ScheduleSerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    alert = serializers.PrimaryKeyRelatedField(**kwargs)
    account = serializers.PrimaryKeyRelatedField(source='account.id', **kwargs)

    class Meta:
        model = Schedule
        fields = ['id', 'time_created', 'user', 'task_type',
        'timezone', 'begin_date', 'time', 'frequency', 'task', 'crontab_id',
        'periodic_task_id', 'status', 'alert', 'extras', 'account', 
        'scope', 'resources', 'time_last_run',
        ]




class AlertSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    schedule = serializers.PrimaryKeyRelatedField(**kwargs)
    user = serializers.ReadOnlyField(source='user.username')
    account = serializers.PrimaryKeyRelatedField(source='account.id', **kwargs)

    class Meta:
        model = Alert
        fields = ['id', 'expressions', 'actions', 'user', 'schedule',
        'time_created', 'name', 'account',
        ]




class ReportSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    page = serializers.PrimaryKeyRelatedField(source='page.id', **kwargs)
    site = serializers.PrimaryKeyRelatedField(source='site.id', **kwargs)
    user = serializers.ReadOnlyField(source='user.username')
    account = serializers.PrimaryKeyRelatedField(source='account.id', **kwargs)

    class Meta:
        model = Report
        fields = ['id', 'site', 'page', 'user', 'time_created', 'type',
        'path', 'info', 'account',
        ]




class CaseSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    user = serializers.ReadOnlyField(source='user.username')
    account = serializers.PrimaryKeyRelatedField(source='account.id', **kwargs)
    site = serializers.PrimaryKeyRelatedField(source='site.id', **kwargs)

    class Meta:
        model = Case
        fields = ['id', 'title', 'user', 'steps', 'time_created',
        'tags', 'account', 'site', 'type', 'site_url', 'processed'
        ]




class CaseRunSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    site = serializers.PrimaryKeyRelatedField(source='site.id', **kwargs)
    case = serializers.PrimaryKeyRelatedField(source='case.id', **kwargs)
    user = serializers.ReadOnlyField(source='user.username')
    account = serializers.PrimaryKeyRelatedField(source='account.id', **kwargs)

    class Meta:
        model = CaseRun
        fields = ['id', 'site', 'user', 'time_created', 'time_completed',
        'steps', 'case', 'title', 'configs', 'account', 'status',
        ]




class SmallCaseRunSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    site = serializers.PrimaryKeyRelatedField(source='site.id', **kwargs)
    case = serializers.PrimaryKeyRelatedField(source='case.id', **kwargs)
    user = serializers.ReadOnlyField(source='user.username')
    account = serializers.PrimaryKeyRelatedField(source='account.id', **kwargs)

    class Meta:
        model = CaseRun
        fields = ['id', 'site', 'user', 'time_created', 'time_completed',
        'case', 'title', 'configs', 'account', 'status',
        ]




class IssueSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    account = serializers.PrimaryKeyRelatedField(source='account.id', **kwargs)

    class Meta:
        model = Issue
        fields = ['id', 'time_created', 'trigger', 'account', 'title',
        'details', 'status', 'affected', 'labels'
        ]




class FlowSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    user = serializers.ReadOnlyField(source='user.username')
    account = serializers.PrimaryKeyRelatedField(source='account.id', **kwargs)

    class Meta:
        model = Flow
        fields = ['id', 'user', 'account', 'time_created', 'title',
        'nodes', 'edges', 'time_last_run',
        ]




class FlowRunSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    flow = serializers.PrimaryKeyRelatedField(source='flow.id', **kwargs)
    user = serializers.ReadOnlyField(source='user.username')
    account = serializers.PrimaryKeyRelatedField(source='account.id', **kwargs)
    site = serializers.PrimaryKeyRelatedField(source='site.id', **kwargs)

    class Meta:
        model = FlowRun
        fields = ['id', 'user', 'account', 'flow', 'time_created', 'title',
        'nodes', 'edges', 'status', 'time_completed', 'logs', 'site', 'configs'
        ]




class SmallFlowRunSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    flow = serializers.PrimaryKeyRelatedField(source='flow.id', **kwargs)
    user = serializers.ReadOnlyField(source='user.username')
    account = serializers.PrimaryKeyRelatedField(source='account.id', **kwargs)
    site = serializers.PrimaryKeyRelatedField(source='site.id', **kwargs)

    class Meta:
        model = FlowRun
        fields = ['id', 'user', 'account', 'flow', 'time_created', 'title',
        'status', 'time_completed', 'site', 'configs'
        ]





