from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.core import serializers
from datetime import date, datetime, timedelta
from ...models import Account, Card, Site, Issue
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
        'name'              : <str> 'basic', 'pro', 'plus', 'custom' (REQUIRED)
        'interval'          : <str> 'month' or 'year' (REQUIRED)
        'price_amount'      : <int> 1000 == $10 (REQUIRED)
        'max_sites'         : <int> total # `Sites` per `Account` (REQUIRED)
        'max_pages'         : <int> total # `Pages` per `Site` (REQUIRED)
        'max_schedules'     : <int> total # `Schedules` per `Account` (REQUIRED)
        'retention_days'    : <int> total # days to keep data (REQUIRED)
        'testcases'         : <str> 'true' or 'false' (OPTIONAL)
        'scans_allowed'     : <int> total # of `Scans` per `Account` per month (OPTIONAL)
        'tests_allowed'     : <int> total # of `Tests` per `Account` per month (OPTIONAL)
        'testcases_allowed' : <int> total # of `Testcases` per `Account` per month (OPTIONAL)
        'meta'              : <dict> any extra data for the account (OPTIONAL)
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
    scans_allowed = int(request.data.get('scans_allowed'))
    tests_allowed = int(request.data.get('tests_allowed'))
    testcases_allowed = int(request.data.get('testcases_allowed'))
    meta = request.data.get('meta')
    
    # get user
    user = request.user

    # set defaults
    initial_call = True
    client_secret = None

    # build Stripe Product name
    product_name = f'{name.capitalize()}'

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
            scans_allowed=scans_allowed if scans_allowed is not None else 30, 
            tests_allowed=tests_allowed if tests_allowed is not None else 30, 
            testcases_allowed=testcases_allowed if testcases_allowed is not None else 15,
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
    create_or_update_account(
        user=user.id,
        id=account.id,
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
        scans_allowed = scans_allowed,
        tests_allowed = tests_allowed,
        testcases_allowed = testcases_allowed,
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




def calc_price(account: object=None) -> int:
    """ 
    Calculates a `price` based on `Account.max_sites` 
    and any `Account.meta.coupon` data.

    Expects: {
        'account': <object> (REQUIRED)
    } 
    
    Returns: 'price_amount' <int>
    """
    
    # get max_sites
    max_sites = account.max_sites

    # get account coupon
    discount = 1
    if account.meta.get('coupon'):
        discount = account.meta['coupon']['discount']
    
    # calculate 
    price = (
        (
            (-0.0003 * (max_sites ** 2)) + 
            (1.5142 * max_sites) + 325.2
        ) * 100
    )

    # apply discount
    price = price - (price * discount)

    # return price
    return int(price)




def get_stripe_hosted_url(request: object=None) -> object:
    """ 
    Creates either a new 'Stripe Checkout Session' 
    (allows customer to subscribe), or a 'Stripe Customer 
    Portal Session' (allows customer to manage existing subscription).
    Either session type with return a Stripe redirect url

    Expects: {
        'request' : <object> (REQUIRED)
    }
    
    Returns -> data: {
        'stripe_url': <str>
    }
    """

    # get account
    user = request.user
    account = Account.objects.get(user=user)

    # set default url
    stripe_url = None
    
    # create Product, Price, & Checkout Session
    if account.cust_id is None:

        # build product
        product_name = f'Enterprise'
        product = stripe.Product.create(name=product_name)

        # calc price_amount
        price_amount = calc_price(account=account)
        
        # create new Stripe Price 
        price = stripe.Price.create(
            product=product.id,
            unit_amount=price_amount,
            currency='usd',
            recurring={'interval': account.interval,},
        )

        # create Checkout Session
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': price.id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=f'{settings.CLIENT_URL_ROOT}/billing/update' +
            '?success=true&session_id={CHECKOUT_SESSION_ID}',
            cancel_url=f'{settings.CLIENT_URL_ROOT}/billing',
        )

        # setting stripe_url 
        stripe_url = checkout_session.url
    
    # create Portal Session
    if account.cust_id:
        portal_session = stripe.billing_portal.Session.create(
            customer=account.cust_id,
            return_url=f'{settings.CLIENT_URL_ROOT}/billing/update',
        )

        # setting stripe_url 
        stripe_url = portal_session.url

    # return response
    data = {'stripe_url': stripe_url}
    return Response(data, status=status.HTTP_200_OK)




def update_account_with_stripe_redirect(request: object=None) -> object:
    """ 
    Updates `Account` with new sub data from stripe redirect

    Expects: {
        'request' : <object> (REQUIRED)
    }
    
    Returns -> HTTP Response object
    """

    # get account
    account = Account.objects.get(user=request.user)
    cust_id = account.cust_id
    sub_id = account.sub_id

    # try to get session_id
    session_id = request.query_params.get('session_id')

    # if session_id - get customer, subscription
    if session_id:
        session = stripe.checkout.Session.retrieve(
            session_id
        )
        cust_id = session.customer
        sub_id = session.subscription

    # get current stripe sub object
    sub = stripe.Subscription.retrieve(
        sub_id
    )

    # get stripe product & price info
    plan = sub['items']['data'][0]['plan']
    product_id = plan['product']
    price_id = plan['id']
    price_amount = plan['amount']
    interval = plan['interval']

    # setting Account.active
    active = False if (sub['canceled_at'] or sub['pause_collection']) else True
    
    # get billing method info
    pay_method_id = sub.default_payment_method
    pay_method = stripe.PaymentMethod.retrieve(
        pay_method_id
    )

    # create or update Account card
    if not Card.objects.filter(account=account).exists():
        Card.objects.create(
            user            = request.user,
            account         = account,
            pay_method_id   = pay_method.id,
            brand           = pay_method.card.brand,
            exp_year        = pay_method.card.exp_year,
            exp_month       = pay_method.card.exp_month,
            last_four       = pay_method.card.last4
        )
    else:
        Card.objects.filter(account=account).update(
            user            = request.user,
            account         = account,
            pay_method_id   = pay_method.id,
            brand           = pay_method.card.brand,
            exp_year        = pay_method.card.exp_year,
            exp_month       = pay_method.card.exp_month,
            last_four       = pay_method.card.last4
        )

    # update `Account` with new Stripe info
    create_or_update_account(
        user         = request.user.id,
        id           = account.id,
        cust_id      = cust_id,
        sub_id       = sub_id,
        product_id   = product_id,
        price_id     = price_id,
        price_amount = price_amount,
        interval     = interval,
    )
    
    # equeting account data deletion
    if not active:
        cancel_subscription(account=account)

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
    }
    
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
            'usage': account.usage,
            'meta': account.meta,
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




def cancel_subscription(request: object=None, account: object=None) -> object:
    """ 
    Cancels the Stripe Subscription associated with the
    passed "user" and reverts the `Account` to a "free" plan
    
    Expects: {
        'request': object (OPTIONAL)
        'account': object (OPTIONAL)
    }

    Returns -> `Account` HTTP Response object or Bool `true`
    """

    # get user's account
    if request is not None:
        account = Account.objects.get(user=request.user)

    # update billing if accout is active
    if account.active == True:

        # canceling Stripe Subscription billing
        try:
            stripe.Subscription.cancel(
                account.sub_id,
            )
        except Exception as e:
            print(e)

        # update Account plan
        account.type = 'free'
        account.max_sites = 1
        account.max_schedules = 0
        account.max_pages = 1
        account.retention_days = '3'
        account.interval = 'month'
        account.price_amount = 0
        account.cust_id = None
        account.sub_id = None
        account.product_id = None
        account.price_id = None
        account.price_amount = None
        account.usage = {
            'scans': 0,
            'tests': 0,
            'testcases': 0,
            'scans_allowed': 30, 
            'tests_allowed': 30, 
            'testcases_allowed': 15,
        }
        account.meta['last_usage_reset'] = datetime.today().strftime('%Y-%m-%d %H:%M:%S.%f')

        # save Account
        account.save()

        # update user's card
        card = Card.objects.get(account=account)
        card.delete()
    
    # remove sites
    sites = Site.objects.filter(account=account)
    for site in sites:
        delete_site(id=site.id, account=account)
    
    # remove issues
    issues = Issue.objects.filter(account=account)
    for issue in issues:
        issue.delete()

    # serialize and return
    if request is not None:
        serializer_context = {'request': request,}
        serialized = AccountSerializer(account, context=serializer_context)
        data = serialized.data
        return Response(data, status=status.HTTP_200_OK)
    else:
        return True





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

            # clean product name & get interval
            product_name = invoice['lines']['data'][0]['description']
            product_name = product_name.split('1 × ')[1].split(' (')[0]
            interval = invoice['lines']['data'][0]['plan']['interval']

            # get end_date
            period_start = datetime.fromtimestamp(invoice.period_start)
            new = period_start + timedelta(days=30 if interval == 'month' else 365)
            period_end = int(new.timestamp())

            i_list.append({
                'id': invoice.id,
                'status': invoice.status,
                'price_amount': invoice.amount_paid,
                'created': invoice.created,
                'due_date': invoice.due_date,
                'customer_email': invoice.customer_email,
                'customer_name': invoice.customer_name,
                'product_name': product_name,
                'invoice_pdf': invoice.invoice_pdf,
                'number': invoice.number,
                'period_start': invoice.period_start,
                'period_end': period_end
            })
        
        # format response
        data = {
            'has_more': invoice_body.has_more,
            'data': i_list
        }
    
    # return response
    return Response(data, status=status.HTTP_200_OK)


