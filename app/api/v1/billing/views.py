from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status
from django.contrib.auth.models import User
from django.core import serializers
from django.forms.models import model_to_dict
from ...models import Account, Card, Site
from ..ops.services import delete_site
from ..auth.services import create_or_update_account
from datetime import timedelta, datetime
from scanerr import settings
import os, stripe, json 




class StripeKey(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):  
        key = settings.STRIPE_PUBLIC
        data = {'key': key,}
        return Response(data, status=status.HTTP_200_OK)




class CreateCustomer(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):  
        stripe.api_key = settings.STRIPE_PRIVATE
        customer = stripe.Customer.create(email=request.user.email)
        
        account = Account.objects.create(
            user=request.user, 
            cust_id=customer.id
        )

        data = customer.__dict__
        
        return Response(data, status=status.HTTP_200_OK)



class CreateProduct(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):  
        name = request.data['name']
        stripe.api_key = settings.STRIPE_PRIVATE
        product = stripe.Product.create(name=name)
        
        account = Account.objects.get(user=request.user)
        account.product_id = product.id
        account.save()
           
        data = product.__dict__
        
        return Response(data, status=status.HTTP_200_OK)



class CreatePrice(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):  
        account = Account.objects.get(user=request.user)
        price_amount = float(request.data['price_amount'])
        stripe.api_key = settings.STRIPE_PRIVATE
        price = stripe.Price.create(
            product=account.product_id,
            unit_amount=price_amount,
            currency='usd',
            recurring={
                'interval': 'month',
                'trial_period_days': 7,
            },
        )
        
        account.price_id = price.id
        account.save()

        data = price.__dict__
        
        return Response(data, status=status.HTTP_200_OK)



class CreateSubscription(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):  
        stripe.api_key = settings.STRIPE_PRIVATE
        account = Account.objects.get(user=request.user)
        subscription = stripe.Subscription.create(
            customer=account.cust_id,
            items=[{
                'price': account.price_id,
            }],
            payment_behavior='default_incomplete',
            expand=['latest_invoice.payment_intent'],
        )
        
        account.sub_id = subscription.id
        account.save()
        data = {
            'subscription_id' : subscription.id,
            'client_secret' : subscription.latest_invoice.payment_intent.client_secret
        }
        
        return Response(data, status=status.HTTP_200_OK)





class SetupSubscription(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):  
        stripe.api_key = settings.STRIPE_PRIVATE
        user = request.user
        name = request.data.get('name')
        interval = request.data.get('interval') # month or year
        product_name = str(user.email + '_' + str(user.id) + '_' + name)
        price_amount = int(request.data.get('price_amount'))
        max_sites = int(request.data.get('max_sites'))
        max_pages = int(request.data.get('max_pages'))
        max_schedules = int(request.data.get('max_schedules'))
        retention_days = int(request.data.get('retention_days'))
        testcases = str(request.data.get('testcases', False))
        initial_call = True
        client_secret = None

        if str(testcases).lower() == 'true':
            testcases = True
        if str(testcases).lower() == 'false':
            testcases = False

        if not Account.objects.filter(user=user).exists():
            create_or_update_account(
                user=user,
                type=name,
                interval=interval,
                max_sites=max_sites,
                max_pages=max_pages,
                max_schedules=max_schedules,
                retention_days=retention_days,
                testcases=testcases
            )

        account = Account.objects.get(user=user)
        
        if account.cust_id is None:
            product = stripe.Product.create(name=product_name)
            customer = stripe.Customer.create(
                email=request.user.email,
                name=f'{user.first_name} {user.last_name}'
            )

        if account.cust_id is not None:
            initial_call = False
            product = stripe.Product.modify(account.product_id, name=product_name)
            customer = stripe.Customer.retrieve(account.cust_id)

        price = stripe.Price.create(
            product=product.id,
            unit_amount=price_amount,
            currency='usd',
            recurring={'interval': interval,},
        )

        if account.sub_id is None:
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{
                    'price': price.id,
                }],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent'],
                # trial_period_days=7,
            )

        if account.sub_id is not None:
            sub = stripe.Subscription.retrieve(account.sub_id)
            subscription = stripe.Subscription.modify(
                sub.id,
                cancel_at_period_end=False,
                proration_behavior='create_prorations',
                items=[{
                    'id': sub['items']['data'][0].id,
                    'price': price.id,
                }],
                expand=['latest_invoice.payment_intent'],
            )
        
            # updating price defaults and archiving old price
            stripe.Product.modify(product.id, default_price=price,)
            stripe.Price.modify(account.price_id, active=False)


        Account.objects.filter(user=user).update(
            type = name,
            cust_id = customer.id,
            sub_id = subscription.id,
            product_id = product.id,
            price_id = price.id,
            interval = interval,
            max_sites = max_sites,
            max_pages = max_pages,
            price_amount = price_amount,
            max_schedules = max_schedules,
            retention_days = retention_days,
            testcases = testcases
        )        

        if initial_call:
            client_secret = subscription.latest_invoice.payment_intent.client_secret
        
        data = {
            'subscription_id' : subscription.id,
            'client_secret' : client_secret,
        }

        return Response(data, status=status.HTTP_200_OK)






class CompleteSubscription(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):  
        stripe.api_key = settings.STRIPE_PRIVATE
        account = Account.objects.get(user=request.user)
        pay_method_id = request.data['payment_method']
        if Card.objects.filter(account=account).exists():
            pay_method = stripe.PaymentMethod.retrieve(pay_method_id)

            stripe.PaymentMethod.attach(
                pay_method_id,
                customer=account.cust_id,
            )

            stripe.Customer.modify(
                account.cust_id,
                invoice_settings={
                    'default_payment_method': pay_method.id,
                }
            )

            stripe.Subscription.modify(
                account.sub_id,
                default_payment_method=pay_method.id
            )
            
            Card.objects.filter(account=account).update(
                user = request.user,
                account = account,
                pay_method_id = pay_method.id,
                brand = pay_method.card.brand,
                exp_year = pay_method.card.exp_year,
                exp_month = pay_method.card.exp_month,
                last_four = pay_method.card.last4
            )

        else:
            pay_method = stripe.PaymentMethod.retrieve(pay_method_id)

            stripe.Subscription.modify(
                account.sub_id,
                default_payment_method=pay_method.id
            )

            Card.objects.create(
                user = request.user,
                account = account,
                pay_method_id = pay_method.id,
                brand = pay_method.card.brand,
                exp_year = pay_method.card.exp_year,
                exp_month = pay_method.card.exp_month,
                last_four = pay_method.card.last4
                
            )
        

        card = Card.objects.get(account=account)
        account.active = True
        account.save()

        data = {
            'card': {
                'brand': card.brand,
                'exp_year': card.exp_year,
                'exp_month': card.exp_month,
                'last_four': card.last_four,
            },
            'plan': {
                'name': account.type,
                'active': account.active,
                'price_amount': account.price_amount,
                'interval': account.interval,
                'max_sites': account.max_sites,
                'max_pages': account.max_pages,
                'max_schedules': account.max_schedules,
                'retention_days': account.retention_days,
                'testcases': account.testcases,
                'slack': {
                    'slack_name': account.slack['slack_name'], 
                    'bot_user_id': account.slack['bot_user_id'], 
                    'slack_team_id': account.slack['slack_team_id'], 
                    'bot_access_token': account.slack['bot_access_token'], 
                    'slack_channel_id': account.slack['slack_channel_id'], 
                    'slack_channel_name': account.slack['slack_channel_name'],
                }
            },
        }


        return Response(data, status=status.HTTP_200_OK)






class GetBillingInfo(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post',]

    def post(self, request):  
        user = request.user
        if Account.objects.filter(user=user).exists():
            account = Account.objects.get(user=user)
            card = None
            
            if Card.objects.filter(user=user).exists():
                _card = Card.objects.get(user=user)
                card = {
                    'brand': _card.brand,
                    'exp_year': _card.exp_year,
                    'exp_month': _card.exp_month,
                    'last_four': _card.last_four,
                }

            data = {
                'card': card,
                'plan': {
                    'name': account.type,
                    'active': account.active,
                    'price_amount': account.price_amount,
                    'interval': account.interval,
                    'max_sites': account.max_sites,
                    'max_pages': account.max_pages,
                    'max_schedules': account.max_schedules,
                    'retention_days': account.retention_days,
                    'testcases': account.testcases,
                    'slack': {
                        'slack_name': account.slack['slack_name'], 
                        'bot_user_id': account.slack['bot_user_id'], 
                        'slack_team_id': account.slack['slack_team_id'], 
                        'bot_access_token': account.slack['bot_access_token'], 
                        'slack_channel_id': account.slack['slack_channel_id'], 
                        'slack_channel_name': account.slack['slack_channel_name'],
                    }
                },
            }

            return Response(data, status=status.HTTP_200_OK)

        else:
            return Response(status=status.HTTP_404_NOT_FOUND)




class AccountActivation(APIView):
    permission_classes = (IsAuthenticated,)
    https_method_names = ['post',]

    def post(self, request):
        account = Account.objects.get(user=request.user)
        stripe.api_key = settings.STRIPE_PRIVATE

        if account.active == True:
            stripe.Subscription.modify(
                account.sub_id,
                pause_collection={
                    'behavior': 'mark_uncollectible',
                    },
            )
            account.active = False
            account.save()
        else:
            stripe.Subscription.modify(
                account.sub_id,
                pause_collection='',
            )
            account.active = True
            account.save()

        
        card = Card.objects.get(account=account)

        data = {
                'card': {
                    'brand': card.brand,
                    'exp_year': card.exp_year,
                    'exp_month': card.exp_month,
                    'last_four': card.last_four,
                },
                'plan': {
                    'name': account.type,
                    'active': account.active,
                    'price_amount': account.price_amount,
                    'interval': account.interval,
                    'max_sites': account.max_sites,
                    'max_pages': account.max_pages,
                    'max_schedules': account.max_schedules,
                    'retention_days': account.retention_days,
                    'testcases': account.testcases,
                    'slack': {
                        'slack_name': account.slack['slack_name'], 
                        'bot_user_id': account.slack['bot_user_id'], 
                        'slack_team_id': account.slack['slack_team_id'], 
                        'bot_access_token': account.slack['bot_access_token'], 
                        'slack_channel_id': account.slack['slack_channel_id'], 
                        'slack_channel_name': account.slack['slack_channel_name'],
                    }
                },
            }

        return Response(data, status=status.HTTP_200_OK)
        





class CancelSubscription(APIView):
    permission_classes = (IsAuthenticated,)
    https_method_names = ['post',]

    def post(self, request):
        account = Account.objects.get(user=request.user)
        stripe.api_key = settings.STRIPE_PRIVATE

        if account.active == True:
            stripe.Subscription.modify(
                account.sub_id,
                pause_collection={
                    'behavior': 'mark_uncollectible',
                    },
            )
            account.type = 'free'
            account.max_sites = 1
            account.max_schedules = 0
            account.max_pages = 1
            account.retention_days = '3'
            account.interval = 'month'
            account.price_amount = 0
            account.testcases = False
            account.save()
        
        # remove sites
        sites = Site.objects.filter(account=account)
        # site_count = len(sites)
        for site in sites:
            delete_site(request=request, id=site.id)

        card = Card.objects.get(account=account)

        data = {
                'card': {
                    'brand': card.brand,
                    'exp_year': card.exp_year,
                    'exp_month': card.exp_month,
                    'last_four': card.last_four,
                },
                'plan': {
                    'name': account.type,
                    'active': account.active,
                    'price_amount': account.price_amount,
                    'interval': account.interval,
                    'max_sites': account.max_sites,
                    'max_pages': account.max_pages,
                    'max_schedules': account.max_schedules,
                    'retention_days': account.retention_days,
                    'testcases': account.testcases,
                    'slack': {
                        'slack_name': account.slack['slack_name'], 
                        'bot_user_id': account.slack['bot_user_id'], 
                        'slack_team_id': account.slack['slack_team_id'], 
                        'bot_access_token': account.slack['bot_access_token'], 
                        'slack_channel_id': account.slack['slack_channel_id'], 
                        'slack_channel_name': account.slack['slack_channel_name'],
                    }
                },
            }

        return Response(data, status=status.HTTP_200_OK)
        






class StripeInvoice(APIView):
    permission_classes = (IsAuthenticated,)
    https_method_names = ['get',]

    def get(self, request):
        account = Account.objects.get(user=request.user)
        stripe.api_key = settings.STRIPE_PRIVATE

        data = {"message": "no Account found"}
        if account.cust_id is not None:
            invoice_body = stripe.Invoice.list(
                customer=account.cust_id,
            )
            
            i_list = []
            for invoice in invoice_body.data:
                obj = {
                    'id': invoice.id,
                    'status': invoice.status,
                    'price_amount': invoice.amount_paid,
                    'created': invoice.created
                }
                i_list.append(obj)
            data = {
                'has_more': invoice_body.has_more,
                'data': i_list
            }

        return Response(data, status=status.HTTP_200_OK)

