#!/bin/bash

# spin up app in local or remote env
if [[ $1 == *"app"* ]]
then 
  if [[ $2 == *"local"* ]]
  then
    python3 manage.py wait_for_db && 
    python3 manage.py migrate --no-input &&
    python3 manage.py collectstatic --no-input &&
    python3 manage.py create_admin &&
    python3 manage.py driver_test &&
    python3 manage.py runserver 0.0.0.0:8000
  fi
  if [[ $2 == *"remote"* ]]
    then
      python3 manage.py wait_for_db && 
      python3 manage.py migrate --no-input &&
      python3 manage.py collectstatic --no-input &&
      python3 manage.py create_admin &&
      python3 manage.py driver_test &&
      gunicorn --timeout 1000 --graceful-timeout 1000 --keep-alive 3 --log-level debug scanerr.wsgi:application --bind 0.0.0.0:8000
    fi
fi

# spin up celery
if [[ $1 == *"celery"* ]]
then
  python3 manage.py wait_for_db && 
  echo "pausing for migrations to complete..." && sleep 7s &&
  celery -A scanerr worker -E --loglevel=info -O fair
fi

# spin up celery beat
if [[ $1 == *"beat"* ]]
then
  python3 manage.py wait_for_db &&
  echo "pausing for migrations to complete..." && sleep 7s &&
  celery -A scanerr beat --scheduler django --loglevel=info
fi

