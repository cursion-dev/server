from django.core.mail import send_mail, send_mass_mail
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from datetime import date
import os, operator
from ...models import *
from django.utils.html import strip_tags
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from ...utils.alerts import sendgrid_email
from scanerr import settings




def send_reset_link(email):
    if User.objects.filter(email=email).exists():
        user = User.objects.get(email=email)
        token = RefreshToken.for_user(user)
        access_token = str(token.access_token)
        reset_link = str(os.environ.get('CLIENT_URL_ROOT') + '/reset-password?token='+access_token)
        subject = 'Rest Password'
        title = 'Reset Password'
        pre_header = 'Reset Password'
        pre_content = 'Click the link below to reset your password.'

        subject = subject
        context = {
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

        sendgrid_email(message_obj=context)

        # html_message = render_to_string('api/alert_with_button.html', context)
        # plain_message = strip_tags(html_message)
        # send_mail(
        #     from_email = os.getenv('EMAIL_HOST_USER'),
        #     subject = subject,
        #     message = plain_message,
        #     recipient_list = [email],
        #     html_message = html_message,
        #     fail_silently = True,
        # )

        data = {
            'success': True
        }
    
    else:
        data = {
            'success': False
        }
        
    return data







def send_invite_link(member):
    if Member.objects.filter(email=member.email, status="pending").exists():
        member = Member.objects.get(email=member.email)
        link = f'{os.environ.get("CLIENT_URL_ROOT")}/account/join?team={member.account.id}&code={member.account.code}&member={member.id}&email={member.email}'
        subject = 'Scanerr Invite'
        title = 'Scanerr Invite'
        pre_header = 'Scanerr Invite'
        pre_content = f'A user with the email "{member.account.user.username}" invited you to join their Team on Scanerr. Now just click the link below to accept the invite!'

        subject = subject
        context = {
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
        
        sendgrid_email(message_obj=context)

        # html_message = render_to_string('api/alert_with_button.html', context)
        # plain_message = strip_tags(html_message)
        # send_mail(
        #     from_email = os.getenv('EMAIL_HOST_USER'),
        #     subject = subject,
        #     message = plain_message,
        #     recipient_list = [member.email],
        #     html_message = html_message,
        #     fail_silently = True,
        # )

        data = {
            'success': True
        }
    
    else:
        data = {
            'success': False
        }
        
    return data





def send_remove_alert(member):
    if Member.objects.filter(email=member.email, status="removed").exists():
        member = Member.objects.get(email=member.email)
        subject = 'Removed From Account'
        title = 'Removed From Account'
        pre_header = 'Removed From Account'
        pre_content = f'A user with the email "{member.account.user.username}" removed you from their Team on Scanerr. Please let us know if there\'s been a mistake.'

        subject = subject
        context = {
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

        sendgrid_email(message_obj=context)

        # html_message = render_to_string('api/alert_no_button.html', context)
        # plain_message = strip_tags(html_message)
        # send_mail(
        #     from_email = os.getenv('EMAIL_HOST_USER'),
        #     subject = subject,
        #     message = plain_message,
        #     recipient_list = [member.email],
        #     html_message = html_message,
        #     fail_silently = True,
        # )

        data = {
            'success': True
        }
    
    else:
        data = {
            'success': False
        }
        
    return data