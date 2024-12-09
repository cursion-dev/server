import os, requests, json






def verify():
    username = os.environ.get('ADMIN_USER')
    email = os.environ.get('ADMIN_EMAIL')
    license_key = os.environ.get('LICENSE_KEY')
    api_root = os.environ.get('API_URL_ROOT')
    client_root = os.environ.get('CLIENT_URL_ROOT')
    url = 'https://cursion.dev/api/verify'

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

    # remove this !!!
    print(res)

    if res.get('verified'):
        return
    else:
        os.abort()