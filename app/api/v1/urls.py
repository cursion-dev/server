from .billing import urls as billing_urls
from .auth import urls as auth_urls
from .ops import urls as ops_urls
from django.urls import path, include
from rest_framework import (
    routers, serializers, viewsets, 
)


urlpatterns = [
    path('billing/', include(billing_urls)),
    path('auth/', include(auth_urls)),
    path('ops/', include(ops_urls)),
]
