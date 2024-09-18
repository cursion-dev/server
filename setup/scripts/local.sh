#!/bin/bash

cd $HOME/documents/coding/scanerr/server &&
{   
    docker compose -f docker-compose.local.yml down &&
    docker volume rm server_app server_beat server_celery &&
    docker compose -f docker-compose.local.yml up --build
} || {
    docker compose -f docker-compose.local.yml up --build
}

