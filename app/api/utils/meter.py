from ..models import Account
from cursion import settings
import stripe






def meter_account(account_id: str=None, count: int=1) -> None:
    """ 
    Sends a `MeterEvent` request to Stripe to 
    track account usage

    Expects:
        'account_id' `<str>` (REQUIRED)   
        'count'      `<int>` (OPTIONAL)   

    Returns: None
    """

    # init Stripe client
    stripe.api_key = settings.STRIPE_PRIVATE

    # get account
    account = Account.objects.get(id=account_id)

    # send stripe request
    stripe.billing.MeterEvent.create(
        event_name  = 'tasks',
        payload     = {
            'stripe_customer_id': account.cust_id, 
            'value': count
        },
    )

    # return
    return None