from ..models import *
from django.utils import timezone
from datetime import datetime






def update_flowrun(*args, **kwargs) -> object:
    """ 
    Updates the `FlowRun`, matching the 'flowrun_id',
    with the **kwargs data

    Args:
        'kwargs' : {
            'flowrun_id'   : str
            'node_index'   : int or str,
            'messsage'     : str,
            'node_status'  : str,
            'objects'      : list of dicts
        }
    
    Returns: `FlowRun` obj
    """
    
    # get passed kwargs
    flowrun_id = kwargs.get('flowrun_id')
    node_index = kwargs.get('node_index')
    node_status = kwargs.get('node_status')
    message = kwargs.get('message')
    objects = kwargs.get('objects')

    # get flowrun
    flowrun = FlowRun.objects.get(id=flowrun_id)

    # set timestamp
    timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S.%f')


    # find flowrun.edge by target
    def get_edge_by_target(target: str=None) -> dict:
        # defaults
        edge = None
        index = 0
        # find target
        for e in flowrun.edges:
            if e['target'] == target:
                edge = e
                break
            index+=1
        # return data
        return {
            'index': index,
            'edge': edge
        }


    # update object_list
    def add_or_update_objects(object_list, objects):
        i = 0
        # find obj
        for obj in objects:
            exists = False
            j = 0
            for o in object_list:
                if obj['parent'] == o['parent']:
                    exists = True
                    # update
                    object_list[j] = obj
                    break
                j+=1
            # add
            if not exists:
                object_list.append(obj) 
            i+=1
        return object_list


    # check if all objects are complete
    def objects_are_complete(object_list):
        if len(object_list) == 0:
            return True
        for obj in object_list:
            if obj['status'] == 'working':
                return False
        return True


    # get collective status of  
    def get_step_status(object_list):
        statuses = [obj['status'] for obj in object_list]
        if len(object_list) == 0:
            return 'passed'
        if 'working' in statuses:
            return 'working'
        if 'failed' in statuses and 'working' not in statuses:
            return 'failed'
        return 'passed'
    

    # update flowrun logs, nodes, & edges
    nodes = flowrun.nodes
    edges = flowrun.edges
    logs = flowrun.logs


    if node_index is not None:
        # get node object_list
        object_list = nodes[int(node_index)]['data'].get('objects', [])

        # update object_list if objects
        if objects:
            object_list = add_or_update_objects(object_list, objects)
            nodes[int(node_index)]['data']['objects'] = object_list

        # if node_status is provided
        if node_status:
            nodes[int(node_index)]['data']['status'] = node_status
            if node_status != 'working':
                nodes[int(node_index)]['data']['time_completed'] = timestamp

        # decide on node status if 'node_status' not provided
        if not node_status:
            complete = objects_are_complete(object_list)
            nodes[int(node_index)]['data']['status'] = get_step_status(object_list) if complete else 'working'
            nodes[int(node_index)]['data']['time_completed'] = timestamp if complete else None
            
        # update current edge if not at flowrun start
        if int(node_index) != 0:
            edge_index = get_edge_by_target(target=nodes[int(node_index)]['id'])['index']
            edges[edge_index]['animated'] = True if nodes[int(node_index)]['data']['status'] == 'working' else False
            edges[edge_index]['style'] = {'stroke': "#60a5fa"} if nodes[int(node_index)]['data']['status'] == 'working' else None

    # added messages to logs
    if message:

        # loop through multiple messages if passed:
        for msg in message.split(','):
            
            # check for empty string
            if msg and len(msg) > 0:

                # update current logs
                logs.append({
                    'timestamp': timestamp,
                    'message': msg,
                    'step': nodes[int(node_index)]['id'] if node_index else logs[-1]['step']
                })

                # sort new logs
                logs = sorted(logs, key=lambda l: (int(l['step'])))


    # save updates
    flowrun.nodes = nodes
    flowrun.edges = edges
    flowrun.logs = logs
    flowrun.save()

    # signals.py should pickup this `update()` event and 
    # execute the run_next() instance of flowr.py

    # return updated flowrun
    return flowrun