from .v1 import urls as v1_urls
from django.urls import path, include




urlpatterns = [
    path('v1/', include(v1_urls)),
]


