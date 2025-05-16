from ..models import * 
from .alerter import Alerter
from ..tasks import (
    create_caserun_bg, create_report_bg,
    create_scan_bg, create_test_bg, 
    create_issue_bg,
    send_phone_bg, send_email_bg, 
    send_slack_bg, send_webhook_bg
)
from cursion import settings
from datetime import datetime, timezone
import time, uuid, json, boto3, os, requests, uuid, random






class Flowr():
    """ 
    Executes a `FlowRun` based on the state of 
    the `FlowRun` instance.

    Expects: {
        'flowrun_id' : str,
    }

    - Use `Flowr.run_next()` to run next step in `FlowRun`

    Returns -> Flow instance
    """




    def __init__(self, flowrun_id: str=None) -> object:
        
        # retrieve flowrun
        self.flowrun_id = flowrun_id
        self.flowrun = FlowRun.objects.get(id=flowrun_id)

        # constants for tasks that require 'object_id'
        self.alert_types = [
            'webhook', 'email', 'phone', 'slack', 'report', 'issue'
        ]



    
    def build_timestamp(self) -> object:
        # build timestamp
        return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')




    def get_timestamp(self, timestamp: str=None) -> object:
        """ 
        Formats the 'timestamp' if not None

        Expects: {
            timestamp: str
        }

        Returns: datetime object
        """

        # format for timestamp
        f = '%Y-%m-%d %H:%M:%S.%f'
        
        if timestamp:
            # clean timestamp str
            clean_str = timestamp.replace('T', ' ').replace('Z', '')
            # format date str as datetime obj
            return datetime.strptime(clean_str, f)

        # return None if no timestamp
        return None




    def get_current_step(self) -> dict:
        """ 
        Finds the most recently completed step

        Expects: None

        Returns: {
            'index' : int,
            'node'  : dict
        } 
        """

        # copy all "completed" self.flowrun.nodes
        nodes = [
            node for node in self.flowrun.nodes \
            if (node['data']['time_completed'] and not node['data']['finalized'])
        ]

        # sort nodes/steps by time_completed
        sorted_nodes = sorted(
            nodes, 
            key=lambda x: self.get_timestamp(x['data']['time_completed']),
            reverse=True
        )

        # get current_node
        current_node = sorted_nodes[0] if len(sorted_nodes) > 0 else None

        # get index of current_node
        index = 0
        if current_node:
            for node in self.flowrun.nodes:
                if current_node['id'] == node['id']:
                    break
                index+=1

        # return data
        data = {
            'index': index,
            'node': current_node
        }
        return data
    



    def get_last_node_id(self) -> str:
        """ 
        Sorts the nodes by time_completed 
        and largets ID.

        Expects: None

        Returns: ID <str>
        """
        # copy all "completed" self.flowrun.nodes
        nodes = [
            node for node in self.flowrun.nodes if (node['data']['time_completed'])
        ]

        # sort nodes/steps by decending int(id)
        sorted_nodes = sorted(
            nodes, 
            key=lambda x: int(x['data']['id']),
            reverse=True
        )

        # return first node in sorted nodes
        return sorted_nodes[0]['data']['id']




    def get_edge_by_target(self, target: str=None) -> dict:
        """ 
        Retrieves the self.flowrun.edge[] that matched the 
        passed 'target' id

        Expects: {
            'target': str
        }

        Returns: {
            'index': str,
            'edge': dict
        }
        """

        # find target
        index = 0
        for e in self.flowrun.edges:
            if e['target'] == target:
                return {
                    'index': index,
                    'edge': e
                }
            index+=1
        return {'index': None, 'edge': None}


    

    def get_edges_by_source(self, source: str=None) -> dict:
        """ 
        Retrieves the self.flowrun.edges[] that matched the 
        passed 'source' id

        Expects: {
            'source': str
        }

        Returns: [{
            'index': str,
            'edge': dict
        },]
        """

        # find 
        index = 0
        edges = []
        for e in self.flowrun.edges:
            if e['source'] == source:
                edges.append({
                    'index': index,
                    'edge': e
                })
            index+=1
        return edges




    def get_node_by_id(self, id: str=None) -> dict:
        """ 
        Retrieves the self.flowrun.node[] that matched the 
        passed 'id'

        Expects: {
            'id': str
        }

        Returns: {
            'index': str,
            'node': dict
        }
        """

        # find node by id
        index = 0
        for n in self.flowrun.nodes:
            if n['id'] == id:
                return {
                    'index': index,
                    'node': n
                }
            index+=1
        return {'index': None, 'node': None}


    
   
    def objects_are_complete(self, object_list: list=[]) -> bool:
        """ 
        Iterates through the object_list of a given node
        and returns True if all object.status != 'working'

        Expects: {
            'object_list': list
        }

        Returns: bool
        """
        if len(object_list) == 0:
            return True
        for obj in object_list:
            if obj['status'] == 'working':
                return False
        return True




    def check_all_working_nodes(self, ignore_ids: list=[]) -> None:
        """ 
        Check all objs.time_complete for each working node.
        if node is `working` and all obj.time_complete 
        are not None: update node & edge with status.'passed'

        Expects: 
            "ignore_ids": list of node.ids to ignore

        Returns: None
        """
        # get fresh flowrun obj
        flowrun = FlowRun.objects.get(id=self.flowrun_id)

        # copy flowrun.nodes & flowrun.edges
        nodes = flowrun.nodes
        edges = flowrun.edges

        # set index 
        i = 0       

        # loop through all nodes
        for node in flowrun.nodes:
            if node['data']['status'] == 'working' and node['id'] not in ignore_ids:

                # loop through each "working" obj
                if node['data']['objects']:

                    # set defaults
                    status = 'passed'

                    for obj in node['data']['objects']:
                        if obj['status'] == 'working':

                            # catch all objs that have no id yet (i.e. `Test` objs)
                            if obj['id'] is None:
                                status = 'working'
                                continue

                            # get object using Alerter()
                            o = Alerter(
                                object_id=obj['id'],
                                task_type=node['data']['task_type']
                            ).get_object()

                            # check time_complete
                            if o is not None:
                                try:
                                    if o.time_completed is None:
                                        status = 'working'
                                except Exception as e:
                                    print(e)
                                    pass
            
                    # update node if changed
                    if status != 'working':

                        # update node
                        j = 0
                        final_status = status
                        for obj in nodes[i]['data'].get('objects', []):
                            
                            # get current obj status
                            _status = nodes[i]['data']['objects'][j]['status']
                            
                            # update obj status 
                            nodes[i]['data']['objects'][j]['status'] = _status if _status != 'working' else 'passed'
                            
                            # update final_status if obj failed
                            if _status == 'failed':
                                final_status = 'failed'
                            j += 1

                        # add final node status
                        nodes[i]['data']['status'] = final_status
                        nodes[i]['data']['time_completed'] = self.build_timestamp()
                        
                        # update edge
                        edge = self.get_edge_by_target(nodes[i]['data']['id'])
                        if edge['edge']:
                            edges[edge['index']]['animated'] = True if final_status == 'working' else False
                            edges[edge['index']]['style'] = {'stroke': "#60a5fa"} if final_status == 'working' else None
            
            # increment
            i += 1

        # update flowrun
        flowrun.nodes = nodes
        flowrun.edges = edges
        flowrun.save()

        return None




    def finalize_node(self, index: int=None) -> None:
        """ 
        Updates the node matching the 'index' with 
        'finalized' = True, then updates self.flowrun

        Expects: {
            'index': int
        }

        Returns: None
        """

        # copy and update 
        nodes = self.flowrun.nodes
        nodes[int(index)]['data']['finalized'] = True

        # save to DB
        self.flowrun.nodes = nodes
        self.flowrun.save()
        return None




    def complete_flowrun(self, current_data: dict=None) -> None:
        """ 
        Checks for run completion and updates final 
        run status.

        Expects: {
            'current_data': dict
        }

        Returns: `FlowRun` object
        """
        
        # defaults
        status  = 'passed'
        nodes   = self.flowrun.nodes
        logs    = self.flowrun.logs

        # mark current current node as finalized 
        # and update status
        if current_data:
            index           = current_data['index']
            current_status  = nodes[int(index)]['data']['status']
            
            nodes[int(index)]['data']['finalized'] = True
            nodes[int(index)]['data']['status'] = 'passed' if current_status == 'working' else current_status

        # check all nodes statuses
        for node in FlowRun.objects.get(id=self.flowrun_id).nodes:
            
            # check for non-current 'working' nodes
            if node['data']['status'] == 'working':
                if current_data:
                    if node['id'] != current_data['node']['id']:
                        return self.flowrun
                else:
                    return self.flowrun
            
            # check for any 'failed' nodes
            if node['data']['status'] == 'failed':
                status = 'failed'
            
        # check for current node failure
        if current_data:
            current_status = nodes[int(current_data['index'])]['data']['status']
            status = current_status if current_status == 'failed' else status
        
        # build log data
        logs.append({
            'timestamp' : self.build_timestamp(),
            'step'      : current_data['node']['id'] if current_data else self.get_last_node_id(),
            'message'   : (
                f'flowrun completed with status: {"✅ PASSED" if status == "passed" else "❌ FAILED"}'
            ),
        })
        # sort logs
        logs = sorted(logs, key=lambda l: int(l['step']),)

        # update flowrun
        self.flowrun.time_completed = self.build_timestamp()
        self.flowrun.status         = status
        self.flowrun.logs           = logs
        self.flowrun.nodes          = nodes
        self.flowrun.save()

        # run alert if requested
        alert_id = current_data['node']['data'].get('alert_id') if current_data else None
        if alert_id:
            Alerter(alert_id=alert_id, object_id=str(self.flowrun_id)).run_alert()

        # return flowrun
        return self.flowrun




    def run_next(self) -> None:
        """ 
        Checks for the next step and executes 
        if current step has completed.

        Expects: None

        Returns: `FlowRun` object
        """

        # check if flowrun is complete
        if self.flowrun.time_completed:
            # return early 
            print('flowrun is complete')
            return self.flowrun


        # get last completed node or None
        current_data = self.get_current_step()


        # check if FlowRun is just starting
        if current_data['node'] is None and \
            self.flowrun.nodes[0]['data']['status'] == 'queued':
            
            # create step_data for first step
            step_data = {
                'index': 0,
                'node': self.flowrun.nodes[0]
            }
            
            # create alert obj if needed for first job
            alert_obj = {
                'parent': str(self.flowrun_id),
                'id': str(self.flowrun_id),
                'status': 'working'
            }
            objs = [alert_obj,] if step_data['node']['data']['task_type'] in self.alert_types else []

            # catch empty task_type
            if not step_data['node']['data']['task_type']:
                self.complete_flowrun(current_data=step_data)
                return self.flowrun

            # run first step
            print('running first step')
            self.execute_step(step_data=step_data, objects=objs)
            return self.flowrun


        # catch updates without a current_node 
        if current_data['node'] is None:
            return self.flowrun


        # check for node conditions given not 'queued' or 'working'
        if current_data['node']['data']['conditions'] and \
            (current_data['node']['data']['status'] != 'failed' or not self.flowrun.configs.get('end_on_fail')):
            
            # starting conditons buliding & execution
            print('building conditons')

            # finialize node
            self.finalize_node(index=current_data['index'])

            # set defaults
            true_outcomes       = []
            false_outcomes      = []
            run_as_cumulative   = False
            false_child_ran     = False
            true_child_ran      = False

            # iterate through the objects and run conditions for each
            for obj_data in current_data['node']['data'].get('objects', []):
            
                # get obj using Alerter
                obj = Alerter(
                    object_id=obj_data['id'],
                    task_type=current_data['node']['data']['task_type']
                ).get_object()
                
                # build and execute conditions
                conditions = Alerter(
                    expressions=current_data['node']['data']['conditions']
                ).build_expressions()
                
                # evaluate conditons
                outcome = eval(f'True if ({conditions}) else False')

                # create new fake parent ID
                parentID = uuid.uuid4()
                
                # sorting
                if outcome == True:
                    true_outcomes.append({
                        'parent'    : str(parentID),
                        'id'        : obj_data['id'],
                        'status'    : 'working'
                    })
                if outcome == False:
                    false_outcomes.append({
                        'parent'    : str(parentID),
                        'id'        : obj_data['id'],
                        'status'    : 'working'
                    })

            # get child edges
            edges = self.get_edges_by_source(current_data['node']['id'])
            children = [self.get_node_by_id(e['edge']['target']) for e in edges]
            
            # establish true/false child nodes
            true_child = None
            false_child = None
            for c in children:
                if c['node']['data']['start_if'] == True:
                    true_child = c
                if c['node']['data']['start_if'] == False:
                    false_child = c

            # run true_child if true_outcomes exists
            if len(true_outcomes) > 0:
                print('RUNNING TRUE CHILD')
                true_task = true_child['node']['data']['task_type'] if true_child else None
                # sleeping random for DB 
                time.sleep(random.uniform(1, 5))
                self.execute_step(
                    step_data=true_child, 
                    objects=true_outcomes if true_task in self.alert_types else []
                )
            
            # run false_child if false_outcomes exists
            if len(false_outcomes) > 0:
                print('RUNNING FALSE CHILD')
                false_task = false_child['node']['data']['task_type'] if false_child else None
                # sleeping random for DB 
                time.sleep(random.uniform(1, 5))
                self.execute_step(
                    step_data=false_child, 
                    objects=false_outcomes if false_task in self.alert_types else []
                )

            # ending section
            return self.flowrun

        
        # get and execute next step if current_node status is 'passed'
        if current_data['node']['data']['status'] == 'passed':

            # finialize node
            self.finalize_node(index=current_data['index'])
            
            # get child edges
            edges = self.get_edges_by_source(current_data['node']['id'])
            children = [self.get_node_by_id(e['edge']['target']) for e in edges]

            # children length should be <= 1 since
            # current_node.conditions == None
            if len(children) == 1:
                if children[0] is not None:
                    next_step = children[0]
                    if next_step['node']['data']['task_type']:
                        print('running next step after "PASSED" non-conditional step')
                        objs = []
                        if next_step['node']['data']['task_type'] in self.alert_types:
                            objs = current_data['node']['data'].get('objects', [])
                        self.execute_step(step_data=next_step, objects=objs)
                        return self.flowrun

            # if no children, end flowrun and update logs
            self.complete_flowrun(current_data=current_data)
            
            # return flowrun
            return self.flowrun
            
        
        # mark flowrun as `complete` and `failed` if 
        # current_node status is 'failed' & 'end_on_fail' is True
        if current_data['node']['data']['status'] == 'failed':

            # finialize node
            self.finalize_node(index=current_data['index'])

            # end flowrun if requested
            if self.flowrun.configs.get('end_on_fail', True):

                print('--- ending run early due to failure ---')
                self.complete_flowrun(current_data=current_data)

                # return flowrun
                return self.flowrun
                    
            # get child edges
            edges = self.get_edges_by_source(current_data['node']['id'])
            children = [self.get_node_by_id(e['edge']['target']) for e in edges]

            # children length should be <= 1 since
            # current_node.conditions == None
            if len(children) == 1:
                if children[0] is not None:
                    next_step = children[0]
                    # check for data in next_step
                    if next_step['node']['data']['task_type']:
                        print('running next step after "FAILED" non-conditional step')
                        objs = []
                        if next_step['node']['data']['task_type'] in self.alert_types:
                            objs = current_data['node']['data'].get('objects', [])
                        self.execute_step(step_data=next_step, objects=objs)
                        return self.flowrun

            # if no children, end flowrun as 'failed' and update logs
            self.complete_flowrun(current_data=current_data)

            # return flowrun
            return self.flowrun


        

    def execute_step(self, step_data: dict=None, objects: list=None) -> None:
        """ 
        Executes the `step` with associated job.

        Expects: {
            'step_data': {
                'index': str,
                'node' : dict
            },
            'objects': list
        }
        
        Returns: None
        """

        if step_data is None:
            print('no step_data provided - attempting to end run...')
            self.complete_flowrun(current_data=step_data)
            return 

        if not step_data['node']['data']['task_type']:
            print('no task_type provided - attempting to end run...')
            self.complete_flowrun(current_data=step_data)
            return 

        # get step/node data & task_type
        node_data   = step_data['node']['data']
        task_type   = node_data['task_type']
        node_index  = step_data['index']
        parent_data = None if node_index == 0 else self.get_node_by_id(node_data['parentId'])
        message     = (
            f'starting job ID: {node_data["id"]} ' + 
            f'| job type is [ {task_type.upper()} ]'
        )

        # update self.flowrun logs, nodes, & edges
        self.flowrun    = FlowRun.objects.get(id=self.flowrun_id)
        nodes           = self.flowrun.nodes
        edges           = self.flowrun.edges
        logs            = self.flowrun.logs

        # update current node
        nodes[step_data['index']]['data']['status']         = 'working' 
        nodes[step_data['index']]['data']['time_started']   = self.build_timestamp()

        # update node objects only if task_type is not 'issue' or 'report'
        nodes[step_data['index']]['data']['objects'] = objects if (task_type != 'issue' and task_type != 'report') else []

        # update current edge if not first step
        if step_data['index'] != 0:
            edge_index = self.get_edge_by_target(target=node_data['id'])['index']
            edges[edge_index]['animated'] = True
            edges[edge_index]['style'] = {'stroke': "#60a5fa"}

        # update current logs
        logs.append({
            'timestamp' : self.build_timestamp(),
            'message'   : message,
            'step'      : node_data['id']
        })

        # sort logs
        logs = sorted(logs, key=lambda l: int(l['step']),)
        
        # save updates
        self.flowrun.nodes  = nodes
        self.flowrun.edges  = edges
        self.flowrun.logs   = logs
        self.flowrun.save()

        # build common data
        scope       = 'account'
        configs     = node_data['configs']
        flowrun_id  = str(self.flowrun.id)
        account_id  = str(self.flowrun.account.id)
        types       = node_data.get('type')
        resources   = [{
            'str'   : self.flowrun.site.site_url,
            'id'    : str(self.flowrun.site.id),
            'type'  : 'site'
        },]
    

        # create new scan
        if task_type == 'scan':
            create_scan_bg.delay(
                scope         = scope,
                resources     = resources,
                account_id    = account_id,
                type          = types,
                configs       = configs,
                flowrun_id    = flowrun_id,
                node_index    = node_index
            )
        
        # create new test
        if task_type == 'test': 
            create_test_bg.delay(
                scope         = scope,
                resources     = resources,
                account_id    = account_id,
                type          = types,
                configs       = configs,
                threshold     = node_data['threshold'],
                flowrun_id    = flowrun_id,
                node_index    = node_index
            )
        
        # create new caserun
        if task_type == 'case':
            create_caserun_bg.delay(
                scope         = scope,
                resources     = resources,
                account_id    = account_id,
                case_id       = node_data['case_id'],
                updates       = node_data['updates'],
                configs       = configs,
                flowrun_id    = flowrun_id,
                node_index    = node_index
            )

        # create new issue
        if task_type == 'issue':
            create_issue_bg.delay(
                account_id    = account_id,
                objects       = objects,
                title         = node_data['title'],
                details       = node_data['details'],
                generate      = node_data['generate'],
                flowrun_id    = flowrun_id,
                node_index    = node_index
            )
        
        # create new report
        if task_type == 'report':
            create_report_bg.delay(
                scope         = scope,
                resources     = resources,
                account_id    = account_id,
                configs       = configs,
                flowrun_id    = flowrun_id,
                node_index    = node_index
            )

        # send phone notification
        if task_type == 'phone':
            send_phone_bg.delay(
                account_id    = account_id,
                objects       = objects,
                phone_number  = node_data['phone_number'],
                body          = node_data['message'],
                flowrun_id    = flowrun_id,
                node_index    = node_index
            )
        
        # send slack notification
        if task_type == 'slack':
            send_slack_bg.delay(
                account_id    = account_id,
                objects       = objects,
                body          = node_data['message'],
                flowrun_id    = flowrun_id,
                node_index    = node_index
            )

        # send email notification
        if task_type == 'email':
            send_email_bg.delay(
                account_id    = account_id,
                objects       = objects,
                message_obj   = {
                    'plain_text'  : True,
                    'email'       : node_data['email'],
                    'subject'     : node_data['subject'],
                    'content'     : node_data['message']
                },
                flowrun_id    = flowrun_id,
                node_index    = node_index
            )

        # send webhook notification
        if task_type == 'webhook':
            send_webhook_bg.delay(
                account_id    = account_id,
                objects       = objects,
                request_type  = node_data['request_type'],
                url           = node_data['uri'],
                headers       = node_data['headers'],
                payload       = node_data['payload'],
                flowrun_id    = flowrun_id,
                node_index    = node_index
            )


        # check all objs.time_complete for each "working" node.
        # if node is `working` and all obj.time_complete 
        # are not None: update node with status.'passed'
        self.check_all_working_nodes(ignore_ids=[node_data['id']])


        # returning 
        return None





