#!/bin/bash
# /healthcheck.sh


# check celery worker
if [[ $1 == *"celery"* ]]
  then
    celery -A cursion inspect ping -d "celery@$(hostname)" --timeout=15 | grep -q OK
fi