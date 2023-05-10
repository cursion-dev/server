from rest_framework.response import Response
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.viewsets import ModelViewSet, ViewSet
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework import status, serializers
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.models import TokenUser
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer
from scanerr import settings
from django.shortcuts import redirect
from django.contrib.auth.models import User
from .alerts import send_reset_link
from ...models import Account, Member
from datetime import timedelta, datetime
from .services import *
import os, stripe, json 


class LoginViewSet(ModelViewSet, TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = (AllowAny,)
    http_method_names = ['post']

    def create(self, request, *args, **kwargs):
        
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class RegistrationViewSet(ModelViewSet, TokenObtainPairView):
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)
    http_method_names = ['post']

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        # creating API token
        api_token = Token.objects.create(user=user)
        res = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

        return Response({
            "user": serializer.data,
            "refresh": res["refresh"],
            "token": res["access"],
            "api_token": api_token.key,
        }, status=status.HTTP_201_CREATED)



class ApiToken(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get']

    def get(self, request):
        response = create_user_token(request)
        return response



class Verify(APIView):
    authentication_classes = []
    permission_classes = (AllowAny,)
    http_method_names = ['get']

    def get(self, request):
        response = t7e(request)
        return response



class RefreshViewSet(ViewSet, TokenRefreshView):
    permission_classes = (AllowAny,)
    http_method_names = ['post']

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        return Response(serializer.validated_data, status=status.HTTP_200_OK)



class GetResetLink(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]
    authentication_classes = []

    def post(self, request): 
        email = request.data['email']
        response = send_reset_link(email)
        
        if response['success'] == True:
            return Response(status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)



class ResetPassword(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]

    def post(self, request): 
        password = request.data['password']
        user = request.user 
        try:
            if validate_password(password, user=user) == None:
                user.set_password(password)
                user.save()
                return Response(status=status.HTTP_200_OK)
        except:
            return Response(status=status.HTTP_417_EXPECTATION_FAILED)
        




class UpdateUser(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]

    def post(self, request): 
        email = request.data['email']
        user = request.user
        try:
            if User.objects.filter(email=email).exists():
                return Response(status=status.HTTP_417_EXPECTATION_FAILED)
            user.username = email
            user.email = email
            user.save()
            data = UserSerializer(user).data
            return Response(data, status=status.HTTP_200_OK)
        except:
            return Response(status=status.HTTP_417_EXPECTATION_FAILED)




class GoogleLoginApi(APIView):
    authentication_classes = []
    permission_classes = (AllowAny,)
    class InputSerializer(serializers.Serializer):
        code = serializers.CharField(required=False)
        error = serializers.CharField(required=False)

    def get(self, request, *args, **kwargs):
        input_serializer = self.InputSerializer(data=request.GET)
        input_serializer.is_valid(raise_exception=True)

        validated_data = input_serializer.validated_data

        code = validated_data.get('code')
        error = validated_data.get('error')

        login_url = f'{settings.CLIENT_URL_ROOT}/login'

        if error or not code:
            params = urlencode({'error': error})
            return redirect(f'{login_url}?{params}')

        domain = settings.API_URL_ROOT
        api_uri = '/v1/auth/google'
        redirect_uri = f'{domain}{api_uri}'

        access_token = google_get_access_token(code=code, redirect_uri=redirect_uri)

        user_data = google_get_user_info(access_token=access_token)

        profile_data = {
            'email': user_data['email'],
            'first_name': user_data.get('given_name', ''),
            'last_name': user_data.get('family_name', ''),
        }


        user = user_get_or_create(**profile_data)
        confirm_url = jwt_login(user=user)

        return redirect(confirm_url)



class SlackOauth(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get', 'post']

    def post(self, request, *args, **kwargs):
        user = request.user
        response = slack_oauth_init(request, user)
        return response

    def get(self, request, *args, **kwargs):
        user = request.user
        response = slack_oauth_middleware(request, user)
        return response





class Account(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get', 'post']

    def post(self, request, *args, **kwargs ):
        response = create_or_update_account(request)
        return response

    def get(self, request, id=None, *args, **kwargs):
        response = get_account(request, id)
        return response



class AccountMembers(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get',]

    def get(self, request, id=None, *args, **kwargs):
        response = get_account_members(request, id)
        return response


class Member(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get', 'post']

    def post(self, request, *args, **kwargs ):
        response = create_or_update_member(request)
        return response

    def get(self, request, id=None, *args, **kwargs):
        response = get_member(request, id)
        return response

        
