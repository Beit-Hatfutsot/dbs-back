import re
import json
import logging
import pytest

from pytest_flask.plugin import client

# The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

def test_api_public_view(client):
    res = client.get('/')
    assert res.json == {'access': 'public'}

def test_send_ticket(client, app):
    from bhs_api.user import send_ticket
    mail = app.extensions.get('mail')
    with mail.record_messages() as outbox:
        ticket = send_ticket({'email': 'ster@example.com', 'next': '/mjs'})
        assert len(outbox) == 1
        urls = re.findall('http\S+', outbox[0].body)
        assert len(urls) == 1
    res = client.get(urls[0], headers={'Accept': 'application/json'})
    assert res.status_code == 200
    assert res.json['meta']['code'] == 200
    token = res.json['response']['user']['authentication_token']
    res = client.get('/', headers={'Authentication-Token': token})
    assert "private" in res.data

def test_dummy_token(client):
    res = client.get('/', headers={'Authentication-Token': 'dfdfdfdf'})
    assert "public" in res.data

