FROM python:2.7-alpine

RUN apk add --update \
    build-base curl jpeg-dev libxml2-dev libxml2 libxslt-dev libxslt \
    libstdc++ libffi-dev zlib-dev openssl-dev git

ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH .

COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt

RUN mkdir -p /mojp
COPY . /mojp/
WORKDIR /mojp

ENTRYPOINT ["/mojp/docker-entrypoint.sh"]

VOLUME /etc/bhs
