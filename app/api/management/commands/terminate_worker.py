from cursion import celery
from django.core.management.base import BaseCommand
import time, os






# init warm shutdown (prevent new task acceptance) 
class Command(BaseCommand):

    def handle(self, *args, **options):

        # get worker / pod name
        default_worker = 'cursion-celery'
        if os.environ.get('THIS_POD_NAME'):
            default_worker = str(os.environ.get('THIS_POD_NAME'))

        # get celery worker
        this_worker = f"celery@{default_worker}"

        # sending initial SIGTERM to celery worker for warm-shutdown
        celery.app.control.broadcast('shutdown', destination=[this_worker])




# check if current tasks have completed
def wait_for_tasks_to_complete():

    # get worker / pod name
    default_worker = 'cursion-celery'
    if os.environ.get('THIS_POD_NAME'):
        default_worker = str(os.environ.get('THIS_POD_NAME'))

    # get celery worker
    this_worker = f"celery@{default_worker}"

    def get_task_list():
    
        # set default 
        tasks = 0

        try:
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
        
        except Exception as e:
            print(e)

        # return tasks count
        return int(tasks)

    # get length of active and reserved task lists
    tasks = get_task_list()

    # waiting for tasks to complete
    while tasks > 0:
        time.sleep(10)
        tasks = get_task_list()

        