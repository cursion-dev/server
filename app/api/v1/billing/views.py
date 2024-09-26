from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status
from .services import *
from cursion import settings 






class StripeKey(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        data = {'key': settings.STRIPE_PUBLIC,}
        return Response(data, status=status.HTTP_200_OK)




class SubscriptionSetup(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):  
        response = stripe_setup(request)
        return response




class SubscriptionComplete(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):  
        response = stripe_complete(request)
        return response




class SubscriptionUrl(APIView):
    permission_classes = (IsAuthenticated,)
    https_method_names = ['get',]

    def get(self, request):
        response = get_stripe_hosted_url(request)
        return response




class SubscriptionUpdate(APIView):
    permission_classes = (IsAuthenticated,)
    https_method_names = ['get',]

    def get(self, request):
        response = update_account_with_stripe_redirect(request)
        return response




class BillingInfo(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):  
        response = get_billing_info(request)
        return response




class AccountActivation(APIView):
    permission_classes = (IsAuthenticated,)
    https_method_names = ['post',]

    def post(self, request):
        response = account_activation(request)
        return response
        



class SubscriptionCancel(APIView):
    permission_classes = (IsAuthenticated,)
    https_method_names = ['post',]

    def post(self, request):
        response = cancel_subscription(request)
        return response
        



class StripeInvoice(APIView):
    permission_classes = (IsAuthenticated,)
    https_method_names = ['get',]

    def get(self, request):
        response = get_stripe_invoices(request)
        return response




