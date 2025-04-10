from django.urls import path, include
from . import views as views
from rest_framework.authtoken.views import obtain_auth_token 
from rest_framework import (
    routers, serializers, viewsets, 
)






# refresh route
router = routers.DefaultRouter()
router.register(r'refresh', views.RefreshViewSet, basename='auth_refresh')




urlpatterns = [
    path('', include(router.urls)),
    path('login', views.Login.as_view(), name='login'),
    path('register', views.Register.as_view(), name='register'),
    path('login/', views.Login.as_view(), name='login'),
    path('register/', views.Register.as_view(), name='register'),
    path('api-auth', include('rest_framework.urls', namespace='rest_framework')),
    path('api-token-auth', obtain_auth_token, name='api_token_auth'),
    path('google', views.GoogleLoginApi.as_view(), name='auth_google'),
    path('get-reset-link', views.GetResetLink.as_view(), name='auth_get_reset_link'),
    path('reset-password', views.ResetPassword.as_view(), name='auth_reset_password'), 
    path('update-user', views.UpdateUser.as_view(), name='update_user'), 
    path('slack', views.SlackOauth.as_view(), name='auth_slack'),
    path('token', views.ApiToken.as_view(), name='token'),
    path('verify', views.Verify.as_view(), name='verify'),
    path('account', views.Account.as_view(), name='account'),
    path('account/<uuid:id>/members', views.AccountMembers.as_view(), name='account-members'),
    path('account/license', views.AccountLicense.as_view(), name='account-license'),
    path('member', views.Member.as_view(), name='member'),
    path('member/<uuid:id>', views.Member.as_view(), name='member-detail'),
    path('prospect', views.Prospect.as_view(), name='prospect'),
]