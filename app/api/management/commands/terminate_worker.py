from scanerr import celery
from django.core.management.base import BaseCommand
import time, os

# checking if celery tasks have completed running

class Command(BaseCommand):

    def handle(self, *args, **options):

        # get celery worker
        this_worker = f"celery@{str(os.environ.get('THIS_POD_NAME'))}"
        
        # sending initial SIGTERM to celery worker for warm-shutdown
        celery.app.control.broadcast('shutdown', destination=[this_worker])

        def get_task_list():
            # Inspect all nodes.
            i = celery.app.control.inspect()
            
            # Tasks received, but are still waiting to be executed.
            reserved = i.reserved()[this_worker]
            print(f'Reserved tasks -> {str(reserved)}')
            
            # Active tasks
            active = i.active()[this_worker]
            print(f'Active tasks -> {str(reserved)}')
            
            # Sum all tasks
            tasks = len(active) + len(reserved)
            return int(tasks)
        
        # get length of active and reserved task lists
        tasks = get_task_list()

        # waiting for tasks to complete
        while tasks > 0:
            time.sleep(10)
            tasks = get_task_list()

        