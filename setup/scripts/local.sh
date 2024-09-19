#!/bin/bash

# ensure you create $SCANERR_ROOT first:
#  echo 'export SCANERR_ROOT=<your/path/to/scanerr/root>' >> ~/.zshrc   (or ~/.bash_profile)

cd $SCANERR_ROOT/server &&
{   
    docker compose -f docker-compose.local.yml down &&
    docker volume rm server_app server_beat server_celery &&
    docker compose -f docker-compose.local.yml up --build
} || {
    docker volume rm server_app server_beat server_celery &&
    docker compose -f docker-compose.local.yml up --build
} || {
    docker compose -f docker-compose.local.yml up --build
}

