from ..models import *
from .alerts import *
import re, uuid



def automation(automation_id, object_id):
    automation = Automation.objects.get(id=automation_id)
    schedule = automation.schedule
    expressions = automation.expressions
    exp_list = []
    actions = automation.actions
    act_list = []
    scan = None
    test = None
    report = None
    use_exp = True

    if schedule.task_type == 'scan':
        try:
            scan = Scan.objects.get(id=object_id)
        except:
            return False

    elif schedule.task_type == 'test':
        try:
            test = Test.objects.get(id=object_id)
        except:
            return False
    
    elif schedule.task_type == 'report':
        try:
            report = Report.objects.get(id=object_id)
            use_exp = False
        except:
            return False
    else:
        return False      
    

                

    if use_exp:

        for expression in expressions:

            exp = None
            data_type = None
            value = str(float(re.search(r'\d+', str(expression['value'])).group()))

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
            
            # lighthouse test data
            elif 'current_lighthouse_average' in expression['data_type']:
                data_type = 'float(test.lighthouse_delta["scores"]["current_average"])'
            elif 'seo_delta' in expression['data_type']:
                data_type = 'float(test.lighthouse_delta["scores"]["seo_delta"])'
            elif 'pwa_delta' in expression['data_type']:
                data_type = 'float(test.lighthouse_delta["scores"]["pwa_delta"])'
            elif 'crux_delta' in expression['data_type']:
                data_type = 'float(test.lighthouse_delta["scores"]["crux_delta"])'
            elif 'best_practices_delta' in expression['data_type']:
                data_type = 'float(test.lighthouse_delta["scores"]["best_practices_delta"])'
            elif 'performance_delta' in expression['data_type']:
                data_type = 'float(test.lighthouse_delta["scores"]["performance_delta"])'
            elif 'accessibility_delta' in expression['data_type']:
                data_type = 'float(test.lighthouse_delta["scores"]["accessibility_delta"])'
            # lighthouse scan data
            elif 'lighthouse_average' in expression['data_type']:
                data_type = 'float(scan.lighthouse["scores"]["average"])'
            elif 'seo' in expression['data_type']:
                data_type = 'float(scan.lighthouse["scores"]["seo"])'
            elif 'pwa' in expression['data_type']:
                data_type = 'float(scan.lighthouse["scores"]["pwa"])'
            elif 'crux' in expression['data_type']:
                data_type = 'float(scan.lighthouse["scores"]["crux"])'
            elif 'best_practices' in expression['data_type']:
                data_type = 'float(scan.lighthouse["scores"]["best_practices"])'
            elif 'performance' in expression['data_type']:
                data_type = 'float(scan.lighthouse["scores"]["performance"])'
            elif 'accessibility' in expression['data_type']:
                data_type = 'float(scan.lighthouse["scores"]["accessibility"])'

            # yellowlab test data
            elif 'current_yellowlab_average' in expression['data_type']:
                data_type = 'float(test.yellowlab_delta["scores"]["current_average"])'
            elif 'pageWeight_delta' in expression['data_type']:
                data_type = 'float(test.yellowlab_delta["scores"]["pageWeight_delta"])'
            elif 'requests_delta' in expression['data_type']:
                data_type = 'float(test.yellowlab_delta["scores"]["requests_delta"])'
            elif 'domComplexity_delta' in expression['data_type']:
                data_type = 'float(test.yellowlab_delta["scores"]["domComplexity_delta"])'
            elif 'javascriptComplexity_delta' in expression['data_type']:
                data_type = 'float(test.yellowlab_delta["scores"]["javascriptComplexity_delta"])'
            elif 'badJavascript_delta' in expression['data_type']:
                data_type = 'float(test.yellowlab_delta["scores"]["badJavascript_delta"])'
            elif 'jQuery_delta' in expression['data_type']:
                data_type = 'float(test.yellowlab_delta["scores"]["jQuery_delta"])'
            elif 'cssComplexity_delta' in expression['data_type']:
                data_type = 'float(test.yellowlab_delta["scores"]["cssComplexity_delta"])'
            elif 'badCSS_delta' in expression['data_type']:
                data_type = 'float(test.yellowlab_delta["scores"]["badCSS_delta"])'
            elif 'fonts_delta' in expression['data_type']:
                data_type = 'float(test.yellowlab_delta["scores"]["fonts_delta"])'
            elif 'serverConfig_delta' in expression['data_type']:
                data_type = 'float(test.yellowlab_delta["scores"]["serverConfig_delta"])'
            # yellowlab scan data
            elif 'yellowlab_average' in expression['data_type']:
                data_type = 'float(scan.yellowlab["scores"]["globalScore"])'
            elif 'pageWeight' in expression['data_type']:
                data_type = 'float(scan.yellowlab["scores"]["pageWeight"])'
            elif 'requests' in expression['data_type']:
                data_type = 'float(scan.yellowlab["scores"]["requests"])'
            elif 'domComplexity' in expression['data_type']:
                data_type = 'float(scan.yellowlab["scores"]["domComplexity"])'
            elif 'javascriptComplexity' in expression['data_type']:
                data_type = 'float(scan.yellowlab["scores"]["javascriptComplexity"])'
            elif 'badJavascript' in expression['data_type']:
                data_type = 'float(scan.yellowlab["scores"]["badJavascript"])'
            elif 'jQuery' in expression['data_type']:
                data_type = 'float(scan.yellowlab["scores"]["jQuery"])'
            elif 'cssComplexity' in expression['data_type']:
                data_type = 'float(scan.yellowlab["scores"]["cssComplexity"])'
            elif 'badCSS' in expression['data_type']:
                data_type = 'float(scan.yellowlab["scores"]["badCSS"])'
            elif 'fonts' in expression['data_type']:
                data_type = 'float(scan.yellowlab["scores"]["fonts"])'
            elif 'serverConfig' in expression['data_type']:
                data_type = 'float(scan.yellowlab["scores"]["serverConfig"])'
            
            
            elif 'logs' in expression['data_type']:
                data_type = 'len(scan.logs)'
            
            elif 'current_health' in expression['data_type']:
                data_type = '((float(test.lighthouse_delta["scores"]["current_average"]) + float(test.yellowlab_delta["scores"]["current_average"]))/2)'

            elif 'health' in expression['data_type']:
                data_type = '((float(scan.lighthouse["scores"]["average"]) + float(scan.yellowlab["scores"]["globalScore"]))/2)'

            elif 'avg_image_score' in expression['data_type']:
                data_type = 'float(test.images_delta["average_score"])'

            elif 'image_scores' in expression['data_type']:
                data_type = '[i["score"] for i in test.images_delta["images"]]' 
                exp = f'{joiner}any(i{operator}{value} for i in {data_type})'
            
            if exp is None:
                exp = f'{joiner}{data_type}{operator}{value}'
           
            exp_list.append(exp)



    for action in actions:

        if 'slack' in action['action_type']:
            action_type = f"\n  print('sending slack alert')\
                \n  automation_slack(automation_id='{str(automation.id)}', \
                object_id='{str(object_id)}')"
        
        if 'webhook' in action['action_type']:
            action_type = f"\n  print('sending webhook alert')\
                \n  automation_webhook(request_type='{action['request']}', \
                request_url='{action['url']}', request_data='{action['json']}', \
                automation_id='{str(automation.id)}', \
                object_id='{str(object_id)}')"
        
        if 'email' in action['action_type']:
            action_type = f"\n  print('sending email alert')\
                \n  automation_email(email='{action['email']}',\
                automation_id='{str(automation.id)}', \
                object_id='{str(object_id)}')"
            
            if report:
                action_type = f"\n  print('sending report email')\
                    \n  automation_report_email(email='{action['email']}',\
                    automation_id='{str(automation.id)}', \
                    object_id='{str(object_id)}')"
        
        if 'phone' in action['action_type']:
            action_type = f"\n  print('sending phone alert')\
                \n  automation_phone(phone_number='{action['phone']}', \
                automation_id='{str(automation.id)}', \
                object_id='{str(object_id)}')"

        act = f'{action_type}'
        act_list.append(act)


    exp_string = ' '.join(exp_list)
    act_string = ''.join(act_list)

    if not use_exp:
        exp_string = '1 == 1'

    automation_logic = f'if {exp_string}:{act_string}'
    print(automation_logic)
    exec(automation_logic)

    return True


        




        


        
        