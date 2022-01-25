FROM python:3.9-alpine

ENV PYTHONUNBUFFERED 1

# create the app user
RUN addgroup -S app && adduser -S app -G app

RUN apk add --update --no-cache postgresql-client jpeg-dev

RUN apk add --no-cache --update \
    python3 python3-dev gcc gfortran openssl

RUN apk add --update --no-cache --virtual .tmp-build-deps \ 
    gcc libc-dev linux-headers postgresql-dev musl-dev zlib zlib-dev \
    wget curl unzip build-base libffi libffi-dev

# installing chromium and chromium-chromedriver
RUN apk add --update --no-cache chromium chromium-chromedriver

# installing node and npm
RUN apk add --update nodejs npm

# installing lighthouse
RUN npm install -g lighthouse

# Install numpy
RUN apk add --update --no-cache py3-numpy

# Install scipy
RUN apk add --update --no-cache py3-scipy

# setting path for numpy and scipy
ENV PYTHONPATH /usr/lib/python3.9/site-packages

# super hacky BS to fix Alpine instalation issues with the data science packages
RUN find /usr/lib/python3.9/site-packages -iname "*.so" -exec sh -c 'x="{}"; mv "$x" "${x/cpython-39-x86_64-linux-musl./}"' \;

# Install sewar
RUN python3 -m pip install --no-deps sewar==0.4.4 

# install requirements
COPY ./requirements.txt /requirements.txt
RUN python3 -m pip install -r /requirements.txt
RUN apk del .tmp-build-deps
RUN apk --no-cache add curl


RUN mkdir /app
COPY ./app /app
WORKDIR /app

# # chown all the files to the app user
# RUN chown -R app:app /app

# # change to the app user
# USER app