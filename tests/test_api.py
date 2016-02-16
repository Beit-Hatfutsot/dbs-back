import json
import logging
import pytest

from pytest_flask.plugin import client
from fixtures import get_auth_header
from api import user_datastore

# The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

def test_api_public_view(client):
    res = client.get('/')
    assert res.json == {'access': 'public'}

def test_api_private_view(client, get_auth_header):
    'Uses the JWT token obtained from get_auth_header fixture'
    headers = [('Content-Type', 'application/json')]
    headers.append(get_auth_header)
    res = client.get('/private', headers=headers)
    assert res.json.has_key('access') and res.json['access'] == 'private'

def test_api_jwt_auth(client):
    res = client.post('/auth', data = '{"username": "tester@example.com", "password": "password"}')
    assert res.json.has_key('token')

#==================================================================================================================================#
# User API

def test_user(client, request):

    email = 'krakoziabr@example.com'
    new_email = 'shmakoziabr@example.com'

    def delete_test_user():
        test_user = user_datastore.get_user(email)
        if test_user: test_user.delete()
        test_user = user_datastore.get_user(new_email)
        if test_user: test_user.delete()


    def get_generic_auth_header(email, password):
        data =  json.dumps({'username': email, 'password': password})
        res = client.post('/auth', data=data)
        token = res.json['token']
        auth_header_tuple = ('Authorization', 'Bearer ' + token)
        return [auth_header_tuple]

    name = 'The evil one'
    password = 'kr0koftW!'
    route = '/user'
    new_password = 'kr0koftL!'
    # clean the db
    delete_test_user()

    logging.info('Creating a test user %s' % name)
    res = client.post('/user',
                      headers = {'Content-Type': 'application/json'},
                      data = json.dumps({'email': email,
                                         'name': name,
                                         'password': password}))
    parsed_res = res.json
    assert parsed_res['email'] == email

    auth_header = get_generic_auth_header(email, password)

    # change the email and password
    res = client.put(route,
                     headers=[('Content-Type', 'application/json')]+auth_header,
                     data=json.dumps({'email': new_email}))
    assert res.status == '200 OK'
    auth_header = get_generic_auth_header(new_email, password)
    res = client.put(route,
                     headers=[('Content-Type', 'application/json')]+auth_header,
                     data=json.dumps({'password': new_password}))
    assert res.status == '200 OK'
    headers = [('Content-Type', 'application/json')]
    headers = [('Content-Type', 'application/json')]
    auth_header = get_generic_auth_header(new_email, new_password)
    res = client.get(route,
                     headers=[('Content-Type', 'application/json')]+auth_header)
    assert res.status == '200 OK'
    assert res.json['email'] == new_email

    request.addfinalizer(delete_test_user)
  
