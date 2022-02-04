from ..models import *
from .alerts import *
import re, uuid



def automation(automation_id, scan_or_test_id):
    automation = Automation.objects.get(id=automation_id)
    expressions = automation.expressions
    exp_list = []
    actions = automation.actions
    act_list = []

    try:
        scan = Scan.objects.get(id=scan_or_test_id)
    except:
        try:
            test = Test.objects.get(id=scan_or_test_id)
        except:
            return False


    for expression in expressions:
        if '>=' in expression['operator']:
            operator = ' >= '
        else:
            operator = ' <= '
        
        if 'and' in expression['joiner']:
            joiner = ' and '
        elif 'or' in expression['joiner']:
            joiner = ' or '
        else:
            joiner = ''
        
        if 'test_score' in expression['data_type']:
            data_type = 'float(test.score)'
        elif 'current_average' in expression['data_type']:
            data_type = 'float(test.lighthouse_delta["current_average"])'
        elif 'seo_delta' in expression['data_type']:
            data_type = 'float(test.lighthouse_delta["seo_delta"])'
        elif 'best_practices_delta' in expression['data_type']:
            data_type = 'float(test.lighthouse_delta["best_practices_delta"])'
        elif 'performance_delta' in expression['data_type']:
            data_type = 'float(test.lighthouse_delta["performance_delta"])'
        elif 'images_score' in expression['data_type']:
            data_type = 'float(test.images_delta["average_score"])'
        elif 'logs' in expression['data_type']:
            data_type = 'len(scan.logs)'
        elif 'health' in expression['data_type']:
            data_type = 'float(scan.lighthouse["scores"]["average"])'
        

        value = str(float(re.search(r'\d+', str(expression['value'])).group()))
        exp = f'{joiner}{data_type}{operator}{value}'
        exp_list.append(exp)


    for action in actions:

        if 'slack' in action['action_type']:
            action_type = f"\n  print('sending slack alert')\
                \n  automation_slack(automation_id='{str(automation.id)}', \
                scan_or_test_id='{str(scan_or_test_id)}')"
        
        if 'webhook' in action['action_type']:
            action_type = f"\n  print('sending webhook alert')\
                \n  automation_webhook(request_type='{action['request']}', \
                request_url='{action['url']}', request_data='{action['json']}', \
                automation_id='{str(automation.id)}', \
                scan_or_test_id='{str(scan_or_test_id)}')"
        
        if 'email' in action['action_type']:
            action_type = f"\n  print('sending email alert')\
                \n  automation_email(email='{action['email']}',\
                automation_id='{str(automation.id)}', \
                scan_or_test_id='{str(scan_or_test_id)}')"
        
        if 'phone' in action['action_type']:
            action_type = f"\n  print('sending phone alert')\
                \n  automation_phone(phone_number='{action['phone']}', \
                automation_id='{str(automation.id)}', \
                scan_or_test_id='{str(scan_or_test_id)}')"

        act = f'{action_type}'
        act_list.append(act)


    exp_string = ' '.join(exp_list)
    act_string = ''.join(act_list)

    automation_logic = f'if {exp_string}:{act_string}'
    exec(automation_logic)

    return True


        




        


        
        