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



class SiteSerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    id = serializers.PrimaryKeyRelatedField(**kwargs)

    class Meta:
        model = Site
        fields = ['id', 'user', 'site_url', 'time_created', 'info']


class ScanSerializer(serializers.HyperlinkedModelSerializer):
    site = serializers.PrimaryKeyRelatedField(source='site.id',**kwargs)
    paired_scan = serializers.PrimaryKeyRelatedField(source='paired_scan.id',**kwargs)
    id = serializers.PrimaryKeyRelatedField(**kwargs)

    class Meta:
        model = Scan
        fields = ['id', 'site', 'paired_scan', 'time_created',
        'time_completed', 'html', 'logs', 'lighthouse', 'yellowlab', 
        'images', 'configs',
        ]


class SmallScanSerializer(serializers.HyperlinkedModelSerializer):
    site = serializers.PrimaryKeyRelatedField(source='site.id',**kwargs)
    paired_scan = serializers.PrimaryKeyRelatedField(source='paired_scan.id',**kwargs)
    id = serializers.PrimaryKeyRelatedField(**kwargs)

    class Meta:
        model = Scan
        fields = ['id', 'site', 'paired_scan', 'time_created', 'logs', 
        'time_completed', 'lighthouse', 'yellowlab', 'configs', 
        ]

        
class TestSerializer(serializers.HyperlinkedModelSerializer):
    site = serializers.PrimaryKeyRelatedField(**kwargs)
    pre_scan = serializers.PrimaryKeyRelatedField(**kwargs)
    post_scan = serializers.PrimaryKeyRelatedField(source='post_scan.id',**kwargs)
    id = serializers.PrimaryKeyRelatedField(**kwargs)

    class Meta:
        model = Test
        fields = ['id', 'site', 'time_created', 'time_completed',
        'pre_scan', 'post_scan', 'score', 'html_delta', 'logs_delta',
        'lighthouse_delta', 'yellowlab_delta', 'images_delta', 'type',
        ]


class SmallTestSerializer(serializers.HyperlinkedModelSerializer):
    site = serializers.PrimaryKeyRelatedField(**kwargs)
    pre_scan = serializers.PrimaryKeyRelatedField(**kwargs)
    post_scan = serializers.PrimaryKeyRelatedField(source='post_scan.id',**kwargs)
    id = serializers.PrimaryKeyRelatedField(**kwargs)

    class Meta:
        model = Test
        fields = ['id', 'site', 'time_created', 'time_completed',
        'pre_scan', 'post_scan', 'score', 'lighthouse_delta', 
        'yellowlab_delta',
        ]


class ScheduleSerializer(serializers.HyperlinkedModelSerializer):
    site = serializers.PrimaryKeyRelatedField(**kwargs)
    user = serializers.ReadOnlyField(source='user.username')
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    automation = serializers.PrimaryKeyRelatedField(**kwargs)

    class Meta:
        model = Schedule
        fields = ['id', 'site', 'time_created', 'user', 'task_type',
        'timezone', 'begin_date', 'time', 'frequency', 'task', 'crontab_id',
        'periodic_task_id', 'status', 'automation', 'extras'
        ]



class AutomationSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    schedule = serializers.PrimaryKeyRelatedField(**kwargs)
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Automation
        fields = ['id', 'expressions', 'actions', 'user', 'schedule',
        'time_created', 'name'
        ]




class ReportSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.PrimaryKeyRelatedField(**kwargs)
    site = serializers.PrimaryKeyRelatedField(source='site.id', **kwargs)
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Report
        fields = ['id', 'site', 'user', 'time_created', 'type',
        'path', 'info'
        ]