from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.core import serializers
from datetime import date, datetime, timedelta
from ...models import (
    Account, Member, Card, Site, Issue, Schedule, Flow,
    get_meta_default, get_usage_default, Coupon
)
from ..ops.services import delete_site
from ..auth.services import create_or_update_account
from ..auth.serializers import AccountSerializer
from ...tasks import create_prospect
from cursion import settings
import stripe









def stripe_setup(request: object) -> object: 
    """ 
    Creates or updates the Stripe Customer, Product, 
    Price, & Subscription associated with the passed 
    "user" and `Account`

    Expects: {
        'name'                  : <str> 'free', 'cloud', 'selfhost', 'enterprise' (REQUIRED)
        'interval'              : <str> 'month' or 'year' (REQUIRED)
        'price_amount'          : <int> 1000 == $10 (REQUIRED)
        'task_amount'           : <int> 1000 == $10 (REQUIRED)
        'sites_allowed'         : <int> total # `Sites` per `Account` (REQUIRED)
        'pages_allowed'         : <int> total # `Pages` per `Site` (REQUIRED)
        'schedules_allowed'     : <int> total # `Schedules` per `Account` (REQUIRED)
        'retention_days'        : <int> total # days to keep data (REQUIRED)
        'caseruns_allowed'      : <int> total # of CaseRuns per `Account` per month (OPTIONAL)
        'scans_allowed'         : <int> total # of `Scans` per `Account` per month (OPTIONAL)
        'tests_allowed'         : <int> total # of `Tests` per `Account` per month (OPTIONAL)
        'caseruns_allowed'      : <int> total # of `CaseRuns` per `Account` per month (OPTIONAL)
        'flowruns_allowed'      : <int> total # of `FlowRuns` per `Account` per month (OPTIONAL)
        'nodes_allowed'         : <int> total # of `nodes` per `Flow` per month (OPTIONAL)
        'conditions_allowed'    : <int> total # of `conditons` per `Flow` (OPTIONAL)
        'meta'                  : <dict> any extra data for the account (OPTIONAL)
    }
    
    Returns -> data: {
        'subscription_id' : Stripe subscription id,
        'client_secret' : Stripe subscription client_secret,
    }
    """ 

    # init Stripe client
    stripe.api_key = settings.STRIPE_PRIVATE
    
    # get request data
    name = request.data.get('name')
    interval = request.data.get('interval', 'month') # month or year
    price_amount = int(request.data.get('price_amount'))
    task_amount = int(request.data.get('task_amount'))
    sites_allowed = int(request.data.get('sites_allowed'))
    pages_allowed = int(request.data.get('pages_allowed'))
    schedules_allowed = int(request.data.get('schedules_allowed'))
    retention_days = int(request.data.get('retention_days'))
    scans_allowed = int(request.data.get('scans_allowed'))
    tests_allowed = int(request.data.get('tests_allowed'))
    caseruns_allowed = int(request.data.get('caseruns_allowed'))
    flowruns_allowed = int(request.data.get('flowruns_allowed'))
    nodes_allowed = int(request.data.get('nodes_allowed'))
    conditions_allowed = int(request.data.get('conditions_allowed'))
    meta = request.data.get('meta', get_meta_default())
    
    # get user
    user = request.user

    # set defaults
    initial_call = True
    client_secret = None
    default_product = None
    default_price = None
    task_product = None
    task_price = None
    prices = []

    # build Stripe Default Product name
    default_product_name = f'{name.capitalize()}'

    # get account 
    account = Account.objects.get(user=user)

    # get cursion task meter
    meters = stripe.billing.Meter.list()
    meter = meters['data'][0]
    
    # create new Stripe Customer & Product
    if account.cust_id is None:
        default_product = stripe.Product.create(name=default_product_name)
        customer = stripe.Customer.create(
            email = request.user.email,
            name  = f'{user.first_name} {user.last_name}'
        )

    # update existing Stripe Customer & Product
    if account.cust_id is not None:
        initial_call = False
        default_product = stripe.Product.modify(account.product_id, name=default_product_name)
        customer = stripe.Customer.retrieve(account.cust_id)

    # create new Stripe Default Price for 
    default_price = stripe.Price.create(
        product     = default_product.id,
        unit_amount = price_amount,
        currency    = 'usd',
        recurring   = {'interval': interval,},
    )

    # add to prices
    prices.append(default_price)
    
    # create new Stripe Task Product & Price for CLOUD
    if name == 'cloud':

        # create task product
        task_product = stripe.Product.create(name='Tasks')

        # create task price
        task_price = stripe.Price.create(
            product        = task_product.id,
            unit_amount    = task_amount,
            currency       = 'usd',
            billing_scheme = 'per_unit',
            recurring      = {
                'usage_type' : 'metered', 
                'interval'   : 'month', 
                'meter'      : meter['id']
            },
        )

        # add to prices
        prices.append(task_price)

    # create new Stripe Subscription if none exists
    if account.sub_id is None:

        # build items
        items = []
        for price in prices:
            items.append({
                'price': price.id
            })

        # create subscription
        subscription = stripe.Subscription.create(
            customer            = customer.id,
            items               = items,
            payment_behavior    = 'default_incomplete',
            expand              = ['latest_invoice.payment_intent'],
            # trial_period_days   = 7,
        )

    # update existing Stripe Subscription
    if account.sub_id is not None:

        # get subscription
        sub = stripe.Subscription.retrieve(account.sub_id)

        # build items
        items = []
        i = 0
        for price in prices:
            items.append({
                'id'    : sub['items']['data'][i].id,
                'price' : price.id
            })
            i += 1
    
        # updating price defaults and archiving old default_price
        stripe.Product.modify(default_product.id, default_price=default_price,)
        stripe.Price.modify(account.price_id, active=False)

        # get old task_price if available
        if not task_price:
            for item in sub['items']['data']:
                if item['price']['recurring']['usage_type'] == 'metered':
                    task_price_id = item['price']['id']
                    
                    # archive old task price
                    stripe.Price.modify(task_price_id, active=False)
        
        # update subscription
        subscription = stripe.Subscription.modify(
            sub.id,
            cancel_at_period_end    = False,
            pause_collection        = '',
            proration_behavior      = 'create_prorations',
            items                   = items,
            expand                  = ['latest_invoice.payment_intent'],
        )

    # update `Account` with new Stripe info
    create_or_update_account(
        user                = user.id,
        id                  = account.id,
        type                = name,
        cust_id             = customer.id,
        sub_id              = subscription.id,
        product_id          = default_product.id,
        price_id            = default_price.id,
        price_amount        = price_amount,
        interval            = interval,
        sites_allowed       = sites_allowed,
        pages_allowed       = pages_allowed,
        schedules_allowed   = schedules_allowed,
        retention_days      = retention_days,
        scans_allowed       = scans_allowed,
        tests_allowed       = tests_allowed,
        caseruns_allowed    = caseruns_allowed,
        flowruns_allowed    = flowruns_allowed,
        nodes_allowed       = nodes_allowed,
        conditions_allowed  = conditions_allowed,
        meta                = meta
    )        

    # get client_secret from Stripe 
    # Subscription if Sub is new (i.e. initial_call == True)
    if initial_call:
        client_secret = subscription.latest_invoice.payment_intent.client_secret
    
    # format and return
    data = {
        'subscription_id'   : subscription.id,
        'client_secret'     : client_secret,
    }
    return Response(data, status=status.HTTP_200_OK)




def stripe_complete(request: object) -> object: 
    """ 
    Confirms the Stripe Payment intent after user 
    enters CC details on Cursion.client - Also updates 
    `Account` payment method.

    Expects: {
        'payment_method' : <str> stripe payment method id from client (REQUIRED)
    
    Returns -> `Account` HTTP Response object
    """

    # init Stripe client
    stripe.api_key = settings.STRIPE_PRIVATE
    
    # get request data
    user = request.user
    account = Account.objects.get(user=user)
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
            user            = user,
            account         = account,
            pay_method_id   = pay_method.id,
            brand           = pay_method.card.brand,
            exp_year        = pay_method.card.exp_year,
            exp_month       = pay_method.card.exp_month,
            last_four       = pay_method.card.last4
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
            user            = user,
            account         = account,
            pay_method_id   = pay_method.id,
            brand           = pay_method.card.brand,
            exp_year        = pay_method.card.exp_year,
            exp_month       = pay_method.card.exp_month,
            last_four       = pay_method.card.last4
        )

    # update account activation
    account.active = True
    account.save()

    # update prospect
    create_prospect.delay(user_email=str(user.email))

    # serialize and return
    serializer_context = {'request': request,}
    serialized = AccountSerializer(account, context=serializer_context)
    data = serialized.data
    return Response(data, status=status.HTTP_200_OK)




def calc_price(account: object=None) -> int:
    """ 
    Calculates a `price` based on `Account.sites_allowed` 
    and any `Account.meta.coupon` data.

    Expects: {
        'account': <object> (REQUIRED)
    } 
    
    Returns: 'price_amount' <int>
    """

    # init Stripe client
    stripe.api_key = settings.STRIPE_PRIVATE
    
    # get sites_allowed
    sites_allowed = account.usage['sites_allowed']

    # get account coupon
    discount = 0
    if account.meta.get('coupon'):
        discount = account.meta['coupon']['discount']

    # calculate
    price = (
        ( 
            (54.444 * (sites_allowed ** 0.4764))
        ) * 100
    )

    # apply discount
    price = price - (price * discount)

    # update for interval 
    price = round(price if account.interval == 'month' else (price * 10))

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

    # init Stripe client
    stripe.api_key = settings.STRIPE_PRIVATE

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

    # init Stripe client
    stripe.api_key = settings.STRIPE_PRIVATE

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
    
    # starting account data deletion
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

    # init Stripe client
    stripe.api_key = settings.STRIPE_PRIVATE

    # get user and account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # set defaults
    card = None
    estimated_cost = None

    # get current task usage overages if cloud
    if account.type == 'cloud':
        
        task_count = 0
        task_items = ['caseruns', 'flowruns', 'scans', 'tests']
        
        for item in task_items:
            overage = int(account.usage[item]) - int(account.usage[f'{item}_allowed'])
            if overage > 0:
                task_count += overage
        
        # calc current estimated costs
        estimated_cost = round(
            (account.price_amount) + 
            (
                (10 - (10 * account.meta['coupon']['discount'])) 
                * task_count
            )
        )

    # build plan
    plan = {
        'name': account.type,
        'active': account.active,
        'price_amount': account.price_amount,
        'interval': account.interval,
        'usage': account.usage,
        'meta': account.meta,
        'estimated_cost': estimated_cost
    }
        
    # get `Card` info if exists
    if Card.objects.filter(account=account).exists():
        _card = Card.objects.get(account=account)
        card = {
            'brand': _card.brand,
            'exp_year': _card.exp_year,
            'exp_month': _card.exp_month,
            'last_four': _card.last_four,
        }

    # format billing info
    data = {
        'card': card,
        'plan': plan
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

    # init Stripe client
    stripe.api_key = settings.STRIPE_PRIVATE

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

    # init Stripe client
    stripe.api_key = settings.STRIPE_PRIVATE

    # get user's account
    if request is not None:
        user = request.user
        account = Account.objects.get(user=user)

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
        account.interval = 'month'
        account.price_amount = 0
        account.cust_id = None
        account.sub_id = None
        account.product_id = None
        account.price_id = None
        account.price_amount = None
        account.usage = get_usage_default()
        account.meta = get_meta_default()

        # save Account
        account.save()

        # update user's card
        card = Card.objects.get(account=account)
        card.delete()
    
    # remove sites
    for site in Site.objects.filter(account=account):
        delete_site(id=site.id, user=user)

    # remove flows
    for flow in Flow.objects.filter(account=account):
        flow.delete()
    
    # remove issues
    for issue in Issue.objects.filter(account=account):
        issue.delete()

    # remove schedules
    for schedule in Schedule.objects.filter(account=account):
        schedule.delete()

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

    # init Stripe client
    stripe.api_key = settings.STRIPE_PRIVATE

    # get user's account
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # setting defaults
    data = {"message": "no Account found"}
    i_list = []
    
    # check that Account has a Stripe Customer
    if account.cust_id is not None:

        # retrieve Stripe Invoices
        invoice_body = stripe.Invoice.list(
            customer=account.cust_id,
        )

        # add to invoices list
        invoices = [i for i in invoice_body.data]

        # build list of Stripe Invice objects
        for invoice in invoices:

            # setting defaults
            items = []
            product_name = None
            interval = None

            # create line items
            for item in invoice['lines']['data']:

                # add item data
                items.append({
                    'amount': item['amount'],
                    'description': item['description'],
                    'period_start': item['period']['start'],
                    'period_end': item['period']['end'],
                    'quantity': item['quantity'],
                    'proration': item['proration'],
                    'unit_amount': item['price']['unit_amount']
                })

                # getting product name and interval if item 
                # is not proration
                if not item['proration']:
                    # get product_name
                    if 'cloud' in item['description'].lower():
                        product_name = 'Cloud'
                    if 'selfhost' in item['description'].lower():
                        product_name = 'Self Host'
                    if 'enterprise' in item['description'].lower():
                        product_name = 'Enterprise'
                    # get interval
                    interval = item['plan']['interval']
            
            # get end_date
            period_start = datetime.fromtimestamp(invoice.period_start)
            new = period_start + timedelta(days=30 if interval == 'month' else 365)
            period_end = int(new.timestamp())

            i_list.append({
                'id': invoice.id,
                'status': invoice.status,
                'subtotal': invoice.subtotal,
                'subtotal_excluding_tax': invoice.subtotal_excluding_tax,
                'price_amount': invoice.amount_paid,
                'created': invoice.created,
                'due_date': invoice.due_date,
                'customer_email': invoice.customer_email,
                'customer_name': invoice.customer_name,
                'product_name': product_name,
                'invoice_pdf': invoice.invoice_pdf,
                'number': invoice.number,
                'period_start': invoice.period_start,
                'period_end': period_end,
                'items': items
            })
        
        # format response
        data = {
            'has_more': invoice_body.has_more,
            'data': i_list
        }
    
    # return response
    return Response(data, status=status.HTTP_200_OK)




### ------ Begin Coupon Services ------ ###




def check_coupon(request: object) -> object:
    """ 
    Checks the passed 'query' against any existing
    `Coupon.codes`. If found, returns "success=True" 
    and the whole `Coupon` object

    Expects: {
        'request' : <object> (REQUIRED)
    }
    
    Returns -> HTTP Response of serialized `Coupon` objects
    """

    # get request data
    user = request.user
    member = Member.objects.get(user=user)
    account = member.account

    # get code
    code = request.query_params.get('code')

    # defaults
    coupon = None
    success = False

    # check code against Coupons
    if Coupon.objects.filter(code=code, status='active').exists():
        
        # get coupon object
        coup = Coupon.objects.get(code=code)
        success = True
        coupon = {
            'id': str(coup.id),
            'code': str(coup.code),
            'discount': float(coup.discount),
        }

    # return
    data = {
        'success': success,
        'coupon': coupon
    }

    # return response
    return Response(data, status=status.HTTP_200_OK) 





