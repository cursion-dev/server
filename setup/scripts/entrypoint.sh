#!/bin/bash
# /entrypoint.sh


# spin up server in local, remote, or stage env
if [[ $1 == *"server"* ]]
  then 
    if [[ $2 == *"local"* ]]
      then
        python3 manage.py wait_for_db && 
        python3 manage.py migrate --no-input &&
        python3 manage.py create_admin &&
        python3 manage.py verify_account &&
        python3 manage.py create_tasks &&
        python3 manage.py test_driver &&
        python3 manage.py runserver 0.0.0.0:8000
    fi
    if [[ $2 == *"remote"* ]]
      then
        python3 manage.py wait_for_db && 
        python3 manage.py migrate --no-input &&
        python3 manage.py create_admin &&
        python3 manage.py verify_account &&
        python3 manage.py create_tasks &&
        python3 manage.py test_driver &&
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
    QUEUES=${2:-"scheduled,on_demand"}
    CONCURRENCY=${3:-${CELERY_CONCURRENCY:-""}}
    EXTRA_ARGS=""
    if [[ -n "$CONCURRENCY" ]]; then
      EXTRA_ARGS="--concurrency=$CONCURRENCY"
    fi
    celery -A cursion worker -E --loglevel=info -O fair --hostname=celery@$(hostname) -Q "$QUEUES" $EXTRA_ARGS
fi

# spin up celery beat
if [[ $1 == *"beat"* ]]
  then
    python3 manage.py wait_for_db &&
    echo "pausing for migrations to complete..." && sleep 7s &&
    celery -A cursion beat --scheduler django --loglevel=info
fi
