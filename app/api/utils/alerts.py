from django.core.mail import send_mail, send_mass_mail
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from datetime import date
import os, operator, json, requests, uuid
from django.utils.html import strip_tags
from django.contrib.auth.models import User
from rest_framework.response import Response
from ..models import *
from twilio.rest import Client
from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, From, To
from scanerr import settings





def create_exp_str(item, automation, is_email=False):

    exp_list = []
    
    for e in automation.expressions:
        if 'test_score' in e['data_type']:
            data_type = 'Test Score:\t'+str(round(item.score, 2))+'\n\t'
        elif 'current_health' in e['data_type']:
            data_type = 'Health:\t'+str((float(item.lighthouse_delta["scores"]["current_average"]) + float(item.yellowlab_delta["scores"]["current_average"])/2))+'\n\t'
        elif 'health' in e['data_type']:
            data_type = 'Health:\t'+str(((float(item.lighthouse["scores"]["average"]) + float(item.yellowlab["scores"]["globalScore"]))/2))+'\n\t'
        # LH test data
        elif 'current_lighthouse_average' in e['data_type']:
            data_type = 'Lighthouse Average:\t'+str(item.lighthouse_delta["scores"]["current_average"])+'\n\t'
        elif 'seo_delta' in e['data_type']:
            data_type = 'SEO Delta:\t'+str(item.lighthouse_delta["scores"]["seo_delta"])+'\n\t'
        elif 'pwa_delta' in e['data_type']:
            data_type = 'PWA Delta:\t'+str(item.lighthouse_delta["scores"]["pwa_delta"])+'\n\t'
        elif 'crux_delta' in e['data_type']:
            data_type = 'CRUX Delta:\t'+str(item.lighthouse_delta["scores"]["crux_delta"])+'\n\t'
        elif 'best_practices_delta' in e['data_type']:
            data_type = 'Best Practices Delta:\t'+str(item.lighthouse_delta["scores"]["best_practices_delta"])+'\n\t'
        elif 'performance_delta' in e['data_type']:
            data_type = 'Performance Delta:\t'+str(item.lighthouse_delta["scores"]["performance_delta"])+'\n\t'
        elif 'accessibility_delta' in e['data_type']:
            data_type = 'Accessibility Delta:\t'+str(item.lighthouse_delta["scores"]["accessibility_delta"])+'\n\t'
        # LH scan data
        elif 'lighthouse_average' in e['data_type']:
            data_type = 'Lighthouse Average:\t'+str(item.lighthouse["scores"]["average"])+'\n\t'
        elif 'seo' in e['data_type']:
            data_type = 'SEO:\t'+str(item.lighthouse["scores"]["seo"])+'\n\t'
        elif 'pwa' in e['data_type']:
            data_type = 'PWA:\t'+str(item.lighthouse["scores"]["pwa"])+'\n\t'
        elif 'crux' in e['data_type']:
            data_type = 'CRUX:\t'+str(item.lighthouse["scores"]["crux"])+'\n\t'
        elif 'best_practices' in e['data_type']:
            data_type = 'Best Practices:\t'+str(item.lighthouse["scores"]["best_practices"])+'\n\t'
        elif 'performance' in e['data_type']:
            data_type = 'Performance:\t'+str(item.lighthouse["scores"]["performance"])+'\n\t'
        elif 'accessibility' in e['data_type']:
            data_type = 'Accessibility:\t'+str(item.lighthouse["scores"]["accessibility"])+'\n\t'
        
        

        # yellowlab test data
        elif 'current_yellowlab_average' in e['data_type']:
            data_type = 'Yellow Lab Avg:\t'+str(item.yellowlab_delta["scores"]["current_average"])+'\n\t'
        elif 'pageWeight_delta' in e['data_type']:
            data_type = 'Page Weight Delta:\t'+str(item.yellowlab_delta["scores"]["pageWeight_delta"])+'\n\t'
        elif 'requests_delta' in e['data_type']:
            data_type = 'Requests Delta:\t'+str(item.yellowlab_delta["scores"]["requests_delta"])+'\n\t'
        elif 'domComplexity_delta' in e['data_type']:
            data_type = 'DOM Complex. Delta:\t'+str(item.yellowlab_delta["scores"]["domComplexity_delta"])+'\n\t'
        elif 'javascriptComplexity_delta' in e['data_type']:
            data_type = 'JS Complex. Delta:\t'+str(item.yellowlab_delta["scores"]["javascriptComplexity_delta"])+'\n\t'
        elif 'badJavascript_delta' in e['data_type']:
            data_type = 'Bad JS Delta:\t'+str(item.yellowlab_delta["scores"]["badJavascript_delta"])+'\n\t'
        elif 'jQuery_delta' in e['data_type']:
            data_type = 'jQuery Delta:\t'+str(item.yellowlab_delta["scores"]["jQuery_delta"])+'\n\t'
        elif 'cssComplexity_delta' in e['data_type']:
            data_type = 'CSS Complex. Delta:\t'+str(item.yellowlab_delta["scores"]["cssComplexity_delta"])+'\n\t'
        elif 'badCSS_delta' in e['data_type']:
            data_type = 'Bad CSS Delta:\t'+str(item.yellowlab_delta["scores"]["badCSS_delta"])+'\n\t'
        elif 'fonts_delta' in e['data_type']:
            data_type = 'Fonts Delta:\t'+str(item.yellowlab_delta["scores"]["fonts_delta"])+'\n\t'
        elif 'serverConfig_delta' in e['data_type']:
            data_type = 'Server Config Delta:\t'+str(item.yellowlab_delta["scores"]["serverConfig_delta"])+'\n\t'

        # yellowlab scan data
        elif 'yellowlab_average' in e['data_type']:
            data_type = 'Yellow Lab Avg:\t'+str(item.yellowlab["scores"]["globalScore"])+'\n\t'
        elif 'pageWeight' in e['data_type']:
            data_type = 'Page Weight:\t'+str(item.yellowlab["scores"]["pageWeight"])+'\n\t'
        elif 'requests' in e['data_type']:
            data_type = 'Requests:\t'+str(item.yellowlab["scores"]["requests"])+'\n\t'
        elif 'domComplexity' in e['data_type']:
            data_type = 'DOM Complex.:\t'+str(item.yellowlab["scores"]["domComplexity"])+'\n\t'
        elif 'javascriptComplexity' in e['data_type']:
            data_type = 'JS Complex.:\t'+str(item.yellowlab["scores"]["javascriptComplexity"])+'\n\t'
        elif 'badJavascript' in e['data_type']:
            data_type = 'Bad JS:\t'+str(item.yellowlab["scores"]["badJavascript"])+'\n\t'
        elif 'jQuery' in e['data_type']:
            data_type = 'jQuery:\t'+str(item.yellowlab["scores"]["jQuery"])+'\n\t'
        elif 'cssComplexity' in e['data_type']:
            data_type = 'CSS Complex.:\t'+str(item.yellowlab["scores"]["cssComplexity"])+'\n\t'
        elif 'badCSS' in e['data_type']:
            data_type = 'Bad CSS:\t'+str(item.yellowlab["scores"]["badCSS"])+'\n\t'
        elif 'fonts' in e['data_type']:
            data_type = 'Fonts:\t'+str(item.yellowlab["scores"]["fonts"])+'\n\t'
        elif 'serverConfig' in e['data_type']:
            data_type = 'Server Config:\t'+str(item.yellowlab["scores"]["serverConfig"])+'\n\t'
        
        elif 'avg_image_score' in e['data_type']:
            data_type = ' Avg Image Score:\t'+str(item.images_delta["average_score"])+'\n\t'
        elif 'image_scores' in e['data_type']:
            data_type = 'List of Image Scores:\t'+str([i["score"] for i in item.images_delta["images"]])+'\n\t' 
        
        elif 'logs' in e['data_type']:
            data_type = 'Error Logs:\t'+str(len(item.logs))+'\n\t'


        elif 'testcase' in e['data_type']:
            status = 'Failed'
            if e['value'] == 'True':
                status = 'Passed'
            data_type = 'Testcase "'+str(item.case.name)+'" --> '+str(status)
        
        
        exp_list.append(data_type)

    if is_email:
        return exp_list

    exp_str = ('\t'+''.join(exp_list))
    return exp_str





def create_json_data(data, obj): 
    json_data = data
    item = obj

    for key in json_data:
        if 'test_score' == json_data[key]:
            json_data[key] = item.score
        elif 'seo_delta' == json_data[key]:
            json_data[key] = item.lighthouse_delta["scores"]["seo_delta"]
        elif 'pwa_delta' == json_data[key]:
            json_data[key] = item.lighthouse_delta["scores"]["pwa_delta"]
        elif 'crux_delta' == json_data[key]:
            json_data[key] = item.lighthouse_delta["scores"]["crux_delta"]
        elif 'best_practices_delta' == json_data[key]:
            json_data[key] = item.lighthouse_delta["scores"]["best_practices_delta"]
        elif 'performance_delta' == json_data[key]:
            json_data[key] = item.lighthouse_delta["scores"]["performance_delta"]
        elif 'accessibility_delta' == json_data[key]:
            json_data[key] = item.lighthouse_delta["scores"]["accessibility_delta"]
        elif 'current_health' == json_data[key]:
            json_data[key] = (float(item.lighthouse_delta["scores"]["average"]) + float(item.yellowlab_delta["scores"]["globalScore"])/2)
        elif 'health' == json_data[key]:
            json_data[key] = (float(item.lighthouse["scores"]["average"]) + float(item.yellowlab["scores"]["globalScore"])/2)
        elif 'logs' == json_data[key]:
            json_data[key] = len(item.logs)
        elif 'current_lighthouse_average' == json_data[key]:
            json_data[key] = item.lighthouse_delta["scores"]["current_average"]
        elif 'current_average' == json_data[key]:
            json_data[key] = item.lighthouse["scores"]["current_average"]
        elif 'seo' == json_data[key]:
            json_data[key] = item.lighthouse["scores"]["seo"]
        elif 'pwa' == json_data[key]:
            json_data[key] = item.lighthouse["scores"]["pwa"]
        elif 'crux' == json_data[key]:
            json_data[key] = item.lighthouse["scores"]["crux"]
        elif 'best_practice' == json_data[key]:
            json_data[key] = item.lighthouse["scores"]["best_practices"]
        elif 'performance' == json_data[key]:
            json_data[key] = item.lighthouse["scores"]["performance"]
        elif 'accessibility' == json_data[key]:
            json_data[key] = item.lighthouse["scores"]["accessibility"]

        elif 'current_yellowlab_average' == json_data[key]:
            json_data[key] = item.yellowlab_delta["scores"]["current_average"]
        elif 'pageWeight_delta' == json_data[key]:
            json_data[key] = item.yellowlab_delta["scores"]["pageWeight_delta"]
        elif 'requests_delta' == json_data[key]:
            json_data[key] = item.yellowlab_delta["scores"]["requests_delta"]
        elif 'domComplexity_delta' == json_data[key]:
            json_data[key] = item.yellowlab_delta["scores"]["domComplexity_delta"]
        elif 'javascriptComplexity_delta' == json_data[key]:
            json_data[key] = item.yellowlab_delta["scores"]["javascriptComplexity_delta"]
        elif 'badJavascript_delta' == json_data[key]:
            json_data[key] = item.yellowlab_delta["scores"]["badJavascript_delta"]
        elif 'jQuery_delta' == json_data[key]:
            json_data[key] = item.yellowlab_delta["scores"]["jQuery_delta"]
        elif 'cssComplexity_delta' == json_data[key]:
            json_data[key] = item.yellowlab_delta["scores"]["cssComplexity_delta"]
        elif 'badCSS_delta' == json_data[key]:
            json_data[key] = item.yellowlab_delta["scores"]["badCSS_delta"]
        elif 'fonts_delta' == json_data[key]:
            json_data[key] = item.yellowlab_delta["scores"]["fonts_delta"]
        elif 'serverConfig_delta' == json_data[key]:
            json_data[key] = item.yellowlab_delta["scores"]["serverConfig_delta"]
        
        elif 'yellowlab_average' == json_data[key]:
            json_data[key] = item.yellowlab["scores"]["globalScore"]
        elif 'pageWeight' == json_data[key]:
            json_data[key] = item.yellowlab["scores"]["pageWeight"]
        elif 'requests' == json_data[key]:
            json_data[key] = item.yellowlab["scores"]["requests"]
        elif 'domComplexity' == json_data[key]:
            json_data[key] = item.yellowlab["scores"]["domComplexity"]
        elif 'javascriptComplexity' == json_data[key]:
            json_data[key] = item.yellowlab["scores"]["javascriptComplexity"]
        elif 'badJavascript' == json_data[key]:
            json_data[key] = item.yellowlab["scores"]["badJavascript"]
        elif 'jQuery' == json_data[key]:
            json_data[key] = item.yellowlab["scores"]["jQuery"]
        elif 'cssComplexity' == json_data[key]:
            json_data[key] = item.yellowlab["scores"]["cssComplexity"]
        elif 'badCSS' == json_data[key]:
            json_data[key] = item.yellowlab["scores"]["badCSS"]
        elif 'fonts' == json_data[key]:
            json_data[key] = item.yellowlab["scores"]["fonts"]
        elif 'serverConfig' == json_data[key]:
            json_data[key] = item.yellowlab["scores"]["serverConfig"]

        elif 'avg_image_score' == json_data[key]:
            json_data[key] = item.images_delta["average_score"]
        elif 'image_scores' == json_data[key]:
            json_data[key] = [i["score"] for i in item.images_delta["images"]]


    return json_data






def get_item(object_id):
    try:
        item = Test.objects.get(id=uuid.UUID(object_id))
        item_type = 'Test'
    except:
        try:
            item = Scan.objects.get(id=uuid.UUID(object_id))
            item_type = 'Scan'
        except:
            try:
                item = Testcase.objects.get(id=uuid.UUID(object_id))
                item_type = 'Testcase'
            except:
                return {'success': False}

    data = {
        'item_type': item_type, 
        'item': item,
        'success': True
    }

    return data





def automation_email(email=None, automation_id=None, object_id=None):
    if email and automation_id:
        user = User.objects.get(email=email)
        automation = Automation.objects.get(id=automation_id)
        schedule = automation.schedule
        if schedule.site is not None:
            url_end = '/site/'+str(schedule.site.id)
            url = schedule.site.site_url
        else:
            url_end = '/page/'+str(schedule.page.id)
            url = schedule.page.page_url

        # getting object
        data = get_item(object_id=object_id)
        if not data['success']:
            return {'success': False}

        item = data['item']
        item_type = data['item_type']

        exp_list = create_exp_str(item=item, automation=automation, is_email=True)

        object_url = str(os.environ.get('CLIENT_URL_ROOT') + url_end)
        subject = f'Alert for {url}'
        title = f'Alert for {url}'
        pre_header = f'Alert for {url}'
        pre_content = (
            f'Scanerr just finished running a {item_type} for {url}. ' 
            f'Below are the current stats:\n'
        )
        content = (
            f'This message was triggered by an automation you created. ' 
            f'You can change the automation and schedule in your site\'s dashboard. '
        )
        subject = subject

        context = {
            'title' : title,
            'subject': subject,
            'pre_header' : pre_header,
            'pre_content' : pre_content,
            'exp_list': exp_list,
            'object_url' : object_url,
            'home_page' : os.environ.get('CLIENT_URL_ROOT'),
            'button_text' : 'View Site Dashboard',
            'content' : content,
            'email': email,
            'signature' : '- Cheers!',
        }

        sendgrid_email(message_obj=context)

        data = {
            'success': True
        }
    
    else:
        data = {
            'success': False
        }
        
    return data





def automation_report_email(email=None, automation_id=None, object_id=None):
    if email and automation_id:
        automation = Automation.objects.get(id=automation_id)
        schedule = automation.schedule
        if schedule.site is not None:
            url_end = '/site/'+str(schedule.site.id)
            url = schedule.site.site_url
        else:
            url_end = '/page/'+str(schedule.page.id)
            url = schedule.page.page_url
        try:
            item = Report.objects.get(id=uuid.UUID(object_id))
            item_type = 'Report'
        except:
            return {'success': False}

        exp_list = ''
        object_url = str(item.path)
        subject = f'Report for {url}'
        title = f'Report for {url}'
        pre_header = f'Report for {url}'
        pre_content = (
            f'Scanerr just finished creating a {item_type} for {url}. ' 
            f'Please click the link below to access and download the report.\n'
        )
        content = (
            f'This message was triggered by an automation created with Scanerr. ' 
            f'You can change the automation and schedule in your site\'s dashboard. '
        )
        subject = subject
        context = {
            'title' : title,
            'pre_header' : pre_header,
            'pre_content' : pre_content,
            'exp_list': exp_list,
            'object_url' : object_url,
            'home_page' : os.environ.get('CLIENT_URL_ROOT'),
            'button_text' : 'View Report',
            'content' : content,
            'signature' : '- Cheers!',
        }

        html_message = render_to_string('api/automation_email.html', context)
        plain_message = strip_tags(html_message)
        send_mail(
            from_email = os.getenv('EMAIL_HOST_USER'),
            subject = subject,
            message = plain_message,
            recipient_list = [email],
            html_message = html_message,
            fail_silently = True,
        )

        data = {
            'success': True
        }
    
    else:
        data = {
            'success': False
        }
        
    return data




def automation_webhook(
        request_type=None, 
        request_url=None, 
        request_data=None,
        automation_id=None, 
        object_id=None,
    ):
    if request_type and automation_id and request_url and request_data and object_id:
        automation = Automation.objects.get(id=automation_id)
        schedule = automation.schedule
        if schedule.site is not None:
            url_end = '/site/'+str(schedule.site.id)
            url = schedule.site.site_url
        else:
            url_end = '/page/'+str(schedule.page.id)
            url = schedule.page.page_url

        # getting object
        data = get_item(object_id=object_id)
        if not data['success']:
            return {'success': False}

        item = data['item']
        item_type = data['item_type']
        
        pre_json_data = json.loads(request_data)
        json_data = create_json_data(data=pre_json_data, obj=item)

        try:
            if request_type == 'POST':
                response = requests.post(request_url, data=json_data)
            elif request_data == 'GET':
                response = requests.get(request_url, params=json_data)

            print(response.json())

        except:
            data = {'success': False}

        data = {
            'success': True
        }
    
    else:
        data = {
            'success': False
        }
        
    return data





def automation_phone(phone_number=None, automation_id=None, object_id=None):
    if phone_number and automation_id and object_id:
        automation = Automation.objects.get(id=automation_id)
        schedule = automation.schedule
        if schedule.site is not None:
            url_end = '/site/'+str(schedule.site.id)
            url = schedule.site.site_url
        else:
            url_end = '/page/'+str(schedule.page.id)
            url = schedule.page.page_url

        # getting object
        data = get_item(object_id=object_id)
        if not data['success']:
            return {'success': False}

        item = data['item']
        item_type = data['item_type']

        exp_str = create_exp_str(item=item, automation=automation)

        object_url = str(os.environ.get('CLIENT_URL_ROOT') + url_end)
        pre_content = (
            f'Scanerr just finished running a {item_type} for {url}. ' 
            f'Below are the current stats:\n\n\t{exp_str}\n'
        )
        content = (
            f'This message was triggered by an automation you created. ' 
            f'You can change the automation and schedule in your site\'s dashboard. '
        )

        body = f'Hi there,\n\n{pre_content}{content}\n{object_url}'

        account_sid = os.environ.get("TWILIO_SID")
        auth_token  = os.environ.get("TWILIO_AUTH_TOKEN")
        client = Client(account_sid, auth_token)

        message = client.messages.create(
            to=phone_number, 
            from_=os.environ.get('TWILIO_NUMBER'),
            body=body
        )
        
        data = {
            'success': True
        }
    
    else:
        data = {
            'success': False
        }
        
    return data




def automation_slack(automation_id=None, object_id=None):
    if automation_id and object_id:
        automation = Automation.objects.get(id=automation_id)
        account = Account.objects.get(user=automation.user)
        schedule = automation.schedule
        if schedule.site is not None:
            url_end = '/site/'+str(schedule.site.id)
            url = schedule.site.site_url
        else:
            url_end = '/page/'+str(schedule.page.id)
            url = schedule.page.page_url


        # getting object
        data = get_item(object_id=object_id)
        if not data['success']:
            return {'success': False}

        item = data['item']
        item_type = data['item_type']

        exp_str = create_exp_str(item=item, automation=automation)

        object_url = str(os.environ.get('CLIENT_URL_ROOT') + url_end)
        pre_content = (
            f'Scanerr just finished running a {item_type} for {url}. ' 
            f'Below are the current stats:\n\n\t{exp_str}\n'
        )
        content = (
            f'This message was triggered by an automation you created. ' 
            f'You can change the automation and schedule in your site\'s dashboard. '
        )

        body = f'Hi there,\n\n{pre_content}{content}\n{object_url}'

        token = account.slack['bot_access_token']
        channel = account.slack['slack_channel_id']

        client = WebClient(token=token) 
        try:
            response = client.chat_postMessage(
                channel=channel,
                text=(body),
                block=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": body,
                                    
                        }
                    }
                ]
            )
        except SlackApiError as e:
            assert e.response["error"]

        data = {
            'success': True
        }
    
    else:
        data = {
            'success': False
        }
        
    return data







def sendgrid_email(message_obj):
    """
    Tries to send an email via the SendGrid API.

    Expects the following:
        "message_obj": <obj> {
            'pre_content':  <str>,
            'content':      <str>,
            'subject':      <str>,
            'title':        <str>,
            'pre_header':   <str>,
            'button_text':  <str>,
            'exp_list':     <array>,
            'email':        <str>,
            'template':     <str>,
            'object_url':   <str>,
            'signature':    <str>,
            'greeting':     <str>,
        }

    Returns --> data: {
        'message': True
    }
    """


    # defining data
    pre_content = message_obj.get('pre_content')
    content = message_obj.get('content')
    subject = message_obj.get('subject')
    title = message_obj.get('title')
    pre_header = message_obj.get('pre_header')
    button_text = message_obj.get('button_text')
    email = message_obj.get('email')
    exp_list = message_obj.get('exp_list')
    object_url = message_obj.get('object_url')
    signature = message_obj.get('signature', '- Cheers!')
    greeting = message_obj.get('greeting', 'Hi there,')


    # build template data
    template_data = {
        'greeting': greeting,
        'title' : title,
        'pre_header' : pre_header,
        'pre_content' : pre_content,
        'object_url' : object_url,
        'exp_list': exp_list,
        'home_page' : settings.LANDING_API_ROOT,
        'button_text' : button_text,
        'content' : content,
        'signature' : signature,
        'subject': subject,
    }

    # decide which template to use based on data
    template = settings.DEFAULT_TEMPLATE
    if object_url is None:
        template = settings.DEFAULT_TEMPLATE_NO_BUTTON
    if exp_list is not None:
        template = settings.AUTOMATION_TEMPLATE


    # init SendGrid message
    message = Mail(
        from_email=From('hello@scanerr.io', 'Scanerr'),  # prod -> settings.EMAIL_HOST_USER
        to_emails=email,  
    )
    
    # attach template data and id
    message.dynamic_template_data = template_data
    message.template_id = template

    # send message 
    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        status = True
    except Exception as e:
        status = False
        print(e.message)

    
    data = {
        'success': status
    }

    return data
