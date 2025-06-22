from ..models import *
from cursion import settings






def record_task(
        resource_type: str=None, 
        resource_id: str=None, 
        task_id: str=None, 
        task_method: str=None, 
        **kwargs,
    ) -> bool:
    """ 
    Records task information in the `resource.system` 
    attribute.

    Expects: {
        'resource_type' : str (scan, test, caserun)
        'resource_id'   : str 
        'task_id'       : str 
        'task_method'   : str
        'kwargs'        : dict
    }
    
    Returns: max_attempts_reached <bool>
    """

    # set default 
    max_attempts_reached = False

    # get resource 
    if resource_type == 'scan':
        resource = Scan.objects.get(id=resource_id)
    if resource_type == 'test':
        resource = Test.objects.get(id=resource_id)
    if resource_type == 'caserun':
        resource = CaseRun.objects.get(id=resource_id)

    # get current resoruce.system.tasks data
    tasks = (resource.system or {}).get('tasks', [])

    # get component based on task_name
    component = task_method.replace('run_', '').replace('_bg', '').replace('_and_logs', '')

    # check if task exists
    i = 0
    exists = False
    for task in tasks:
        if task['component'] == component:
            # update existing task
            max_attempts_reached   = True if (tasks[i]['attempts'] >= settings.MAX_ATTEMPTS) else False
            tasks[i]['task_id']    = str(task_id)
            tasks[i]['attempts']   += 1 if not max_attempts_reached else tasks[i]['attempts']
            tasks[i]['kwargs']     = kwargs.get('kwargs')
            exists                 = True
        i += 1

    # append new task data
    if not exists:
        tasks.append({
            'attempts'      : int(1),
            'task_id'       : str(task_id),
            'task_method'   : str(task_method),
            'component'     : str(component),
            'kwargs'        : kwargs.get('kwargs'),
        })

    # update resource with new system data
    resource.system = resource.system or {}
    resource.system['tasks'] = tasks
    resource.save()

    # return
    return max_attempts_reached