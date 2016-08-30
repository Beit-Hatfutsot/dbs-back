import re
import json
import logging
import pytest
import hashlib

from pytest_flask.plugin import client

# The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

def test_api_public_view(client):
    res = client.get('/')
    assert res.json == {'access': 'public'}

def test_login_scenario(client, app):
    ''' login scenario, starting with sending the ticket '''
    from bhs_api.user import send_ticket
    mail = app.extensions.get('mail')
    with mail.record_messages() as outbox:
        ticket = client.post('/login',
                             data={'email': 'ster@example.com', 'next': '/mjs'})
        assert len(outbox) == 1
        urls = re.findall('http\S+', outbox[0].body)
    assert len(urls) == 1
    res = client.get(urls[0], headers={'Accept': 'application/json'})
    assert res.status_code == 200
    assert res.json['meta']['code'] == 200
    token = res.json['response']['user']['authentication_token']
    res = client.get('/', headers={'Authentication-Token': token})
    assert "private" in res.data
    # now get the user
    res = client.get('/user', headers={'Authentication-Token': token})
    assert res.status_code == 200
    assert res.json['email'] == 'ster@example.com'
    hash = res.json['hash']
    assert hash == hashlib.md5('ster@example.com').hexdigest()
    # now let's get the public stroy
    res = client.get('/v1/story/'+hash)
    assert res.status_code == 200
    assert res.json['hash'] == hash


def test_dummy_token(client):
    res = client.get('/', headers={'Authentication-Token': 'dfdfdfdf'})
    assert "public" in res.data

