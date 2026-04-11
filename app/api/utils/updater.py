from ..models import *
from django.utils import timezone
from django.db import transaction
from cursion import settings






def update_flowrun(**kwargs) -> object:
    """ 
    Updates the `FlowRun`, matching the 'flowrun_id',
    with the **kwargs data

    Args:
        'flowrun_id'   : str
        'node_index'   : int or str,
        'messsage'     : str,
        'node_status'  : str,
        'objects'      : list of dicts
    
    Returns:
        `FlowRun` obj
    """
    
    # get passed kwargs
    flowrun_id = kwargs.get('flowrun_id')
    node_index = kwargs.get('node_index')
    node_status = kwargs.get('node_status')
    message = kwargs.get('message')
    objects = kwargs.get('objects')

    with transaction.atomic():
        # lock the row so concurrent workers cannot read-modify-write
        # stale copies of nodes/edges/logs.
        flowrun = FlowRun.objects.select_for_update().get(id=flowrun_id)

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

        # object helpers
        def _clean_str(value):
            return str(value) if value is not None else None

        def _normalize_object(obj):
            normalized = dict(obj or {})
            normalized['parent'] = _clean_str(normalized.get('parent'))
            normalized['id'] = _clean_str(normalized.get('id'))
            normalized['source_id'] = _clean_str(
                normalized.get('source_id', normalized.get('id'))
            )
            normalized['track_id'] = _clean_str(normalized.get('track_id'))

            # Transitional defaults while older callers still send legacy shape.
            if normalized['track_id'] is None:
                if normalized['id'] is not None:
                    normalized['track_id'] = normalized['id']
                elif normalized['source_id'] is not None:
                    normalized['track_id'] = f'source:{normalized["source_id"]}'
                elif normalized['parent'] is not None:
                    normalized['track_id'] = f'legacy:{normalized["parent"]}'

            return normalized

        def _same_object(a, b):
            # Preferred identity key.
            if a.get('track_id') and b.get('track_id'):
                return a['track_id'] == b['track_id']
            # Transitional fallback for legacy payloads.
            if a.get('id') and b.get('id'):
                return a['id'] == b['id']
            # Final legacy fallback.
            return a.get('parent') == b.get('parent')

        # update object_list
        def add_or_update_objects(object_list, objects):
            updated = [_normalize_object(o) for o in (object_list or [])]
            for raw_obj in (objects or []):
                incoming = _normalize_object(raw_obj)
                exists = False
                i = 0
                for existing in updated:
                    if _same_object(existing, incoming):
                        merged = dict(existing)
                        merged.update(incoming)

                        # Preserve resolved ids when incoming payload is still pending.
                        if incoming.get('id') is None and existing.get('id') is not None:
                            merged['id'] = existing.get('id')
                            # Keep the resolved source identity when incoming payload
                            # is only a placeholder update.
                            if existing.get('source_id') is not None:
                                merged['source_id'] = existing.get('source_id')
                        if incoming.get('source_id') is None and existing.get('source_id') is not None:
                            merged['source_id'] = existing.get('source_id')
                        if incoming.get('track_id') is None and existing.get('track_id') is not None:
                            merged['track_id'] = existing.get('track_id')

                        updated[i] = merged
                        exists = True
                        break
                    i += 1

                if not exists:
                    updated.append(incoming)

            return updated

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

        # save updates while holding the row lock
        flowrun.nodes = nodes
        flowrun.edges = edges
        flowrun.logs = logs
        flowrun.save()

        # run_next() should execute for updater-driven changes.
        # keep this explicit so progression does not rely solely on signal timing.
        if settings.LOCATION == 'us':
            flowrun_id_str = str(flowrun.id)

            def _run_next():
                try:
                    from .flowr import Flowr
                    Flowr(flowrun_id=flowrun_id_str).run_next()
                except Exception as e:
                    print(f'[update_flowrun] run_next trigger error: {e}')

            transaction.on_commit(_run_next)

        # return updated flowrun
        return flowrun
