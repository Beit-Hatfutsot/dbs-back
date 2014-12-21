import json

import pytest

from pytest_flask.plugin import client, config

# The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

# The documentation for advanced pytest fixtures use is at
# http://pytest.org/latest/fixture.html#fixture

@pytest.fixture
def get_auth_header(client):
    '''Asks the api for a JWT token and returns auth header.
    Uses the client fixture'''

    res = client.post('/auth', data = '{"username": "tester@example.com", "password": "password"}')
    token = res.json['token']
    auth_header_tuple = ('Authorization', 'Bearer ' + token)
    print 'Got jwt token ' + token
    return auth_header_tuple


def test_api_public_view(client):
    res = client.get('/')
    assert res.json == {'access': 'public'}

def test_api_private_view(client, get_auth_header):
    'Uses the JWT token obtained from get_auth_header fixture'
    headers = []
    headers.append(get_auth_header)
    res = client.get('/private', headers=headers)
    assert res.json == {'access': 'private'}

def test_api_jwt_auth(client):
    res = client.post('/auth', data = '{"username": "tester@example.com", "password": "password"}')
    assert res.json.has_key('token')

#==================================================================================================================================#
# User API

def test_user(client, request):
    username = 'krakoziabr@example.com'
    password = 'kr0koftW!'
    route = '/user'
    new_email = 'shmakoziabr@example.com'
    new_password = 'kr0koftL!'

    print 'Creating test user %s' % username
    res = client.post('/user', data = json.dumps({'email': username,
                                                  'password': password}))
    parsed_res = res.json
    assert parsed_res['email'] == username

    def get_generic_auth_header(username, password):
        data =  json.dumps({'username': username, 'password': password})
        res = client.post('/auth', data=data)
        token = res.json['token']
        auth_header_tuple = ('Authorization', 'Bearer ' + token)
        return auth_header_tuple
    
    auth_header = get_generic_auth_header(username, password)    
    headers = []
    headers.append(auth_header)

    def user_get_self(username, password):
        headers = []
        auth_header = get_generic_auth_header(username, password)
        headers.append(auth_header)
        res = client.get(route, headers=headers)
        return res.json

    def user_email_change(new_email):
        data = json.dumps({'email': new_email})
        res = client.put(route, headers=headers, data=data)
        return res.json

    def user_password_change(new_password):
        data = json.dumps({'password': new_password})
        res = client.put(route, headers=headers, data=data)
        return res.json

    def delete_test_user():
        res = client.delete(route, headers=headers)
        assert res.json == {}

    user_email_change(new_email)
    assert user_get_self(new_email, password)['email'] == new_email
    user_password_change(new_password)
    assert user_get_self(new_email, new_password)['email'] == new_email

    request.addfinalizer(delete_test_user)
  
