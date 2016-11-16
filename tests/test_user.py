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

    mail = app.extensions.get('mail')
    with mail.record_messages() as outbox:
        ticket = client.post('/login',
                             data={'email': 'ster@example.com', 'next': '/mjs'})
        assert len(outbox) == 1
        urls = re.findall('http\S+', outbox[0].body)
    assert len(urls) == 1
    login_url = urls[0]
    res = client.get(login_url, headers={'Accept': 'application/json'})
    assert res.status_code == 200
    assert res.json['meta']['code'] == 200
    # test the token we got
    token = res.json['response']['user']['authentication_token']
    res = client.get('/', headers={'Authentication-Token': token})
    assert "private" in res.data
    # now get the user
    res = client.get('/user', headers={'Authentication-Token': token,
                                       'Referer': login_url})
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

def test_bad_next_login(client, app):
    ''' post a login with bad `next` and ensure the user has the default one '''

    mail = app.extensions.get('mail')
    with mail.record_messages() as outbox:
        ticket = client.post('/login',
                             data={'email': 'tanin@example.com', 'next': '/login/badwolf'})
        assert len(outbox) == 1
        urls = re.findall('http\S+', outbox[0].body)
    assert len(urls) == 1
    user = app.user_datastore.get_user('tanin@example.com')
    assert user.next == app.config['DEFAULT_NEXT']
    # cleanup
    app.user_datastore.delete_user(user)
