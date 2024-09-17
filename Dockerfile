# pull main python image
FROM python:3.12-slim

# adding labels
LABEL Author="Scanerr" Support="hello@scanerr.io"

# setting ENVs and Configs
ENV HOME=/app
ENV XDG_CACHE_HOME=$HOME/.cache
ENV DOCKERIZED=yes
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV MOZ_NO_REMOTE=1
ENV MOZ_DISABLE_AUTO_SAFE_MODE=1
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true 
ENV PHANTOMAS_CHROMIUM_EXECUTABLE=/usr/bin/google-chrome-stable
ENV PYTHONPATH="/app:$PYTHONPATH"

# create the app user
RUN addgroup --system app && adduser --system app

# install system dependencies and browsers
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql postgresql-client gcc make gfortran openssl libpq-dev \
    curl libsm6 libxrender1 libxext6 libgl1 nasm autoconf libtool \
    automake libjpeg-dev libglib2.0-0 libfreetype6 ca-certificates \
    libfontconfig apt-transport-https software-properties-common \
    firefox-esr && \
    curl -LO https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg && \
    install -o root -g root -m 644 microsoft.gpg /etc/apt/trusted.gpg.d/ && \
    sh -c 'echo "deb [arch=amd64] https://packages.microsoft.com/repos/edge stable main" > /etc/apt/sources.list.d/microsoft-edge.list' && \
    apt-get update && apt-get install -y microsoft-edge-stable && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* microsoft.gpg google-chrome-stable_current_amd64.deb

# install node and npm, lighthouse, yellowlabtools
RUN apt-get update && apt-get install nodejs npm -y --no-install-recommends && \
    npm install -g n && n lts && npm cache clean --force && \
    npm install -g lighthouse lighthouse-plugin-crux lodash yellowlabtools

# copy requirements and install dependencies as root temporarily
COPY ./setup/requirements/requirements.txt /requirements.txt
COPY ./app /app
WORKDIR /app
RUN mkdir -p .mozilla .cache && chown -R app:app /app

# Install Python dependencies as root (optional debug step)
USER root
RUN python3.12 -m pip install --no-cache-dir -r /requirements.txt

# Switch back to non-root user
USER app

# Verify installation
RUN python3.12 -m pip freeze

# set entrypoint and start services
COPY ./setup/scripts/entrypoint.sh "/entrypoint.sh"
ENTRYPOINT [ "/entrypoint.sh" ]
