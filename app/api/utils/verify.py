import os, requests, json, signal
from cursion import settings






def verify():

    if os.environ.get('MODE') == 'selfhost':
        username = os.environ.get('ADMIN_USER')
        email = os.environ.get('ADMIN_EMAIL')
        license_key = os.environ.get('LICENSE_KEY')
        api_root = os.environ.get('API_URL_ROOT')
        client_root = os.environ.get('CLIENT_URL_ROOT')
        url = f'{settings.LANDING_API_ROOT}/ops/verify'

        headers = {
            "Content-Type": "application/json",
        }
        
        data = {
            "username": username,
            "email": email,
            "license_key": license_key,
            "api_root": api_root,
            "client_root": client_root
        }

        res = requests.get(
            url=url, 
            headers=headers, 
            params=data
        ).json()

        if res.get('verified'):
            return
        else:
            os.kill(os.getpid(), signal.SIGTERM)