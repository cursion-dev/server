from datetime import date
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from ..models import *
from twilio.rest import Client
from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, From, To
from scanerr import settings
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
        reset_link = str(os.environ.get('CLIENT_URL_ROOT') + '/reset-password?token='+access_token)
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
            'home_page' : os.environ.get('CLIENT_URL_ROOT'),
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
        link = f'{os.environ.get("CLIENT_URL_ROOT")}/account/join?team={member.account.id}&code={member.account.code}&member={member.id}&email={member.email}'
        subject = 'Scanerr Invite'
        title = 'Scanerr Invite'
        pre_header = 'Scanerr Invite'
        pre_content = f'A user with the email "{member.account.user.username}" invited you to join their Team on Scanerr. Now just click the link below to accept the invite!'
        greeting = 'Hi there,'

        context = {
            'greeting': greeting,
            'title' : title,
            'subject' : subject,
            'email': member.email,
            'pre_header' : pre_header,
            'pre_content' : pre_content,
            'object_url' : link,
            'home_page' : os.environ.get('CLIENT_URL_ROOT'),
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
        pre_content = f'A user with the email "{member.account.user.username}" removed you from their Team on Scanerr. Please let us know if there\'s been a mistake.'
        greeting = 'Hi there,'

        context = {
            'greeting' : greeting,
            'title' : title,
            'subject' : subject,
            'email': member.email,
            'pre_header' : pre_header,
            'pre_content' : pre_content,
            'object_url' : None,
            'home_page' : os.environ.get('CLIENT_URL_ROOT'),
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




def create_exp(item: object=None, automation: object=None) -> dict:
    """ 
    Builds an expression list (exp_list = []) based 
    on the passed 'item' and `Automation`.

    Expects: {
        'item'       :  object (Scan, Test, Testcase),
        'automation' :  object
    }

    Returns -> data: {
        'exp_list': list, 
        'exp_str' : str,
    }
    """

    # seting defaults
    exp_list = []
    exp_str = ''
    
    # loop through automation expressions
    for e in automation.expressions:

        # top-level scores and data
        if 'test_score' in e['data_type']:
            title = 'Test Score'
            data = str(round(item.score, 2))
        elif 'test_status' in e['data_type']:
            status = '❌ FAILED'
            if item.status == 'passed':
                status = '✅ PASSED'
            title = 'Test Status'
            data = status
        elif 'testcase_status' in e['data_type']:
            status = '❌ FAILED'
            if e['value'] == 'passed':
                status = '✅ PASSED'
            title = f'"{item.case.name}"'
            data = status
        elif 'current_health' in e['data_type']:
            title = 'Health'
            data = str(
                (float(item.lighthouse_delta["scores"]["current_average"]) + 
                float(item.yellowlab_delta["scores"]["current_average"])) /2
            )
        elif 'health' in e['data_type']:
            title = 'Health'
            data = str(
                (float(item.lighthouse["scores"]["average"]) + 
                float(item.yellowlab["scores"]["globalScore"])) /2
            )
        
        # LH test data
        elif 'current_lighthouse_average' in e['data_type']:
            title = 'Lighthouse Average'
            data = str(item.lighthouse_delta["scores"]["current_average"])
        elif 'seo_delta' in e['data_type']:
            title = 'SEO Delta'
            data = str(item.lighthouse_delta["scores"]["seo_delta"])
        elif 'pwa_delta' in e['data_type']:
            title = 'PWA Delta'
            data = str(item.lighthouse_delta["scores"]["pwa_delta"])
        elif 'crux_delta' in e['data_type']:
            title = 'CRUX Delta'
            data = str(item.lighthouse_delta["scores"]["crux_delta"])
        elif 'best_practices_delta' in e['data_type']:
            title = 'Best Practices Delta'
            data = str(item.lighthouse_delta["scores"]["best_practices_delta"])
        elif 'performance_delta' in e['data_type']:
            title = 'Performance Delta'
            data = str(item.lighthouse_delta["scores"]["performance_delta"])
        elif 'accessibility_delta' in e['data_type']:
            title = 'Accessibility Delta'
            data = str(item.lighthouse_delta["scores"]["accessibility_delta"])

        # LH scan data
        elif 'lighthouse_average' in e['data_type']:
            title = 'Lighthouse Average'
            data = str(item.lighthouse["scores"]["average"])
        elif 'seo' in e['data_type']:
            title = 'SEO'
            data = str(item.lighthouse["scores"]["seo"])
        elif 'pwa' in e['data_type']:
            title = 'PWA'
            data = str(item.lighthouse["scores"]["pwa"])
        elif 'crux' in e['data_type']:
            title = 'CRUX'
            data = str(item.lighthouse["scores"]["crux"])
        elif 'best_practices' in e['data_type']:
            title = 'Best Practices'
            data = str(item.lighthouse["scores"]["best_practices"])
        elif 'performance' in e['data_type']:
            title = 'Performance'
            data = str(item.lighthouse["scores"]["performance"])
        elif 'accessibility' in e['data_type']:
            title = 'Accessibility'
            data = str(item.lighthouse["scores"]["accessibility"])
        
        # yellowlab test data
        elif 'current_yellowlab_average' in e['data_type']:
            title = 'Yellow Lab Avg'
            data = str(item.yellowlab_delta["scores"]["current_average"])
        elif 'pageWeight_delta' in e['data_type']:
            title = 'Page Weight Delta'
            data = str(item.yellowlab_delta["scores"]["pageWeight_delta"])
        elif 'images_delta' in e['data_type']:
            title = 'Images Delta'
            data = str(item.yellowlab_delta["scores"]["images_delta"])
        elif 'domComplexity_delta' in e['data_type']:
            title = 'DOM Complexity Delta'
            data = str(item.yellowlab_delta["scores"]["domComplexity_delta"])
        elif 'javascriptComplexity_delta' in e['data_type']:
            title = 'JS Complexity Delta'
            data = str(item.yellowlab_delta["scores"]["javascriptComplexity_delta"])
        elif 'badJavascript_delta' in e['data_type']:
            title = 'Bad JS Delta'
            data = str(item.yellowlab_delta["scores"]["badJavascript_delta"])
        elif 'jQuery_delta' in e['data_type']:
            title = 'jQuery Delta'
            data = str(item.yellowlab_delta["scores"]["jQuery_delta"])
        elif 'cssComplexity_delta' in e['data_type']:
            title = 'CSS Complexity Delta'
            data = str(item.yellowlab_delta["scores"]["cssComplexity_delta"])
        elif 'badCSS_delta' in e['data_type']:
            title = 'Bad CSS Delta'
            data = str(item.yellowlab_delta["scores"]["badCSS_delta"])
        elif 'fonts_delta' in e['data_type']:
            title = 'Fonts Delta'
            data = str(item.yellowlab_delta["scores"]["fonts_delta"])
        elif 'serverConfig_delta' in e['data_type']:
            title = 'Server Configs Delta'
            data = str(item.yellowlab_delta["scores"]["serverConfig_delta"])

        # yellowlab scan data
        elif 'yellowlab_average' in e['data_type']:
            title = 'Yellow Lab Avg'
            data = str(item.yellowlab["scores"]["globalScore"])
        elif 'pageWeight' in e['data_type']:
            title = 'Page Weight'
            data = str(item.yellowlab["scores"]["pageWeight"])
        elif 'images' in e['data_type']:
            title = 'Images'
            data = str(item.yellowlab["scores"]["images"])
        elif 'domComplexity' in e['data_type']:
            title = 'DOM Complexity'
            data = str(item.yellowlab["scores"]["domComplexity"])
        elif 'javascriptComplexity' in e['data_type']:
            title = 'JS Complexity'
            data = str(item.yellowlab["scores"]["javascriptComplexity"])  
        elif 'badJavascript' in e['data_type']:
            title = 'Bad JS'
            data = str(item.yellowlab["scores"]["badJavascript"])
        elif 'jQuery' in e['data_type']:
            title = 'jQuery'
            data = str(item.yellowlab["scores"]["jQuery"])
        elif 'cssComplexity' in e['data_type']:
            title = 'CSS Complexity'
            data = str(item.yellowlab["scores"]["cssComplexity"])
        elif 'badCSS' in e['data_type']:
            title = 'Bad CSS'
            data = str(item.yellowlab["scores"]["badCSS"])
        elif 'fonts' in e['data_type']:
            title = 'Fonts'
            data = str(item.yellowlab["scores"]["fonts"])
        elif 'serverConfig' in e['data_type']:
            title = 'Server Configs'
            data = str(item.yellowlab["scores"]["serverConfig"])
        
        # image data
        elif 'avg_image_score' in e['data_type']:
            title = 'Avg Image Score'
            data = str(item.images_delta["average_score"])
        elif 'image_scores' in e['data_type']:
            title = 'List of Image Scores'
            data = str([i["score"] for i in item.images_delta["images"]])
        
        # logs data
        elif 'logs' in e['data_type']:
            title = 'Error Logs'
            data = str(len(item.logs))
        
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




def create_json_data(json_data: dict=None, item: object=None) -> dict: 
    """ 
    Builds an expression list (exp_list = []) based 
    on the passed 'item' and `Automation`.

    Expects: {
        'item'       :  object (Scan, Test, Testcase),
        'automation' :  object
    }

    Returns -> dict
    """

    # looping through json_data to 
    # update values with item.data
    for key in json_data:

        # high-level test score
        if 'test_score' == json_data[key]:
            json_data[key] = item.score
        elif 'current_health' == json_data[key]:
            json_data[key] = (float(item.lighthouse_delta["scores"]["average"]) + float(item.yellowlab_delta["scores"]["globalScore"])/2)
        elif 'avg_image_score' == json_data[key]:
            json_data[key] = item.images_delta["average_score"]
        elif 'image_scores' == json_data[key]:
            json_data[key] = [i["score"] for i in item.images_delta["images"]]

        # high-level scan score
        elif 'health' == json_data[key]:
            json_data[key] = (float(item.lighthouse["scores"]["average"]) + float(item.yellowlab["scores"]["globalScore"])/2)
        elif 'logs' == json_data[key]:
            json_data[key] = len(item.logs)

        # LH test data
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
        elif 'current_lighthouse_average' == json_data[key]:
            json_data[key] = item.lighthouse_delta["scores"]["current_average"]
        
        # LH scan data
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

        # YL test data
        elif 'current_yellowlab_average' == json_data[key]:
            json_data[key] = item.yellowlab_delta["scores"]["current_average"]
        elif 'pageWeight_delta' == json_data[key]:
            json_data[key] = item.yellowlab_delta["scores"]["pageWeight_delta"]
        elif 'images_delta' == json_data[key]:
            json_data[key] = item.yellowlab_delta["scores"]["images_delta"]
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
        
        # YL scan data
        elif 'yellowlab_average' == json_data[key]:
            json_data[key] = item.yellowlab["scores"]["globalScore"]
        elif 'pageWeight' == json_data[key]:
            json_data[key] = item.yellowlab["scores"]["pageWeight"]
        elif 'images' == json_data[key]:
            json_data[key] = item.yellowlab["scores"]["images"]
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

    # return updated json
    return json_data




def get_item(object_id: str=None) -> dict:
    """ 
    Tries to find an object that matches theh passed 'object_id'.

    Expects: {
        'object_id':  str,
    }

    Returns -> data: {
        'item'      : object (Scan, Test, Testcase),
        'item_type' : str,
        'success'   : bool
    }
    """

    # init item
    item = None
    item_type = ''
    success = False

    # check for item
    if not item:
        try:
            item = Test.objects.get(id=uuid.UUID(object_id))
            item_type = 'Test'
            success = True
        except:
            pass
    if not item:
        try:
            item = Scan.objects.get(id=uuid.UUID(object_id))
            item_type = 'Scan'
            success = True
        except:
            pass
    if not item:
        try:
            item = Testcase.objects.get(id=uuid.UUID(object_id))
            item_type = 'Testcase'
            success = True
        except:
            pass
    
    # format and return data
    data = {
        'item': item,
        'item_type': item_type, 
        'success': success
    }

    return data




def automation_email(email: str=None, automation_id: str=None, object_id: str=None) -> dict:
    """
    Sends an automation email to the User with 
    the passed 'email'

    Expects: {
        'email'         : str,
        'automation_id' : str,
        'object_id'     : str
    }

    Returns -> data: {
        'success': bool
    }
    """

    # check if data is present
    if email and automation_id:

        # get automation 
        automation = Automation.objects.get(id=automation_id)
        schedule = automation.schedule
    
        # getting object
        data = get_item(object_id=object_id)
        if not data['success']:
            return {'success': False}

        # getting object data
        item = data['item']
        item_type = data['item_type']

        # deciding if "page" or "site" scope
        if item_type == 'Testcase':
            url = item.site.site_url
            dash_link = f'{settings.CLIENT_URL_ROOT}/site/{str(item.site.id)}'
        else:
            url = item.page.page_url
            dash_link = f'{settings.CLIENT_URL_ROOT}/page/{str(item.page.id)}'

        # generating expressions from automation
        exp_list = create_exp(
            item=item, 
            automation=automation
        )['exp_list']

        # build email data
        object_url = f'{settings.CLIENT_URL_ROOT}/{item_type.lower()}/{str(item.id)}'
        subject = f'Alert for {url}'
        title = f'Alert for {url}'
        pre_header = f'Alert for {url}'
        pre_content = (
            f'Scanerr just finished running a {item_type} for {url}. ' 
            f'Below are the current stats:'
        )
        content = (
            f'This message was triggered by an automation you created. ' 
            f'You can change the automation and schedule in your '
            f'<a href="{dash_link}">dashboard</a>.'
        )

        context = {
            'title' : title,
            'subject': subject,
            'pre_header' : pre_header,
            'pre_content' : pre_content,
            'exp_list': exp_list,
            'object_url' : object_url,
            'home_page' : os.environ.get('CLIENT_URL_ROOT'),
            'button_text' : f'View {item_type}',
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




def automation_report_email(email: str=None, automation_id: str=None, object_id: str=None) -> dict:
    """
    Sends an automation report email to the User with 
    the passed 'email'

    Expects: {
        'email'         : str,
        'automation_id' : str,
        'object_id'     : str
    }

    Returns -> data: {
        'success': bool
    }
    """

    # check if data is present
    if email and automation_id:
        
        # retrieving user
        user = User.objects.get(email=email)

        # get automation and deciding if "page" or "site" scope
        automation = Automation.objects.get(id=automation_id)
        schedule = automation.schedule
        
        # get `Report` if exists
        try:
            report = Report.objects.get(id=uuid.UUID(object_id))
            item_type = 'Report'
            url = report.page.page_url
        except:
            return {'success': False}

        # build email data
        object_url = str(report.path)
        subject = f'Report for {url}'
        title = f'Report for {url}'
        pre_header = f'Report for {url}'
        pre_content = (
            f'Scanerr just finished creating a ' 
            f'<a href="{settings.CLIENT_URL_ROOT}/page/{str(report.page.id)}/report">Report</a> for {url}. '
            f'Please click the link below to access and download the PDF.'
        )
        content = (
            f'\nThis message was triggered by an automation created with Scanerr. ' 
            f'You can change the automation and schedule in your ' 
            f'<a href="{settings.CLIENT_URL_ROOT}/page/{str(report.page.id)}">dashboard</a>.'
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




def automation_webhook(
        request_type: str=None, 
        request_url: str=None, 
        request_data: dict=None,
        automation_id: str=None, 
        object_id: str=None,
    ) -> dict:
    """
    Sends a GET or POST request to the passed 'request_url'
    with the passed 'request_data'

    Expects: {
        'request_type'    : str, 
        'request_url'     : str, 
        'request_data'    : dict,
        'automation_id'   : str, 
        'object_id'       : str,
    }

    Returns -> data: {
        'success': bool
    }
    """

    # checking that data is present
    if request_type and automation_id and request_url and request_data and object_id:

        # deciding if "page" or "site" scope
        automation = Automation.objects.get(id=automation_id)
        schedule = automation.schedule

        # getting object
        data = get_item(object_id=object_id)
        if not data['success']:
            return {'success': False}

        # get object and type
        item = data['item']
        item_type = data['item_type']

        # deciding if "page" or "site" scope
        if item_type == 'Testcase':
            url = item.site.site_url
        else:
            url = item.page.page_url
        
        # building json
        pre_json_data = json.loads(request_data)
        json_data = create_json_data(pre_json_data, item)

        # send the request
        try:
            if request_type == 'POST':
                response = requests.post(request_url, data=json_data)
            elif request_data == 'GET':
                response = requests.get(request_url, params=json_data)
        except:
            return {'success': False}

        data = {
            'success': True
        }
    
    else:
        data = {
            'success': False
        }
        
    return data




def automation_phone(phone_number: str=None, automation_id: str=None, object_id: str=None) -> dict:
    """
    Sends an SMS alert to the passed 'phone_number' 
    with the `Automation` data 

    Expects: {
        'phone_number'    : str, 
        'automation_id'   : str, 
        'object_id'       : str,
    }

    Returns -> data: {
        'success': bool
    }
    """

    # checking if data is present
    if phone_number and automation_id and object_id:

        # getting schedule and automation
        automation = Automation.objects.get(id=automation_id)
        schedule = automation.schedule

        # getting object
        data = get_item(object_id=object_id)
        if not data['success']:
            return {'success': False}

        # get obj and type
        item = data['item']
        item_type = data['item_type']

        # deciding if "page" or "site" scope
        if item_type == 'Testcase':
            url = item.site.site_url
            dash_link = f'{settings.CLIENT_URL_ROOT}/site/{str(item.site.id)}'
        else:
            url = item.page.page_url
            dash_link = f'{settings.CLIENT_URL_ROOT}/page/{str(item.page.id)}'

        # build the exp_str
        exp_str = create_exp(item=item, automation=automation)['exp_str']

        # build message data
        object_url = f'{settings.CLIENT_URL_ROOT}/{item_type.lower()}/{item.id}'
        pre_content = (
            f'Scanerr just finished running a {item_type} for {url}. ' 
            f'Below are the current stats:\n\n{exp_str}\n'
            f'View {item_type}: {object_url}\n\n'
        )
        content = (
            f'This message was triggered by an automation you created. ' 
            f'You can change the automation and schedule in your dashboard: {dash_link}'
        )
        body = f'Hi there,\n\n{pre_content}{content}'
        account_sid = os.environ.get("TWILIO_SID")
        auth_token  = os.environ.get("TWILIO_AUTH_TOKEN")
        client = Client(account_sid, auth_token)

        # send message
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




def automation_slack(automation_id: str=None, object_id: str=None) -> dict:
    """
    Sends a Slack alert with the `Automation` data 

    Expects: {
        'automation_id'   : str, 
        'object_id'       : str,
    }

    Returns -> data: {
        'success': bool
    }
    """

    # check if data is present
    if automation_id and object_id:
        
        # getting schedule, account and automation
        automation = Automation.objects.get(id=automation_id)
        account = Account.objects.get(user=automation.user)
        schedule = automation.schedule

        # getting object
        data = get_item(object_id=object_id)
        if not data['success']:
            return {'success': False}

        # get obj and type
        item = data['item']
        item_type = data['item_type']

        # deciding if "page" or "site" scope
        if item_type == 'Testcase':
            url = item.site.site_url
            dash_link = f'{settings.CLIENT_URL_ROOT}/site/{str(item.site.id)}'
        else:
            url = item.page.page_url
            dash_link = f'{settings.CLIENT_URL_ROOT}/page/{str(item.page.id)}'

        # build exp_str
        exp_str = create_exp(item=item, automation=automation)['exp_str']

        # build message data
        object_url = f'{settings.CLIENT_URL_ROOT}/{item_type}/{item.id}'
        pre_content = (
            f'Scanerr just finished running a `{item_type}` for {url}. ' 
            f'Below are the current stats:\n\n```{exp_str}```\n'
            f'<{object_url}|*View {item_type}*>\n\n'
        )
        content = (
            f'This message was triggered by an automation you created. ' 
            f'You can change the automation and schedule in your '
            f'<{dash_link}|dashboard>.'
        )
        body = f'Hi there,\n\n{pre_content}{content}'
        token = account.slack['bot_access_token']
        channel = account.slack['slack_channel_id']
        client = WebClient(token=token) 

        # send message
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




def sendgrid_email(message_obj: dict=None) -> dict:
    """
    Tries to send an email via the SendGrid API.

    Expects the following:
        'message_obj': dict {
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

    Returns --> data: {
        'success': bool
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
        error = None
    except Exception as e:
        status = False
        error = e.message
        print(e.message)

    # formatting resposne
    data = {
        'success': status,
        'error': error
    }

    return data






