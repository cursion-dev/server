#!/bin/bash

# ensure you create $CURSION_ROOT first:
# " echo 'export CURSION_ROOT=<your/path/to/cursion/server>' >> ~/.zshrc   (or ~/.bash_profile) " 

cd $CURSION_ROOT &&
{   
    docker compose -f docker-compose.yml down &&
    docker volume rm server_server server_beat server_celery &&
    docker compose -f docker-compose.yml up --build
} || {
    docker volume rm server_server server_beat server_celery &&
    docker compose -f docker-compose.yml up --build
} || {
    docker compose -f docker-compose.yml up --build
}



# cmd to run
# > source ./setup/scripts/local.sh