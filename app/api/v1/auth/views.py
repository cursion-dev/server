from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.viewsets import ModelViewSet, ViewSet
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status, serializers
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from django.shortcuts import redirect
from django.contrib.auth.models import User
from datetime import timedelta, datetime
from ...models import Account, Member
from scanerr import settings
from .services import *
import os, stripe, json






### ------ Begin User Views ------ ###




class Login(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]
    authentication_classes = []

    def post(self, request): 
        response = login_user(request=request)
        return response




class Register(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]
    authentication_classes = []

    def post(self, request): 
        response = register_user(request=request)
        return response




class RefreshViewSet(ViewSet, TokenRefreshView):
    permission_classes = (AllowAny,)
    http_method_names = ['post']

    def create(self, request, *args, **kwargs):
        
        # get request data
        serializer = self.get_serializer(data=request.data)

        # validate refresh token and create new access
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        # return response
        return Response(serializer.validated_data, status=status.HTTP_200_OK)




class GetResetLink(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]
    authentication_classes = []

    def post(self, request): 
        response = send_reset_email(request)




class ResetPassword(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['post',]

    def post(self, request): 
        response = update_password(request)
        return response
        



class UpdateUser(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request): 
        response = update_user(request)
        return response




class ApiToken(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get']

    def get(self, request):
        response = create_user_token(request)
        return response




### ------ Begin GoogleAuth Views ------ ###




class GoogleLoginApi(APIView):
    authentication_classes = []
    permission_classes = (AllowAny,)

    def get(self, request, *args, **kwargs):
        confirm_url = google_login(request)
        return redirect(confirm_url)




### ------ Begin Slack Views ------ ###




class SlackOauth(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ['get', 'post']

    def post(self, request, *args, **kwargs):
        response = slack_oauth_init(request)
        return response

    def get(self, request, *args, **kwargs):
        response = slack_oauth_middleware(request)
        return response




### ------ Begin Account Views ------ ###




class Account(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'post']

    def post(self, request):
        response = create_or_update_account(request)
        return response

    def get(self, request):
        response = get_account(request)
        return response




class AccountMembers(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get',]

    def get(self, request, *args, **kwargs):
        response = get_account_members(request)
        return response




class Member(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get', 'post']

    def post(self, request, *args, **kwargs ):
        response = create_or_update_member(request)
        return response

    def get(self, request, id=None, *args, **kwargs):
        response = get_member(request, id)
        return response

        


class Prospect(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['get',]

    def get(self, request):
        response = get_prospects(request)
        return response




class Verify(APIView):
    authentication_classes = []
    permission_classes = (AllowAny,)
    http_method_names = ['get']

    def get(self, request):
        response = t7e(request)
        return response






