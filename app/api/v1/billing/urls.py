from django.urls import path
from . import views as views






urlpatterns = [
    path('setup-subscription', views.SetupSubscription.as_view(), name='setup_subscription'),
    path('complete-subscription', views.CompleteSubscription.as_view(), name='complete_subscription'),
    path('cancel-subscription', views.CancelSubscription.as_view(), name='cancel_subscription'),
    path('stripe-key', views.StripeKey.as_view(), name='stripe_key'),
    path('get-info', views.GetBillingInfo.as_view(), name='get_billing_info'),
    path('get-invoices', views.StripeInvoice.as_view(), name='stripe_invoices'),
    path('account-activation', views.AccountActivation.as_view(), name='account_activation')
]
