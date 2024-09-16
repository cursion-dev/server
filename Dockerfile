# pull main python image
FROM python:3.12-slim

# adding labels
LABEL Author="Scanerr" Support="hello@scanerr.io"

# setting ENVs and Configs
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND noninteractive
ENV DOCKERIZED yes
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD true 
ENV PHANTOMAS_CHROMIUM_EXECUTABLE /usr/bin/google-chrome-stable
ENV MOZ_DISABLE_AUTO_SAFE_MODE 1
ENV MOZ_NO_REMOTE 1
ENV HOME /app
ENV XDG_CACHE_HOME $HOME/.cache

# create the app user
RUN addgroup --system app && adduser --system app

# installing system deps
RUN apt-get update && apt-get install -y postgresql postgresql-client gcc make \
    gfortran openssl libpq-dev curl libjpeg-dev libglib2.0-0 libsm6 libxrender1 \ 
    libxext6 libgl1 libfontconfig apt-transport-https software-properties-common \
    nasm autoconf libtool automake ca-certificates libfreetype6 

# installing firefox-esr
RUN apt-get update && apt-get install -y firefox-esr

# installing google-chrome-stable
RUN curl -LO https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb

# installing microsoft-edge-stable
RUN curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg && \
    install -o root -g root -m 644 microsoft.gpg /etc/apt/trusted.gpg.d/ && \
    sh -c 'echo "deb [arch=amd64] https://packages.microsoft.com/repos/edge stable main" > \
    /etc/apt/sources.list.d/microsoft-edge.list' && \
    apt-get update && apt-get install -y microsoft-edge-stable && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* microsoft.gpg

# installing node and npm
RUN apt-get update && apt-get install nodejs npm -y --no-install-recommends \
    && npm install -g n && n lts && npm cache clean --force

# installing lighthouse & lighthouse-plugin-crux
RUN npm install -g lighthouse lighthouse-plugin-crux

# installing lodash & yellowlabtools
RUN npm install -g lodash yellowlabtools

# installing requirements
COPY ./setup/requirements/requirements.txt /requirements.txt
RUN python3.12 -m pip install -r /requirements.txt

# setting working dir
COPY ./app /app
WORKDIR /app

# setting extra dirs
RUN mkdir -p /app/.mozilla \
    && mkdir -p /app/.cache

# setting ownership
RUN chown -R app:app /app
RUN chown -R app:app /usr/bin/firefox
RUN chown -R app:app /usr/bin/google-chrome-stable
RUN chown -R app:app /usr/bin/microsoft-edge-stable
RUN chown -R app:app /usr/local/bin/yellowlabtools
RUN chown -R app:app /usr/local/bin/lighthouse
RUN chown -R app:app /tmp
RUN chown -R app:app /app/api/migrations
RUN chmod -R 755 /app/api/migrations

# cleaning up
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# setting user
USER app

# staring up services
COPY ./setup/scripts/entrypoint.sh "/entrypoint.sh"
ENTRYPOINT [ "/entrypoint.sh" ]



