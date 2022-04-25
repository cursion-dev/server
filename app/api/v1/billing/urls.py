from django.urls import path
from . import views as views




urlpatterns = [
    path('create-customer', views.CreateCustomer.as_view(), name='create_customer'),
    path('create-product', views.CreateProduct.as_view(), name='create_product'),
    path('create-price', views.CreatePrice.as_view(), name='create_price'),
    path('create-subscription', views.CreateSubscription.as_view(), name='create_subscription'),
    path('setup-subscription', views.SetupSubscription.as_view(), name='setup_subscription'),
    path('complete-subscription', views.CompleteSubscription.as_view(), name='complete_subscription'),
    path('stripe-key', views.StripeKey.as_view(), name='stripe_key'),
    path('get-info', views.GetBillingInfo.as_view(), name='get_billing_info'),
    path('account-activation', views.AccountActivation.as_view(), name='account_activation')

]
