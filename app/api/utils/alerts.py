from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from twilio.rest import Client
from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import *
from ..models import *
from cursion import settings
from .definitions import get_definition, definitions
from datetime import date
from cryptography.fernet import Fernet
import os, json, requests, uuid






def send_reset_link(email: str=None) -> dict:
    """
    Sends a reset password email to the User with 
    the passed 'email'

    Expects: {
        'email': str
    }

    Returns -> data: {
        'success': bool
    }
    """

    # check if User exists
    if User.objects.filter(email=email).exists():

        # build email data
        user = User.objects.get(email=email)
        token = RefreshToken.for_user(user)
        access_token = str(token.access_token)
        reset_link = str(settings.CLIENT_URL_ROOT+'/reset-password?token='+access_token)
        subject = 'Rest Password'
        title = 'Reset Password'
        pre_header = 'Reset Password'
        pre_content = 'Click the link below to reset your password.'
        greeting = f'Hi there,'

        context = {
            'greeting': greeting,
            'title' : title,
            'subject' : subject,
            'email': email,
            'pre_header' : pre_header,
            'pre_content' : pre_content,
            'object_url' : reset_link,
            'home_page' : settings.CLIENT_URL_ROOT,
            'button_text' : 'Rest my password',
            'content' : '',
            'signature' : '- Cheers!',
        }

        # send email
        sendgrid_email(message_obj=context)

        data = {
            'success': True
        }
    
    else:
        data = {
            'success': False
        }
        
    return data




def send_invite_link(member: object=None) -> dict:
    """
    Sends an invite email to the passed `Member`

    Expects: {
        'member': obj
    }

    Returns -> data: {
        'success': bool
    }
    """

    # check if member exists as status "pending"
    if Member.objects.filter(email=member.email, status="pending").exists():

        # build email data
        link = (
            f'{settings.CLIENT_URL_ROOT}/account/join?team={member.account.id}'+
            f'&code={member.account.code}&member={member.id}&email={member.email}'
        )
        subject = 'Cursion Invite'
        title = 'Cursion Invite'
        pre_header = 'Cursion Invite'
        pre_content = (
            f'A user with the email "{member.account.user.username}" invited you to join their '+
            f'Team on Cursion. Now just click the link below to accept the invite!'
        )
        greeting = 'Hi there,'

        context = {
            'greeting': greeting,
            'title' : title,
            'subject' : subject,
            'email': member.email,
            'pre_header' : pre_header,
            'pre_content' : pre_content,
            'object_url' : link,
            'home_page' : settings.CLIENT_URL_ROOT,
            'button_text' : 'Accept Invite',
            'content' : '',
            'signature' : '- Cheers!',
        }
        
        # send email
        sendgrid_email(message_obj=context)

        data = {
            'success': True
        }
    
    else:
        data = {
            'success': False
        }
        
    return data




def send_remove_alert(member: object=None) -> dict:
    """
    Sends a "removed" email to the passed `Member` and 
    deletes member from DB 

    Expects: {
        'member': obj
    }

    Returns -> data: {
        'success': bool
    }
    """

    # check if member exists as status "removed"
    if Member.objects.filter(email=member.email, status="removed").exists():

        # build email data
        subject = 'Removed From Account'
        title = 'Removed From Account'
        pre_header = 'Removed From Account'
        pre_content = (
            f'A user with the email "{member.account.user.username}" removed you '+
            f'from their Team on Cursion. Please let us know if there\'s been a mistake.'
        )
        greeting = 'Hi there,'

        context = {
            'greeting' : greeting,
            'title' : title,
            'subject' : subject,
            'email': member.email,
            'pre_header' : pre_header,
            'pre_content' : pre_content,
            'object_url' : None,
            'home_page' : settings.CLIENT_URL_ROOT,
            'content' : '',
            'signature' : '- Cheers!',
        }

        # send email
        sendgrid_email(message_obj=context)

        # delete member obj
        member.delete()

        data = {
            'success': True
        }
    
    else:
        data = {
            'success': False
        }
        
    return data




def create_exp(obj: object=None, alert: object=None) -> dict:
    """ 
    Builds an expression list (exp_list = []) based 
    on the passed 'obj' and `Alert`.

    Expects: {
        'obj'   :  object (Scan, Test, CaseRun, FlowRun),
        'alert' :  object
    }

    Returns -> data: {
        'exp_list': list, 
        'exp_str' : str,
    }
    """

    # seting defaults
    exp_list = []
    exp_str = ''
    
    # loop through alert expressions
    for e in alert.expressions:

        # settign defaults
        title = None
        data = None

        # generate custom data and scores
        if 'test_score' in e['data_type']:
            title = 'Test Score'
            data = str(round(obj.score, 2))
        if 'test_status' in e['data_type']:
            status = '❌ FAILED'
            if obj.status == 'passed':
                status = '✅ PASSED'
            title = 'Test Status'
            data = status
        if 'caserun_status' in e['data_type']:
            status = '❌ FAILED'
            if e['value'] == 'passed':
                status = '✅ PASSED'
            title = f'"{obj.title}"'
            data = status
        if 'flowrun_status' in e['data_type']:
            status = '❌ FAILED'
            if e['value'] == 'passed':
                status = '✅ PASSED'
            title = f'"{obj.title}"'
            data = status

        # get title and data if None
        if title == None:
            definition = get_definition(e['data_type'])
            if definition:
                title = definition['name']
                data = str(eval(definition['value']))
        
        # create data string
        data_str = f' {title}:   {data}\n'
        exp_str += data_str
        
        # add to exp_list
        exp_list.append({
            'title': title,
            'data': data
        })

    # formating return data
    data = {
        'exp_list': exp_list,
        'exp_str': exp_str,
    }

    return data




def transpose_data(string: str=None, obj: object=None, secrets: list=[]) -> dict: 
    """ 
    Using 'definitions.py' replaces all vairables with definition data.

    Expects: {
        'string'    : str (to be transposed)
        'obj'       : object (Scan, Test, CaseRun, Report),
        'secrets'   : list (account secrets)
    }

    Returns -> transposed string
    """

    # decryption helper
    def decrypt_secret(value):
        f = Fernet(settings.SECRETS_KEY)
        decoded = f.decrypt(value)
        return decoded.decode('utf-8')

    # create secrets_list
    secrets_list = []
    for secret in secrets:
        secrets_list.append({
            'key': '{{'+str(secret.name)+'}}',
            'value': decrypt_secret(secret.value)
        })

    # iterate through secrets and replace data 
    for item in secrets_list:
        string = string.replace(
            item['key'], 
            item['value']
        )

    # iterate through definitions and 
    # replace {{vairables}} with str(value) first
    for item in definitions:
        string = string.replace(
            ('{{'+str(item['key'])+'}}'), 
            str(item['value'])
        )

    # iterate through definitions and replace 
    # str(value) with eval(str(value))
    for item in definitions:
        if item['value'] in string:
            value = eval(item['value'])
            data = value if value is not None else 0
            string = string.replace(
                str(item['value']), 
                str(data)
            )

    # return updated string
    return string




def get_obj(object_id: str=None) -> dict:
    """ 
    Tries to find an object that matches theh passed 'object_id'.

    Expects: {
        'object_id':  str,
    }

    Returns -> data: {
        'obj'      : object (Scan, Test, CaseRun, FlowRun, Report),
        'obj_type' : str,
        'success'  : bool
    }
    """

    # init obj
    obj = None
    obj_type = ''
    success = False

    # check for obj
    if not obj:
        try:
            obj = Test.objects.get(id=uuid.UUID(object_id))
            obj_type = 'Test'
            success = True
        except:
            pass
    if not obj:
        try:
            obj = Scan.objects.get(id=uuid.UUID(object_id))
            obj_type = 'Scan'
            success = True
        except:
            pass
    if not obj:
        try:
            obj = CaseRun.objects.get(id=uuid.UUID(object_id))
            obj_type = 'CaseRun'
            success = True
        except:
            pass
    if not obj:
        try:
            obj = FlowRun.objects.get(id=uuid.UUID(object_id))
            obj_type = 'FlowRun'
            success = True
        except:
            pass
    if not obj:
        try:
            obj = Report.objects.get(id=uuid.UUID(object_id))
            obj_type = 'Report'
            success = True
        except:
            pass
    
    # format and return data
    data = {
        'obj': obj,
        'obj_type': obj_type, 
        'success': success
    }

    return data




def alert_email(email: str=None, alert_id: str=None, object_id: str=None) -> dict:
    """
    Sends an alert email to the User with 
    the passed 'email'

    Expects: {
        'email'         : str,
        'alert_id' : str,
        'object_id'     : str
    }

    Returns -> data: {
        'success': bool
    }
    """

    # check if data is present
    if email and alert_id:

        # get alert 
        alert = Alert.objects.get(id=alert_id)
        schedule = alert.schedule
    
        # getting object
        data = get_obj(object_id=object_id)
        if not data['success']:
            return {'success': False}

        # getting object data
        obj = data['obj']
        obj_type = data['obj_type']

        # clean obj_type
        obj_name = obj_type.replace('Run', '')

        # deciding if "page" or "site" scope
        if obj_type == 'CaseRun' or obj_type == 'FlowRun':
            url = obj.site.site_url
        else:
            url = obj.page.page_url

        # build dash link
        dash_link = f'{settings.CLIENT_URL_ROOT}/schedule'

        # generating expressions from alert
        exp_list = create_exp(
            obj=obj, 
            alert=alert
        )['exp_list']

        # build email data
        object_url = f'{settings.CLIENT_URL_ROOT}/{obj_type.lower()}/{str(obj.id)}'
        subject = f'Alert for {url}'
        title = f'Alert for {url}'
        pre_header = f'Alert for {url}'
        pre_content = (
            f'Cursion just finished running a {obj_name} for {url}. ' 
            f'Below are the current stats:'
        )
        content = (
            f'This message was triggered by an alert you created. ' 
            f'You can change the alert and schedule in your '
            f'<a href="{dash_link}">dashboard</a>.'
        )

        context = {
            'title' : title,
            'subject': subject,
            'pre_header' : pre_header,
            'pre_content' : pre_content,
            'exp_list': exp_list,
            'object_url' : object_url,
            'home_page' : settings.CLIENT_URL_ROOT,
            'button_text' : f'View {obj_name}',
            'content' : content,
            'email': email,
            'signature' : '- Cheers!',
        }

        # send email
        sendgrid_email(message_obj=context)

        data = {
            'success': True
        }
    
    else:
        data = {
            'success': False
        }
        
    return data




def alert_report_email(email: str=None, alert_id: str=None, object_id: str=None) -> dict:
    """
    Sends an alert report email to the User with 
    the passed 'email'

    Expects: {
        'email'         : str,
        'alert_id' : str,
        'object_id'     : str
    }

    Returns -> data: {
        'success': bool
    }
    """

    # check if data is present
    if email and alert_id:
        
        # retrieving user
        user = User.objects.get(email=email)

        # get alert and deciding if "page" or "site" scope
        alert = Alert.objects.get(id=alert_id)
        schedule = alert.schedule
        
        # get `Report` if exists
        try:
            report = Report.objects.get(id=uuid.UUID(object_id))
            obj_type = 'Report'
            url = report.page.page_url
        except:
            return {'success': False}

        # build email data
        object_url = str(report.path)
        subject = f'Report for {url}'
        title = f'Report for {url}'
        pre_header = f'Report for {url}'
        pre_content = (
            f'Cursion just finished creating a ' 
            f'<a href="{settings.CLIENT_URL_ROOT}/page/{str(report.page.id)}/report">Report</a> for {url}. '
            f'Please click the link below to access and download the PDF.'
        )
        content = (
            f'\nThis message was triggered by an alert created with Cursion. ' 
            f'You can change the alert and schedule in your ' 
            f'<a href="{settings.CLIENT_URL_ROOT}/schedule">dashboard</a>.'
        )

        context = {
            'title' : title,
            'subject': subject,
            'pre_header' : pre_header,
            'pre_content' : pre_content,
            'object_url' : object_url,
            'home_page' : settings.CLIENT_URL_ROOT,
            'button_text' : 'View Report',
            'content' : content,
            'email': email,
            'signature' : '- Cheers!',
        }

        # send email
        sendgrid_email(message_obj=context)
        data = {
            'success': True
        }
    
    else:
        data = {
            'success': False
        }
        
    return data




def alert_phone(phone_number: str=None, alert_id: str=None, object_id: str=None) -> dict:
    """
    Sends an SMS alert to the passed 'phone_number' 
    with the `Alert` data 

    Expects: {
        'phone_number'    : str, 
        'alert_id'        : str, 
        'object_id'       : str,
    }

    Returns -> data: {
        'success': bool
    }
    """

    # checking if data is present
    if phone_number and alert_id and object_id:

        # getting schedule and alert
        alert = Alert.objects.get(id=alert_id)
        schedule = alert.schedule
        account_id = str(schedule.account.id)

        # getting object
        data = get_obj(object_id=object_id)
        if not data['success']:
            return {'success': False}

        # get obj and type
        obj = data['obj']
        obj_type = data['obj_type']

        # clean obj_type
        obj_name = obj_type.replace('Run', '')

        # deciding if "page" or "site" scope
        if obj_type == 'CaseRun' or obj_type == 'FlowRun':
            url = obj.site.site_url
        else:
            url = obj.page.page_url
        
        # build dash link
        dash_link = f'{settings.CLIENT_URL_ROOT}/schedule'

        # build the exp_str
        exp_str = create_exp(obj=obj, alert=alert)['exp_str']

        # build message data
        object_url = f'{settings.CLIENT_URL_ROOT}/{obj_type.lower()}/{obj.id}'
        pre_content = (
            f'Cursion just finished running a {obj_name} for {url}. ' 
            f'Below are the current stats:\n\n{exp_str}\n'
            f'View {obj_name}: {object_url}\n\n'
        )
        content = (
            f'This message was triggered by an alert you created. ' 
            f'You can change the alert and schedule in your dashboard: {dash_link}'
        )
        body = f'Hi there,\n\n{pre_content}{content}'

        # send message 
        data = send_phone(
            account_id=account_id, 
            object_id=object_id, 
            phone_number=phone_number, 
            body=body
        )
        return data        
    
    else:
        data = {
            'success': False
        }
        
    return data




def alert_slack(alert_id: str=None, object_id: str=None) -> dict:
    """
    Sends a Slack alert with the `Alert` data 

    Expects: {
        'alert_id'   : str, 
        'object_id'  : str,
    }

    Returns -> data: {
        'success': bool
    }
    """

    # check if data is present
    if alert_id and object_id:
        
        # getting schedule, account and alert
        alert = Alert.objects.get(id=alert_id)
        schedule = alert.schedule
        account = schedule.account
        

        # getting object
        data = get_obj(object_id=object_id)
        if not data['success']:
            return {'success': False}

        # get obj and type
        obj = data['obj']
        obj_type = data['obj_type']

        # deciding if "page" or "site" scope
        if obj_type == 'CaseRun' or obj_type == 'FlowRun':
            url = obj.site.site_url
        else:
            url = obj.page.page_url
        
        # build dash link
        dash_link = f'{settings.CLIENT_URL_ROOT}/schedule'

        # build exp_str
        exp_str = create_exp(obj=obj, alert=alert)['exp_str']

        # clean obj_type
        obj_name = obj_type.replace('Run', '')

        # build message data
        object_url = f'{settings.CLIENT_URL_ROOT}/{obj_type}/{obj.id}'
        pre_content = (
            f'Cursion just finished running a `{obj_name}` for {url}. ' 
            f'Below are the current stats:\n\n```{exp_str}```\n'
            f'<{object_url}|*View {obj_name}*>\n\n'
        )
        content = (
            f'This message was triggered by an alert you created. ' 
            f'You can change the alert and schedule in your '
            f'<{dash_link}|dashboard>.'
        )
        body = f'Hi there,\n\n{pre_content}{content}'

        # send slack message
        data = send_slack(
            account_id=account.id, 
            object_id=object_id, 
            body=body
        )

        return data
    
    else:
        data = {
            'success': False
        }
        
    return data




def sendgrid_email(
        account_id: str=None, 
        object_id: str=None, 
        message_obj: dict=None
    ) -> dict:
    """
    Tries to send an email via the SendGrid API.

    Expects:{
        'account_id' : str, 
        'object_id'  : str,
        'message_obj': dict {
            'plain_text':   bool,
            'pre_content':  str,
            'content':      str,
            'subject':      str,
            'title':        str,
            'pre_header':   str,
            'button_text':  str,
            'exp_list':     list,
            'email':        str,
            'template':     str,
            'object_url':   str,
            'signature':    str,
            'greeting':     str,
        }
    }

    Returns: {
        'success': bool,
        'message': str
    }
    """

    # defining data
    plain_text = message_obj.get('plain_text', False)
    pre_content = message_obj.get('pre_content')
    content = message_obj.get('content')
    subject = message_obj.get('subject', 'Alert from Cursion')
    title = message_obj.get('title')
    pre_header = message_obj.get('pre_header')
    button_text = message_obj.get('button_text')
    email = message_obj.get('email')
    exp_list = message_obj.get('exp_list')
    object_url = message_obj.get('object_url')
    signature = message_obj.get('signature', '- Cheers!')
    greeting = message_obj.get('greeting', 'Hi there,')

    if account_id:
        # get account & secrets
        account = Account.objects.get(id=account_id)
        secrets = Secret.objects.filter(account=account)

        # get object
        obj = get_obj(object_id)['obj']

        # cleaning data
        content = transpose_data(content, obj, secrets)
        subject = transpose_data(subject, obj, secrets)

        # replacing '\n' with <br>
        content = content.replace('\n', '<br>')
        pre_content = content.replace('\n', '<br>')

    # build template data
    template_data = {
        'greeting': greeting,
        'title' : title,
        'pre_header' : pre_header,
        'pre_content' : pre_content,
        'object_url' : object_url,
        'exp_list': exp_list,
        'home_page' : settings.LANDING_URL_ROOT,
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
        from_email=From(settings.SENDGRID_EMAIL, 'Cursion'),
        to_emails=email,  
    )

    # attach template data and id
    if not plain_text:
        message.dynamic_template_data = template_data
        message.template_id = template
    
    # building message as plain text
    if plain_text:
        message.subject = Subject(subject)
        message.content = [
            Content(
                mime_type="text/html",
                content=content
            )
        ]

    # test
    print(f'testing sendgrid using API key {settings.SENDGRID_API_KEY}')
    sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
    try:
        response = sg.client.user.profile.get()
        print(response.status_code)
        print(response.body)
    except Exception as e:
        print(e)

    # send message 
    try:
        print(f'sending email using API key {settings.SENDGRID_API_KEY}')
        sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        response = sg.send(message)
        print(response)
        status = True
        msg = 'email sent successfully'
    except Exception as e:
        status = False
        msg = str(e)
        print(f'Error sending -> {e}')

    # formatting resposne
    data = {
        'success': status,
        'message': msg
    }

    return data




def send_phone(
        account_id: str=None, 
        object_id: str=None, 
        phone_number: str=None, 
        body: str=None
    ) -> dict:
    """ 
    Using Twilio, sends an SMS with the passed 'body'
    top the passed 'phone_number'

    Expects: { 
        'account_id'    : str, 
        'object_id'     : str,
        'phone_number'  : str,
        'body'          : str,
    }

    Returns: {
        'success': bool,
        'message': str
    }
    """

    if account_id and object_id:
        # get account & secrets
        account = Account.objects.get(id=account_id)
        secrets = Secret.objects.filter(account=account)

        # get object
        obj = get_obj(object_id)['obj']

        # cleaning data
        body = transpose_data(body, obj, secrets)

    try:
        # setup client
        account_sid = settings.TWILIO_SID
        auth_token  = settings.TWILIO_AUTH_TOKEN
        client = Client(account_sid, auth_token)

        # clean phone_number
        phone_number = phone_number.strip().replace('(', '').replace(')', '').replace('-', '')
        phone_number = ''.join(phone_number.split())

        # send message
        message = client.messages.create(
            to=phone_number, 
            from_=settings.TWILIO_NUMBER,
            body=body
        )
        success = True
        msg = 'sms sent successfully'

    except Exception as e:
        print(e)
        success = False
        msg = str(e)
    
    data = {
        'success': success,
        'message': msg
    }
    return data




def send_slack(
        account_id: str=None, 
        object_id: str=None, 
        body: str=None
    ) -> dict:
    """ 
    Using Slack, sends an message with the passed 'body'
    top the passed 'account'.channel

    Expects: { 
        'account_id' : str, 
        'object_id'  : str,
        'body'       : str,
    }

    Returns: {
        'success': bool,
        'message': str
    }
    """

    if account_id and object_id:
        # get account & secrets
        account = Account.objects.get(id=account_id)
        secrets = Secret.objects.filter(account=account)

        # get object
        obj = get_obj(object_id)['obj']

        # cleaning data
        body = transpose_data(body, obj, secrets)
    
    try:
        # setup client
        token = account.slack['bot_access_token']
        channel = account.slack['slack_channel_id']
        client = WebClient(token=token) 

        # send message
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
        success = True
        msg = 'slack message sent successfully'

    except SlackApiError as e:
        print(e)
        success = False
        msg = str(e)
    
    data = {
        'success': success,
        'message': msg
    }
    return data
        

    

def send_webhook(
        account_id: str=None, 
        object_id: str=None,
        request_type: str=None, 
        url: str=None, 
        headers: dict=None,
        payload: dict=None,
    ) -> dict:
    """
    Sends a GET or POST request to the passed 'url'
    with the passed 'payload' & 'heasders'

    Expects: {
        'account_id'   : str, 
        'object_id'    : str,
        'request_type' : str, 
        'url'          : str, 
        'headers'      : dict,
        'payload'      : dict,
    }

    Returns: {
        'success': bool,
        'message': str
    }
    """

    # get account & secrets
    account = Account.objects.get(id=account_id)
    secrets = Secret.objects.filter(account=account)

    # get object
    obj = get_obj(object_id)['obj']

    # cleaning data
    cleaned_headers = transpose_data(headers, obj, secrets)
    cleaned_payload = transpose_data(payload, obj, secrets)
    cleaned_url = transpose_data(url, obj, secrets)
    
    # building json
    json_payload = json.loads(cleaned_payload) if request_type == 'POST' else {}
    json_headers = json.loads(cleaned_headers)

    # send the request
    try:
        if request_type == 'POST':
            response = requests.post(
                url=cleaned_url, 
                headers=json_headers,
                data=json.dumps(json_payload)
            ).json()

        elif request_type == 'GET':
            response = requests.get(
                url=cleaned_url, 
                headers=json_headers
            ).json()

        success = True
        msg = str(response) 
    
    except Exception as e:
        success = False
        msg = str(e) 
    
    data = {
        'success': success,
        'message': msg
    }
    return data



