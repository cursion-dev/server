FROM python:3.9-slim
ENV PYTHONUNBUFFERED 1

# increasing allocated memory to node
ENV NODE_OPTIONS=--max_old_space_size=262000
ENV NODE_OPTIONS="--max-old-space-size=262000"

# telling Puppeteer to skip installing Chrome
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD true 

# telling phantomas where Chromium binary is and that we're in docker
ENV PHANTOMAS_CHROMIUM_EXECUTABLE /usr/bin/chromium
ENV DOCKERIZED yes

# create the app user
RUN addgroup --system app && adduser --system app 

# installing python3 & pip
RUN apt-get update && apt-get install -y python3 python3-pip

# installing system deps
RUN apt-get update && apt-get install -y postgresql postgresql-client gcc \
    gfortran openssl libpq-dev curl libjpeg-dev chromium chromium-driver \ 
    libfontconfig 

# installing yellowlab-specific system deps
RUN apt-get update && apt-get install -y libfreetype6 \ 
    libatk-bridge2.0-0 gconf-service libasound2 \ 
    libatk1.0-0 libc6 libcairo2 libcups2 libdbus-1-3 libexpat1 libfontconfig1 \ 
    libgcc1 libgconf-2-4 libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 libnspr4 \ 
    libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 libxcb1 \ 
    libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 \ 
    libxrender1 libxss1 libxtst6 ca-certificates fonts-liberation libappindicator1 \ 
    libnss3 lsb-release libgbm1 xdg-utils wget -y --force-yes > /dev/null 2>&1

# installing node and npm
RUN apt-get update && apt-get install nodejs npm -y --no-install-recommends \
    && npm install -g n && n lts

# cleaning npm
RUN npm cache clean --force

# installing lighthouse & yellowlabtools
RUN npm install -g lighthouse lighthouse-plugin-crux lodash yellowlabtools@2.2.0

# setting --no-sandbox & --disable-dev-shm-usage for Phantomas 
RUN chromium --no-sandbox --version
RUN chromium --disable-dev-shm-usage  --version

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

# removing chromium config
RUN rm -rf ~/.config/chromium