# pull main python image
FROM python:3.9-slim
ENV PYTHONUNBUFFERED 1

# increasing allocated memory to node
ENV NODE_OPTIONS=--max_old_space_size=20000
ENV NODE_OPTIONS="--max-old-space-size=20000"
ENV GENERATE_SOURCEMAP=false

# telling Puppeteer to skip installing Chrome
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true 

# telling phantomas where Chrome binary is and that we're in docker
ENV PHANTOMAS_CHROMIUM_EXECUTABLE=/usr/bin/chromium
ENV DOCKERIZED=yes

# Set up the Chromium environment
ENV XDG_CONFIG_HOME=/tmp/.chromium
ENV XDG_CACHE_HOME=/tmp/.chromium

# create the app user
RUN addgroup --system app && adduser --system app 

# installing python3 & pip
RUN apt-get update && apt-get install -y python3 python3-pip

# installing system deps
RUN apt-get update && apt-get install -y postgresql postgresql-client gcc \
    gfortran openssl libpq-dev curl libjpeg-dev chromium chromium-driver \ 
    libfontconfig firefox-esr

# installing google-chrome-stable
RUN curl -LO https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt-get install -y ./google-chrome-stable_current_amd64.deb
RUN rm google-chrome-stable_current_amd64.deb

# # installing gekodriver
# RUN curl -fL -o /tmp/geckodriver.tar.gz \
#     https://github.com/mozilla/geckodriver/releases/download/v0.34.0/geckodriver-v0.34.0-linux64.tar.gz 
# RUN tar -xzf /tmp/geckodriver.tar.gz -C /tmp/
# RUN chmod +x /tmp/geckodriver
# RUN mv /tmp/geckodriver /usr/local/bin/

# # Cleanup unnecessary stuff
# RUN apt-get purge -y --auto-remove

# installing node and npm --> n lts
RUN apt-get update && apt-get install nodejs npm -y --no-install-recommends \
    && npm install -g n \
    && n lts

# cleaning npm
RUN npm cache clean --force

# installing lighthouse
RUN npm install -g lighthouse@11.7.1 lighthouse-plugin-crux lodash yellowlabtools

# setting --no-sandbox & --disable-dev-shm-usage
RUN chromium --no-sandbox --version
RUN chromium --disable-dev-shm-usage  --version

# installing requirements
COPY ./setup/requirements/requirements.txt /requirements.txt
RUN python3 -m pip install -r /requirements.txt

# removing chromium config
RUN rm -rf ~/.config/chromium

# setting working dir
RUN mkdir /app
COPY ./app /app
WORKDIR /app

# setting ownership
RUN chown -R app:app /app
RUN chown -R app:app /usr/bin/chromium
RUN chown -R app:app /usr/bin/chromedriver
RUN chmod +x /usr/bin/chromedriver

# staring up services
COPY ./setup/scripts/remote-entrypoint.sh "/remote-entrypoint.sh"
ENTRYPOINT [ "/remote-entrypoint.sh" ]

