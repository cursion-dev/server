# Scanerr Server (API repo)

[![Build Status](http://img.shields.io/travis/badges/badgerbadgerbadger.svg?style=flat-square)](https://api.scanerr.io)

This is the server repo for the Scanerr API, an error detection service designed to run front-end tests on web-apps and sites. This service is fully dockertized for local dev/testing as well as deployed environments. 

> This software is only intended for internal white-label use and is not licensed for redristibution. See LICENSE for more information.


Copyright © Scanerr 2023

---
&nbsp;

## Table of Contents
&nbsp;

#### Env's and deployment

- [Scanerr Server (API repo)](#scanerr-server-api-repo)
  - [Table of Contents](#table-of-contents)
      - [Env's and deployment](#envs-and-deployment)
  - [Environment](#environment)
  - [Local](#local)
  - [Remote](#remote)
  - [Scripts](#scripts)


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
$ docker compose up --build
```
*Spin-down the application*
```shell
$ docker compose up down
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
- copy key to clipboard and paste in GutHub


*Create a dir to clone the app into*
``` shell
$ cd ~
$ mkdir app
$ cd app
$ git clone https://github.com/Scanerr-io/server.git
```
*Spin-up the application*
```shell
$ docker-compose -f docker-compose.prod.yml up -d --build
```
*Spin-down the application*
```shell
$ docker-compose -f docker-compose.prod.yml down
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
