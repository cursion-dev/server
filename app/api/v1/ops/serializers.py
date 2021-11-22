from ...models import (Test, Site, Scan, Log, Schedule, Automation)
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
            'html', 'logs', 'scores'
        ]


class SmallScanSerializer(serializers.HyperlinkedModelSerializer):
    site = serializers.PrimaryKeyRelatedField(source='site.id',**kwargs)
    paired_scan = serializers.PrimaryKeyRelatedField(source='paired_scan.id',**kwargs)
    id = serializers.PrimaryKeyRelatedField(**kwargs)

    class Meta:
        model = Scan
        fields = ['id', 'site', 'paired_scan', 'time_created', 'logs', 'scores'
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
        'scores_delta'
        ]


class SmallTestSerializer(serializers.HyperlinkedModelSerializer):
    site = serializers.PrimaryKeyRelatedField(**kwargs)
    pre_scan = serializers.PrimaryKeyRelatedField(**kwargs)
    post_scan = serializers.PrimaryKeyRelatedField(source='post_scan.id',**kwargs)
    id = serializers.PrimaryKeyRelatedField(**kwargs)

    class Meta:
        model = Test
        fields = ['id', 'site', 'time_created', 'time_completed',
        'pre_scan', 'post_scan', 'score', 'scores_delta'
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
        'periodic_task_id', 'status', 'automation'
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