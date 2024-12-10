#!/bin/bash

# spin up server in local or remote env
if [[ $1 == *"server"* ]]
  then 
    if [[ $2 == *"local"* ]]
      then
        python3 manage.py wait_for_db && 
        python3 manage.py migrate --no-input &&
        python3 manage.py create_admin &&
        python3 manage.py create_tasks &&
        python3 manage.py driver_test &&
        python3 manage.py runserver 0.0.0.0:8000
    fi
    if [[ $2 == *"remote"* ]]
      then
        python3 manage.py wait_for_db && 
        python3 manage.py migrate --no-input &&
        python3 manage.py create_admin &&
        python3 manage.py create_tasks &&
        python3 manage.py driver_test &&
        gunicorn --timeout 1000 --graceful-timeout 1000 --keep-alive 3 --log-level debug cursion.wsgi:application --bind 0.0.0.0:8000
    fi
    if [[ $2 == *"stage"* ]]
    then
      python3 manage.py wait_for_db && 
      python3 manage.py makemigrations --no-input &&
      python3 manage.py migrate --no-input
    fi
fi

# spin up celery
if [[ $1 == *"celery"* ]]
  then
    python3 manage.py wait_for_db && 
    echo "pausing for migrations to complete..." && sleep 7s &&
    celery -A cursion worker -E --loglevel=info -O fair
fi

# spin up celery beat
if [[ $1 == *"beat"* ]]
  then
    python3 manage.py wait_for_db &&
    echo "pausing for migrations to complete..." && sleep 7s &&
    celery -A cursion beat --scheduler django --loglevel=info
fi

