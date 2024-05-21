#!/bin/bash

# spin up app in remote env
if [[ $1 == *"app"* ]]
then 
  python3 manage.py wait_for_db && python3 manage.py makemigrations  --no-input &&
  python3 manage.py migrate --no-input &&
  python3 manage.py collectstatic --no-input &&
  python3 manage.py create_admin &&
  python3 manage.py driver_s_test &&
  python3 manage.py driver_p_test &&
  gunicorn  --timeout 1000 --graceful-timeout 1000 --keep-alive 3 --log-level debug scanerr.wsgi:application --bind 0.0.0.0:8000
fi

# spin up celery in remote env
if [[ $1 == *"celery"* ]]
then
  echo "pausing for migrations to complete..." && sleep 7s &&
  celery -A scanerr worker --beat --scheduler django --loglevel=info
fi
