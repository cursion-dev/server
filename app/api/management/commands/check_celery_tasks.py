from scanerr import celery
from django.core.management.base import BaseCommand
import time

# checking if celery tasks have completed running

class Command(BaseCommand):

    def handle(self, *args, **options):

        def get_task_list():
            # Inspect all nodes.
            i = celery.app.control.inspect()
            # Tasks received, but are still waiting to be executed.
            reserved = i.reserved()
            print(f'Reserved tasks -> {str(reserved)}')
            # Active tasks
            active = i.active()
            print(f'Active tasks -> {str(reserved)}')
            tasks = len(active) + len(reserved)
        
        # get length of active and reserved task lists
        tasks = get_task_list()

        # waiting for tasks to complete
        while tasks > 0:
            time.sleep(10)
            tasks = get_task_list()

        