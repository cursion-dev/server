from django.urls import path
from . import views as views






urlpatterns = [
    path('stripe/key', views.StripeKey.as_view(), name='stripe_key'),
    path('invoices', views.StripeInvoice.as_view(), name='stripe_invoices'),
    path('info', views.BillingInfo.as_view(), name='billing_info'),
    path('subscription/setup', views.SubscriptionSetup.as_view(), name='subscription_setup'),
    path('subscription/complete', views.SubscriptionComplete.as_view(), name='subscription_complete'),
    path('subscription/cancel', views.SubscriptionCancel.as_view(), name='subscription_cancel'),
    path('subscription/update', views.SubscriptionUpdate.as_view(), name='subscription_update'),
    path('subscription/url', views.SubscriptionUrl.as_view(), name='subscription_url'),
    path('account/activation', views.AccountActivation.as_view(), name='account_activation')
]
