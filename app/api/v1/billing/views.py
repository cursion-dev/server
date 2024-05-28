from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status
from .services import *
from scanerr import settings 






class StripeKey(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):
        data = {'key': settings.STRIPE_PUBLIC,}
        return Response(data, status=status.HTTP_200_OK)




class SetupSubscription(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):  
        response = stripe_setup(request)
        return response




class CompleteSubscription(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):  
        response = stripe_complete(request)
        return response




class GetBillingInfo(APIView):
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
        



class CancelSubscription(APIView):
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



