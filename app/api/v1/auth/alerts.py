from django.core.mail import send_mail, send_mass_mail
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from datetime import date
import os, operator
from django.utils.html import strip_tags
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response




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
            'pre_header' : pre_header,
            'pre_content' : pre_content,
            'object_url' : reset_link,
            'home_page' : os.environ.get('CLIENT_URL_ROOT'),
            'button_text' : 'Rest my password',
            'content' : '',
            'signature' : '- Cheers!',
        }

        html_message = render_to_string('api/reset_password_email.html', context)
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