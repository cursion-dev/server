FROM python:3.8-alpine

ENV PYTHONUNBUFFERED 1
COPY ./requirements.txt /requirements.txt

# create the app user
RUN addgroup -S app && adduser -S app -G app

RUN apk add --update --no-cache postgresql-client jpeg-dev

RUN apk add --update --no-cache --virtual .tmp-build-deps \ 
    gcc libc-dev linux-headers postgresql-dev musl-dev zlib zlib-dev \
    wget curl unzip 
RUN pip install -r /requirements.txt
RUN apk del .tmp-build-deps
RUN apk --no-cache add curl

# installing chromium and chromium-chromedriver
RUN apk add --update --no-cache chromium chromium-chromedriver

# installing node and npm
RUN apk add --update nodejs npm

# installing lighthouse
RUN npm install -g lighthouse


RUN mkdir /app
COPY ./app /app
WORKDIR /app

# # chown all the files to the app user
# RUN chown -R app:app /app

# # change to the app user
# USER app