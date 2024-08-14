from .v1 import urls as v1_urls
from django.urls import path, include
from django.views.generic.base import RedirectView




urlpatterns = [
    path('v1/', include(v1_urls)),
    path('', RedirectView.as_view(url='v1/auth/', permanent=False))
]


