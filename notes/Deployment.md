# Scanerr Deployment (single Server)
- [Scanerr Deployment (single Server)](#scanerr-deployment-single-server)
  - [Environment](#environment)
  - [Local](#local)
  - [Remote](#remote)
  - [Scripts](#scripts)
    - [Install and run Docker in Containers](#install-and-run-docker-in-containers)
    - [Get \& Set Node Memory:](#get--set-node-memory)
    - [Clean up Docker leftovers on Server](#clean-up-docker-leftovers-on-server)


&nbsp;
 
---
&nbsp;

## Environment

Prior to running app, configure all env's located in the /env directory. There are example .env files for both production and local environments marked `.env.dev.example` and `.env.prod.example`. Prior to running the app, be sure to update with your unique keys, domains, passwords, etc, and remove the `.example` extention from the files.  **Never store actual .env's in a repo.** Things to change:
- high level django configs
- admin credentials 
- email credentials
- database configs
- google API keys
- stripe keys
- OAuth keys
- twilio credentials
- slack credentials
- s3 remote storage credentials

&nbsp;
 
---
&nbsp;

## Local
Install and run locally on your machine in a dev environment.

> Ensure you have Docker and Docker-desktop installed and running on your machine prior to this step.

```shell
$ pip3 install virtualenv
$ virtualenv appenv
$ source appenv/bin/activate
$ mkdir app
$ git clone https://github.com/Scanerr-io/server.git
```
*Spin-up the application*
```shell
$ docker compose -f docker-compose.local.yml up --build
```
*Spin-down the application*
```shell
$ docker compose -f docker-compose.local.yml down
```

&nbsp;
 
---
&nbsp;

## Remote
Install and deploy remotely in a production environment.

> Ensure you have Docker installed and running on your server prior to this step.

*Server configurations for Ubuntu 20.04*
``` shell
$ ssh root@your_server_ip
# apt update
# apt upgrade
# adduser {user}
# usermod -aG sudo {user}
# ufw allow OpenSSH
# ufw enable
# su {user}
```

*Add user to docker group*
```shell
$ sudo usermod -aG docker {user}
$ newgrp docker 
```

*Generate SSH keys for GitHub*
``` shell
$ ssh-keygen -t ed25519 -C "your_github_email@example.com"
```
- press `Enter` 3 times
```shell
$ eval "$(ssh-agent -s)"
$ ssh-add ~/.ssh/id_ed25519
$ cat ~/.ssh/id_ed25519.pub
```
- copy key to clipboard and paste in GitHub


*Add ssh_key.pub to {user} authorized_keys*
```shell
$ {your_ssh_key.pub} >> ~/.ssh/authorized_keys
```


*Create a dir to clone the app into*
``` shell
$ cd ~
$ mkdir app
$ cd app
$ git clone git@github.com:Scanerr-io/server.git
```
*Spin-up the application*
```shell
$ docker compose -f docker-compose.prod.yml up -d --build
```
*Spin-down the application*
```shell
$ docker compose -f docker-compose.prod.yml down
```
*Spin-down the application and removes the volumes*
```shell
$ docker-compose -f docker-compose.prod.yml down -v
```



&nbsp;

---

&nbsp;

## Scripts

*ssh into container*
``` shell
$ docker exec -it <container:id> /bin/sh
```


### Install and run Docker in Containers
```shell
sed -i 's/ulimit -Hn/# ulimit -Hn/g' /etc/init.d/docker;
service docker start &&
sleep 10 &&
docker run -d --privileged --restart unless-stopped -p 8383:8383 scanerr/ylt &&
```


### Get & Set Node Memory:
Get Current Memory
```shell
node -e 'console.log(`Node RAM space: ${v8.getHeapStatistics().heap_size_limit/(1024*1024)}`)'
```
Set New Memory
```shell
export NODE_OPTIONS="--max-old-space-size=4080" # Increase to 4 GB
export NODE_OPTIONS="--max-old-space-size=5120" # Increase to 5 GB
export NODE_OPTIONS="--max-old-space-size=6144" # Increase to 6 GB
export NODE_OPTIONS="--max-old-space-size=7168" # Increase to 7 GB
export NODE_OPTIONS="--max-old-space-size=8192" # Increase to 8 GB
```


### Clean up Docker leftovers on Server
```shell
docker system prune --all --force --volumes
```