import pytest

from pytest_flask.plugin import client, config

# The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

# The documentation for advanced pytest fixtures use is at
# http://pytest.org/latest/fixture.html#fixture

@pytest.fixture
def get_auth_header(client):
    '''Asks the api for a JWT token and returns auth header.
    Uses the client fixture'''

    res = client.post('/auth', data = '{"username": "dannybmail@gmail.com", "password": "password"}')
    parsed_res = res.json
    token = parsed_res['token']
    auth_header_tuple = ('Authorization', 'Bearer ' + token)
    print 'Got jwt token ' + token
    return auth_header_tuple


def test_api_public_view(client):
    res = client.get('/')
    assert res.json == {'access': 'public'}

def test_api_private_view(client, get_auth_header):
    'Uses the JWT token obtained from get_auth_header fixture'
    headers = [get_auth_header]
    res = client.get('/private', headers=headers)
    assert res.json == {'access': 'private'}

def test_api_jwt_auth(client):
    res = client.post('/auth', data = '{"username": "dannybmail@gmail.com", "password": "password"}')
    parsed_res = res.json
    assert parsed_res.has_key('token')
