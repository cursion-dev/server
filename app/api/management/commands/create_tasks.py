from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from datetime import datetime






# creating default system tasks
class Command(BaseCommand):

    def handle(self, *args, **options):

        tasks = [
            {
                'every': 3,
                'peroid': IntervalSchedule.SECONDS,
                'name': 'Redeliver Failed Tasks',
                'task': 'api.tasks.redeliver_failed_tasks'
            },
            {
                'every': 1,
                'peroid': IntervalSchedule.DAYS,
                'name': 'Data Retention Cleanup',
                'task': 'api.tasks.data_retention'
            },
            {
                'every': 1,
                'peroid': IntervalSchedule.DAYS,
                'name': 'Reset Account Usage',
                'task': 'api.tasks.reset_account_usage'
            },
        ]

        # loop through and create 
        # PeriodicTasks for each 
        for task in tasks:

            print(f'Setting up Task: {task.get('name')}')

            try:
                # create the schedule
                schedule, created = IntervalSchedule.objects.get_or_create(
                    every=task.get('every'),
                    period=task.get('period'),
                )

                # create the task
                PeriodicTask.objects.create(
                    interval=schedule,
                    name=task.get('name'),
                    task=task.get('task')
                )
            
            except Exception as e:
                print(e)

