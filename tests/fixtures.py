import pytest
from flask import Response
from pytest_flask.plugin import client
from bhs_api import create_app
# The documentation for advanced pytest fixtures use is at
# http://pytest.org/latest/fixture.html#fixture

@pytest.fixture
def app():
    app, conf = create_app(testing=True)
    return app

@pytest.fixture
def get_auth_header(client):
    '''Asks the api for a JWT token and returns auth header.
    Uses the client fixture'''
    # We must use confusing email=username alias until the flask-jwt
    # author merges request #31
    # https://github.com/mattupstate/flask-jwt/pull/31
    res = client.post('/auth', data = '{"username": "tester@example.com", "password": "password"}')
    token = res.json['token']
    auth_header_tuple = ('Authorization', 'Bearer ' + token)
    print 'Got jwt token ' + token
    return auth_header_tuple



