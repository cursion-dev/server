# pull yellowlab image
FROM ousamabenyounes/yellowlabtools

# pull main python image
FROM python:3.9-slim
ENV PYTHONUNBUFFERED 1

# setting working dir
RUN mkdir /app
COPY ./app /app
WORKDIR /app

# create the app user
RUN addgroup --system app && adduser --system app 

# installing python3 & pip
RUN apt-get update && apt-get install -y python3 python3-pip

# installing system deps
RUN apt-get update && apt-get install -y postgresql postgresql-client gcc \
    gfortran openssl libpq-dev curl libjpeg-dev chromium chromium-driver \ 
    libfontconfig 

# installing node and npm --> n lts
RUN apt-get update && apt-get install nodejs npm -y --no-install-recommends \
    && npm install -g n \
    && n lts

# cleaning npm
RUN npm cache clean --force

# installing lighthouse
RUN npm install -g lighthouse lighthouse-plugin-crux lodash

# setting --no-sandbox & --disable-dev-shm-usage
RUN chromium --no-sandbox --version
RUN chromium --disable-dev-shm-usage  --version

# installing requirements
COPY ./requirements.txt /requirements.txt
RUN python3 -m pip install -r /requirements.txt

# setting ownership
RUN chown -R app:app /app
RUN chown -R app:app /usr/bin/chromium

# removing chromium config
RUN rm -rf ~/.config/chromium

# install docker
RUN curl -fsSL https://get.docker.com -o get-docker.sh && \ 
    sh get-docker.sh