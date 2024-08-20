# pull main python image
FROM python:3.12-slim
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND noninteractive

LABEL Author="Scanerr" Support="hello@scanerr.io"

# create the app user
RUN addgroup --system app && adduser --system app 

# installing python3 & pip
RUN apt-get update && apt-get install -y python3 python3-pip

# installing system deps
RUN apt-get update && apt-get install -y postgresql postgresql-client gcc \
    gfortran openssl libpq-dev curl libjpeg-dev \ 
    libfontconfig firefox-esr apt-transport-https software-properties-common

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

# installing requirements
COPY ./setup/requirements/requirements.txt /requirements.txt
RUN python3 -m pip install -r /requirements.txt

# setting working dir
RUN mkdir /app
COPY ./app /app
WORKDIR /app

# setting ownership
RUN chown -R app:app /app
RUN chown -R app:app /usr/bin/firefox
RUN chown -R app:app /usr/bin/google-chrome-stable
RUN chown -R app:app /usr/bin/microsoft-edge-stable

# staring up services
COPY ./setup/scripts/entrypoint.sh "/entrypoint.sh"
ENTRYPOINT [ "/entrypoint.sh" ]

