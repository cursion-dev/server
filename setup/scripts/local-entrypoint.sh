#!/bin/bash

# spin up app in local env
if [[ $1 == *"app"* ]]
then 
  python3 manage.py wait_for_db && 
  python3 manage.py makemigrations  --no-input &&
  python3 manage.py migrate --no-input &&
  python3 manage.py collectstatic --no-input &&
  python3 manage.py create_admin &&
  python3 manage.py driver_test &&
  python3 manage.py runserver 0.0.0.0:8000
fi

# spin up celery in local env
if [[ $1 == *"celery"* ]]
then
  python3 manage.py wait_for_db && 
  echo "pausing for migrations to complete..." && sleep 7s &&
  celery -A scanerr worker --beat --scheduler django --loglevel=info
fi

# spin up celery beat in remote env
if [[ $1 == *"beat"* ]]
then
  python3 manage.py wait_for_db &&
  echo "pausing for migrations to complete..." && sleep 7s &&
  celery -A scanerr beat --scheduler django --loglevel=info
fi