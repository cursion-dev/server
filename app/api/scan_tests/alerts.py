from django.core.mail import send_mail, send_mass_mail
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from datetime import date
import os, operator, json, requests, uuid
from django.utils.html import strip_tags
from django.contrib.auth.models import User
from rest_framework.response import Response
from ..models import (Schedule, Automation, Test, Scan, Site, Account)
from twilio.rest import Client
from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError





def automation_email(email=None, automation_id=None, scan_or_test_id=None):
    if email and automation_id:
        automation = Automation.objects.get(id=automation_id)
        schedule = automation.schedule
        site = schedule.site

        try:
            item = Test.objects.get(id=uuid.UUID(scan_or_test_id))
            item_type = 'Test'
        except:
            try:
                item = Scan.objects.get(id=uuid.UUID(scan_or_test_id))
                item_type = 'Scan'
            except:
                return {'success': False}

        exp_list = []
        for e in automation.expressions:
            if 'test_score' in e['data_type']:
                data_type = 'Test Score:\t'+str(round(item.score, 2))+'\n\t'
            elif 'current_average' in e['data_type']:
                data_type = 'Health:\t'+str(item.scores_delta["current_average"])+'\n\t'
            elif 'seo_delta' in e['data_type']:
                data_type = 'SEO Delta:\t'+str(item.scores_delta["seo_delta"])+'\n\t'
            elif 'best_practices_delta' in e['data_type']:
                data_type = 'Best Practicies Delta:\t'+str(item.scores_delta["best_practices_delta"])+'\n\t'
            elif 'performance_delta' in e['data_type']:
                data_type = 'Performance Delta:\t'+str(item.scores_delta["performance_delta"])+'\n\t'
            elif 'logs' in e['data_type']:
                data_type = 'Error Logs:\t'+str(len(item.logs))+'\n\t'
            elif 'health' in e['data_type']:
                data_type = 'Health:\t'+str(item.scores["average"])+'\n\t'
            exp_list.append(data_type)

        exp_str = ('\t'+''.join(exp_list))

        object_url = str(os.environ.get('CLIENT_URL_ROOT') + '/site/'+str(site.id))
        subject = f'Alert for {site.site_url}'
        title = f'Alert for {site.site_url}'
        pre_header = f'Alert for {site.site_url}'
        pre_content = (
            f'Scanerr just finished running a {item_type} for {site.site_url}. ' 
            f'Below are the current stats:\n'
        )
        content = (
            f'This message was triggered by an automation you created. ' 
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
            'button_text' : 'View Site Dashboard',
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
    scan_or_test_id=None,
    ):
    if request_type and automation_id and request_url and request_data and scan_or_test_id:
        automation = Automation.objects.get(id=automation_id)
        schedule = automation.schedule
        site = schedule.site

        try:
            item = Test.objects.get(id=uuid.UUID(scan_or_test_id))
            item_type = 'Test'
        except:
            try:
                item = Scan.objects.get(id=uuid.UUID(scan_or_test_id))
                item_type = 'Scan'
            except:
                return {'success': False}
        
        json_data = json.loads(request_data)
        get_list = ['?',]

        for key in json_data:
            if 'test_score' == json_data[key]:
                json_data[key] = item.score
            elif 'current_average' == json_data[key]:
                json_data[key] = item.scores_delta["current_average"]
            elif 'seo_delta' == json_data[key]:
                json_data[key] = item.scores_delta["seo_delta"]
            elif 'best_practices_delta' == json_data[key]:
                json_data[key] = item.scores_delta["best_practices_delta"]
            elif 'performance_delta' == json_data[key]:
                json_data[key] = item.scores_delta["performance_delta"]
            elif 'logs' == json_data[key]:
                json_data[key] = len(item.logs)
            elif 'health' == json_data[key]:
                json_data[key] = item.scores["average"]
            
            get_list.append(f'{key}={json_data[key]}&')

        get_params = ''.join(get_list)

        try:
            if request_type == 'POST':
                request = requests.post(request_url, data=json_data)
            elif request_data == 'GET':
                request = requests.get(request_url, params=json_data)

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





def automation_phone(phone_number=None, automation_id=None, scan_or_test_id=None):
    if phone_number and automation_id and scan_or_test_id:
        automation = Automation.objects.get(id=automation_id)
        schedule = automation.schedule
        site = schedule.site

        try:
            item = Test.objects.get(id=uuid.UUID(scan_or_test_id))
            item_type = 'Test'
        except:
            try:
                item = Scan.objects.get(id=uuid.UUID(scan_or_test_id))
                item_type = 'Scan'
            except:
                return {'success': False}

        exp_list = []
        for e in automation.expressions:
            if 'test_score' in e['data_type']:
                data_type = 'Test Score:\t'+str(round(item.score, 2))+'\n\t'
            elif 'current_average' in e['data_type']:
                data_type = 'Health:\t'+str(item.scores_delta["current_average"])+'\n\t'
            elif 'seo_delta' in e['data_type']:
                data_type = 'SEO Delta:\t'+str(item.scores_delta["seo_delta"])+'\n\t'
            elif 'best_practices_delta' in e['data_type']:
                data_type = 'Best Practicies Delta:\t'+str(item.scores_delta["best_practices_delta"])+'\n\t'
            elif 'performance_delta' in e['data_type']:
                data_type = 'Performance Delta:\t'+str(item.scores_delta["performance_delta"])+'\n\t'
            elif 'logs' in e['data_type']:
                data_type = '# Error Logs:\t'+str(len(item.logs))+'\n\t'
            elif 'health' in e['data_type']:
                data_type = 'Health:\t'+str(item.scores["average"])+'\n\t'
            exp_list.append(data_type)

        exp_str = ''.join(exp_list)

        object_url = str(os.environ.get('CLIENT_URL_ROOT') + '/site/'+str(site.id))
        pre_content = (
            f'Scanerr just finished running a {item_type} for {site.site_url}. ' 
            f'Below are the current stats:\n\n\t{exp_str}\n'
        )
        content = (
            f'This message was triggered by an automation you created. ' 
            f'You can change the automation and schedule in your site\'s dashboard. '
        )

        body = f'Hi there,\n\n{pre_content}{content}'

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




def automation_slack(automation_id=None, scan_or_test_id=None):
    if automation_id and scan_or_test_id:
        automation = Automation.objects.get(id=automation_id)
        account = Account.objects.get(user=automation.user)
        schedule = automation.schedule
        site = schedule.site

        try:
            item = Test.objects.get(id=uuid.UUID(scan_or_test_id))
            item_type = 'Test'
        except:
            try:
                item = Scan.objects.get(id=uuid.UUID(scan_or_test_id))
                item_type = 'Scan'
            except:
                return {'success': False}

        exp_list = []
        for e in automation.expressions:
            if 'test_score' in e['data_type']:
                data_type = 'Test Score:\t'+str(round(item.score, 2))+'\n\t'
            elif 'current_average' in e['data_type']:
                data_type = 'Health:\t'+str(item.scores_delta["current_average"])+'\n\t'
            elif 'seo_delta' in e['data_type']:
                data_type = 'SEO Delta:\t'+str(item.scores_delta["seo_delta"])+'\n\t'
            elif 'best_practices_delta' in e['data_type']:
                data_type = 'Best Practicies Delta:\t'+str(item.scores_delta["best_practices_delta"])+'\n\t'
            elif 'performance_delta' in e['data_type']:
                data_type = 'Performance Delta:\t'+str(item.scores_delta["performance_delta"])+'\n\t'
            elif 'logs' in e['data_type']:
                data_type = '# Error Logs:\t'+str(len(item.logs))+'\n\t'
            elif 'health' in e['data_type']:
                data_type = 'Health:\t'+str(item.scores["average"])+'\n\t'
            exp_list.append(data_type)

        exp_str = ''.join(exp_list)

        object_url = str(os.environ.get('CLIENT_URL_ROOT') + '/site/'+str(site.id))
        pre_content = (
            f'Scanerr just finished running a {item_type} for {site.site_url}. ' 
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