from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.core import serializers
from ...models import Account, Card, Site
from ..ops.services import delete_site
from ..auth.services import create_or_update_account
from ..auth.serializers import AccountSerializer
from scanerr import settings
import stripe






# init Stripe client
stripe.api_key = settings.STRIPE_PRIVATE




def stripe_setup(request: object) -> object: 
    """ 
    Creates or updates the Stripe Customer, Product, 
    Price, & Subscription associated with the passed 
    "user" and `Account`

    Expects: {
        'name'           : <str> 'basic', 'pro', 'plus', 'custom' (OPTIONAL)
        'interval'       : <str> 'month' or 'year' (OPTIONAL)
        'price_amount'   : <int> 1000 == $10 (OPTIONAL)
        'max_sites'      : <int> total # `Sites` per `Account` (OPTIONAL)
        'max_pages'      : <int> total # `Pages` per `Site` (OPTIONAL)
        'max_schedules'  : <int> total # `Schedules` per `Account` (OPTIONAL)
        'retention_days' : <int> total # days to keep data (OPTIONAL)
        'testcases'      : <str> 'true' or 'false' (OPTIONAL)
        'meta'           : <dict> any extra data for the account (OPTIONAL)
    }
    
    Returns -> data: {
        'subscription_id' : Stripe subscription id,
        'client_secret' : Stripe subscription client_secret,
    }
    """ 
    
    # get request data
    name = request.data.get('name')
    interval = request.data.get('interval') # month or year
    price_amount = int(request.data.get('price_amount'))
    max_sites = int(request.data.get('max_sites'))
    max_pages = int(request.data.get('max_pages'))
    max_schedules = int(request.data.get('max_schedules'))
    retention_days = int(request.data.get('retention_days'))
    testcases = str(request.data.get('testcases', 'False'))
    meta = request.data.get('meta')
    
    # get user
    user = request.user

    # set defaults
    initial_call = True
    client_secret = None

    # build Stripe Product name
    product_name = f'{user.email}_{user.id}_{name}'

    # format testcase data
    if str(testcases).lower() == 'true':
        testcases = True
    if str(testcases).lower() == 'false':
        testcases = False

    # create new `Account` if none exists
    if not Account.objects.filter(user=user).exists():
        create_or_update_account(
            user=user,
            type=name,
            interval=interval,
            max_sites=max_sites,
            max_pages=max_pages,
            max_schedules=max_schedules,
            retention_days=retention_days,
            testcases=testcases, 
            meta=meta
        )

    # get account 
    account = Account.objects.get(user=user)
    
    # create new Stripe Customer & Product
    if account.cust_id is None:
        product = stripe.Product.create(name=product_name)
        customer = stripe.Customer.create(
            email=request.user.email,
            name=f'{user.first_name} {user.last_name}'
        )

    # update existing Stripe Customer & Product
    if account.cust_id is not None:
        initial_call = False
        product = stripe.Product.modify(account.product_id, name=product_name)
        customer = stripe.Customer.retrieve(account.cust_id)

    # create new Stripe Price 
    price = stripe.Price.create(
        product=product.id,
        unit_amount=price_amount,
        currency='usd',
        recurring={'interval': interval,},
    )

    # create new Stripe Subscription if none exists
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

    # update existing Stripe Subscription
    if account.sub_id is not None:
        sub = stripe.Subscription.retrieve(account.sub_id)
        subscription = stripe.Subscription.modify(
            sub.id,
            cancel_at_period_end=False,
            pause_collection='',
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

    # update `Account` with new Stripe info
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
        testcases = testcases,
        meta = meta
    )        

    # get client_secret from Stripe 
    # Subscription if Sub is new (i.e. initial_call == True)
    if initial_call:
        client_secret = subscription.latest_invoice.payment_intent.client_secret
    
    # format and return
    data = {
        'subscription_id' : subscription.id,
        'client_secret' : client_secret,
    }
    return Response(data, status=status.HTTP_200_OK)




def stripe_complete(request: object) -> object: 
    """ 
    Confirms the Stripe Payment intent after user 
    enters CC details on Scanerr.client - Also updates 
    `Account` payment method.

    Expects: {
        'payment_method' : <str> stripe payment method id from client (REQUIRED)
    
    Returns -> `Account` HTTP Response object
    """
    
    # get request data
    account = Account.objects.get(user=request.user)
    pay_method_id = request.data['payment_method']

    # get Stripe PaymentMethod object
    pay_method = stripe.PaymentMethod.retrieve(pay_method_id)

    # create new `Card` if none exists
    if Card.objects.filter(account=account).exists():
        
        # attached Stripe Customer to existing
        # Stripe PaymentMethod
        stripe.PaymentMethod.attach(
            pay_method_id,
            customer=account.cust_id,
        )

        # update Stripe Customer
        stripe.Customer.modify(
            account.cust_id,
            invoice_settings={
                'default_payment_method': pay_method.id,
            }
        )

        # update Stripe Subscription
        stripe.Subscription.modify(
            account.sub_id,
            default_payment_method=pay_method.id
        )
        
        # update `Card` object
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
        # update Stripe Subscription with 
        # new payment method
        stripe.Subscription.modify(
            account.sub_id,
            default_payment_method=pay_method_id
        )

        # create new `Card` object
        Card.objects.create(
            user = request.user,
            account = account,
            pay_method_id = pay_method.id,
            brand = pay_method.card.brand,
            exp_year = pay_method.card.exp_year,
            exp_month = pay_method.card.exp_month,
            last_four = pay_method.card.last4
        )

    # update account activation
    account.active = True
    account.save()

    # serialize and return
    serializer_context = {'request': request,}
    serialized = AccountSerializer(account, context=serializer_context)
    data = serialized.data
    return Response(data, status=status.HTTP_200_OK)




def get_billing_info(request: object) -> object: 
    """ 
    Gets the `Card`, `Account`, and slack info associated
    with the passed "user".

    Expects: {
        'request' : <object> (REQUIRED)
    
    Returns -> HTTP Response object
    """

    # get user and account
    user = request.user
    account = Account.objects.get(user=user)

    # set default
    card = None
        
    # get `Card` info if exists
    if Card.objects.filter(user=user).exists():
        _card = Card.objects.get(user=user)
        card = {
            'brand': _card.brand,
            'exp_year': _card.exp_year,
            'exp_month': _card.exp_month,
            'last_four': _card.last_four,
        }

    # format billing info
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
        },
    }
    
    # return data
    return Response(data, status=status.HTTP_200_OK)




def account_activation(request: object) -> object: 
    """ 
    Pauses or Activates the `Account` and billing 
    for the associated Stripe Subscription.

    Expects: {
        'request' : <object> (REQUIRED)
    
    Returns -> `Account` HTTP Response object
    """

    # get user's Account
    account = Account.objects.get(user=request.user)
    
    # setting default
    active = None

    # pause billing  & `Account`
    if account.active == True:
        stripe.Subscription.modify(
            account.sub_id,
            pause_collection={
                'behavior': 'mark_uncollectible',
                },
        )
        active = False

    # activate billing & `Account`
    else:
        stripe.Subscription.modify(
            account.sub_id,
            pause_collection='',
        )
        active = True

    # save updates
    account.active = active
    account.save()

    # serialize and return
    serializer_context = {'request': request,}
    serialized = AccountSerializer(account, context=serializer_context)
    data = serialized.data
    return Response(data, status=status.HTTP_200_OK)



def cancel_subscription(request: object) -> object:
    """ 
    Cancels the Stripe Subscription associated with the
    passed "user" and reverts the `Account` to a "free" plan
    
    Expects: {
        'request': object
    }

    Returns -> `Account` HTTP Response object
    """

    # get user's account
    account = Account.objects.get(user=request.user)

    # update billing if accout is active
    if account.active == True:

        # pause Stripe Subscription billing
        stripe.Subscription.modify(
            account.sub_id,
            pause_collection={
                'behavior': 'mark_uncollectible',
            },
        )

        # update Account plan
        account.type = 'free'
        account.max_sites = 1
        account.max_schedules = 0
        account.max_pages = 1
        account.retention_days = '3'
        account.interval = 'month'
        account.price_amount = 0
        account.testcases = False

        # save Account
        account.save()
    
    # remove sites
    sites = Site.objects.filter(account=account)
    for site in sites:
        delete_site(request=request, id=site.id)

    # serialize and return
    serializer_context = {'request': request,}
    serialized = AccountSerializer(account, context=serializer_context)
    data = serialized.data
    return Response(data, status=status.HTTP_200_OK)




def get_stripe_invoices(request: object) -> object:
    """ 
    Gets a list of Stripe Invoice objects associated with the 
    passed "user" `Account`
    
    Expects: {
        'request': object
    }

    Returns -> data: {
        'has_more': <bool> true if more than 10
        'data': <list> of invoice objects
    }
    """

    # get user's account
    account = Account.objects.get(user=request.user)

    # setting defaults
    data = {"message": "no Account found"}
    i_list = []
    
    # check that Account has a Stripe Customer
    if account.cust_id is not None:

        # retrieve Stripe Invoices
        invoice_body = stripe.Invoice.list(
            customer=account.cust_id,
        )
        
        # build list of Stripe Invice objects
        for invoice in invoice_body.data:
            i_list.append({
                'id': invoice.id,
                'status': invoice.status,
                'price_amount': invoice.amount_paid,
                'created': invoice.created
            })
        
        # format response
        data = {
            'has_more': invoice_body.has_more,
            'data': i_list
        }
    
    # return response
    return Response(data, status=status.HTTP_200_OK)



