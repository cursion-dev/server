# pull main python image
FROM python:3.12-slim

# adding labels
LABEL Author="Cursion" Support="hello@cursion.dev"

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
ENV PYTHONPATH="$HOME:$PYTHONPATH"
ENV NODE_OPTIONS="--max-old-space-size=4080"
ENV DJANGO_ALLOWED_HOSTS="*"
ENV SECRET_KEY="abcdefghijklmno123456789"

# create the app user
RUN addgroup --system app && adduser --system app

# Clean cache to avoid issues
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# installing system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql \
    postgresql-client \
    gcc \
    make \
    gfortran \
    openssl \
    libpq-dev \
    curl \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1 \
    nasm \
    autoconf \
    libtool \
    automake \
    libjpeg-dev \
    libglib2.0-0 \
    libfreetype6 \
    ca-certificates \
    libfontconfig \
    apt-transport-https \
    software-properties-common
     
# installing firefox-esr
RUN apt-get update && apt-get install -y --no-install-recommends firefox-esr

# installing google-chrome-stable
RUN curl -LO https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb

# installing microsoft-edge-stable
RUN curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg && \
    install -o root -g root -m 644 microsoft.gpg /etc/apt/trusted.gpg.d/ && \
    sh -c 'echo "deb [arch=amd64] https://packages.microsoft.com/repos/edge stable main" > \
    /etc/apt/sources.list.d/microsoft-edge.list' && \
    apt-get update && apt-get install -y microsoft-edge-stable

# installing node and npm
RUN curl -fsSL https://deb.nodesource.com/setup_current.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g --no-cache n && \
    n lts

# installing lighthouse & lighthouse-plugin-crux
RUN npm install -g lighthouse lighthouse-plugin-crux

# installing lodash & yellowlabtools
RUN npm install -g lodash yellowlabtools

# copying & installing requirements
COPY ./setup/requirements/requirements.txt /requirements.txt
RUN python3.12 -m pip install -r /requirements.txt

# setting working dir
COPY ./app /app
WORKDIR /app

# setting browser cache dirs 
RUN mkdir -p .mozilla .cache

# setting ownership
RUN chown -R app:app /app
RUN chown -R app:app /usr/local/bin/lighthouse
RUN chown -R app:app /usr/local/bin/yellowlabtools

# writing migrations file
RUN python3.12 manage.py makemigrations --no-input

# collecting static assets
RUN python3.12 manage.py collectstatic --no-input

# cleaning up
RUN apt-get clean && rm -rf \
    /var/lib/apt/lists/* \
    /tmp/* \
    /var/tmp/* \
    microsoft.gpg

# setting final user
USER app

# copy healthcheck.sh
COPY ./setup/scripts/healthcheck.sh "/healthcheck.sh"

# staring up services
COPY ./setup/scripts/entrypoint.sh "/entrypoint.sh"
ENTRYPOINT [ "/entrypoint.sh" ]



