FROM python:3.9-alpine

ENV PYTHONUNBUFFERED 1

# create the app user
RUN addgroup -S app && adduser -S app -G app

# installing postgres deps
RUN apk add --update --no-cache postgresql-client jpeg-dev

# installing python3
RUN apk add --no-cache --update \
    python3 python3-dev 

# installing env deps
RUN apk add --update --no-cache --virtual .tmp-build-deps \ 
    gcc libc-dev linux-headers postgresql-dev musl-dev zlib zlib-dev \
    build-base libffi libffi-dev fontconfig libjpeg-turbo-dev \
    ttf-freefont ca-certificates freetype freetype-dev harfbuzz nss \
    nasm git make g++ automake autoconf libtool gfortran openssl

# installing chromium and chromium-chromedriver
RUN apk add --update --no-cache chromium chromium-chromedriver

# installing node and npm
RUN apk add --update nodejs npm

# increasing allocated memory to node
RUN export NODE_OPTIONS="--max-old-space-size=2048"

# installing lighthouse
RUN npm install -g lighthouse

# installing yellowlabs tools
RUN npm install -g yellowlabtools

# telling Puppeteer to skip installing Chrome
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD true 

# telling phantomas where Chromium binary is and that we're in docker
ENV PHANTOMAS_CHROMIUM_EXECUTABLE /usr/bin/chromium-browser
ENV DOCKERIZED yes

# setting --no-sandbox for Phantomas 
RUN chromium-browser --no-sandbox --version

# inatalling numpy
RUN apk add --update --no-cache py3-numpy

# installing scipy
RUN apk add --update --no-cache py3-scipy

# setting path for numpy and scipy
ENV PYTHONPATH /usr/lib/python3.9/site-packages

# super hacky BS to fix Alpine instalation issues with the data science packages
RUN find /usr/lib/python3.9/site-packages -iname "*.so" -exec sh -c 'x="{}"; mv "$x" "${x/cpython-39-x86_64-linux-musl./}"' \;

# installing sewar
RUN python3 -m pip install --no-deps sewar==0.4.4 

# installing requirements
COPY ./requirements.txt /requirements.txt
RUN python3 -m pip install -r /requirements.txt
RUN apk del .tmp-build-deps

# setting working dir
RUN mkdir /app
COPY ./app /app
WORKDIR /app

# setting ownership
RUN chown -R app:app /app
RUN chown -R app:app /usr/bin/chromium-browser