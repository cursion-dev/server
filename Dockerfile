FROM python:3.9-slim
ENV PYTHONUNBUFFERED 1

# create the app user
RUN addgroup --system app && adduser --system app 

# installing python3 & pip
RUN apt-get update && apt-get install -y python3 python3-pip

# installing system deps
RUN apt-get update && apt-get install -y postgresql postgresql-client gcc \
    gfortran openssl libpq-dev curl libjpeg-dev chromium chromium-driver \ 
    libfontconfig

# installing node and npm
RUN apt-get update && apt-get install nodejs npm -y --no-install-recommends \
    && npm install -g n && n lts

RUN npm cache clean --force

# increasing allocated memory to node
RUN export NODE_OPTIONS="--max-old-space-size=4096"
ENV NODE_OPTIONS=--max_old_space_size=7000
ENV NODE_OPTIONS="--max-old-space-size=7000"

# installing lighthouse & yellowlabtools
RUN npm install -g lighthouse lighthouse-plugin-crux lodash yellowlabtools


# telling Puppeteer to skip installing Chrome
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD true 

# telling phantomas where Chromium binary is and that we're in docker
ENV PHANTOMAS_CHROMIUM_EXECUTABLE /usr/bin/chromium
ENV DOCKERIZED yes

# setting --no-sandbox for Phantomas 
RUN chromium --no-sandbox --version

# installing requirements
COPY ./requirements.txt /requirements.txt
RUN python3 -m pip install -r /requirements.txt

# setting working dir
RUN mkdir /app
COPY ./app /app
WORKDIR /app

# setting ownership
RUN chown -R app:app /app
RUN chown -R app:app /usr/bin/chromium