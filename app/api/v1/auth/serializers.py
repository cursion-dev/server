from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.settings import api_settings
from django.contrib.auth.models import update_last_login
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User
from django.shortcuts import render
from ...models import (Test, Site, Scan, Account, Member)
from django.urls import path, include
from rest_framework import routers, serializers, viewsets
from rest_framework.fields import UUIDField

kwargs = {
    'allow_null': False, 
    'read_only': True, 
    'pk_field': UUIDField(format='hex_verbose')
    }



class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'is_active', 'date_joined', 'last_login']



class LoginSerializer(TokenObtainPairSerializer):

    def validate(self, attrs):
        data = super().validate(attrs)

        refresh = self.get_token(self.user)
        api_token = Token.objects.get(user=self.user)

        data['user'] = UserSerializer(self.user).data
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)
        data['api_token'] = api_token.key

        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, self.user)

        return data


class RegisterSerializer(UserSerializer):
    password = serializers.CharField(max_length=128, min_length=8, write_only=True, required=True)
    email = serializers.EmailField(required=True, write_only=True, max_length=128)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'is_active', 'date_joined', 'last_login']

    def create(self, validated_data):
        try:
            user = User.objects.get(email=validated_data['email'])
        except ObjectDoesNotExist:
            user = User.objects.create_user(**validated_data)
        return user



class AccountSerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    id = serializers.PrimaryKeyRelatedField(**kwargs)

    class Meta:
        model = Account
        fields = ['id', 'active', 'time_created', 'type',
        'cust_id', 'sub_id', 'product_id', 'price_id', 'slack',
        'user',
        ]



class MemberSerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    account = serializers.PrimaryKeyRelatedField(source='account.id', **kwargs)
    id = serializers.PrimaryKeyRelatedField(**kwargs)

    class Meta:
        model = Member
        fields = ['id', 'status', 'time_created', 'type',
        'email', 'type', 'user', 'account',
        ]


        