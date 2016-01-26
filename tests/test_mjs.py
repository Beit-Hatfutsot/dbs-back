import json

from fixtures import get_auth_header
from pytest_flask.plugin import client

def test_mjs(client, request, get_auth_header):
    # first let's clean test user's story
    res = client.post('/auth', data = '{"username": "tester@example.com", "password": "password"}')


    headers = [('Content-Type', 'application/json')]
    headers.append(get_auth_header)
    res = client.post('/mjs',
                headers = headers,
                data = 'photoUnits.123')
    assert res.status_code == 200
    res = client.get('/mjs', headers=headers)
    assert len(res.json['items']) == 1
    item = res.json['items'][0]
    assert item['_id'] == '123'
    assert item['branches'] == [False, False, False, False]

    res = client.post('/mjs/1/name', headers=headers,
                     data = 'mothers')
    assert res.status_code == 200
    res = client.get('/mjs', headers=headers)
    assert res.json['branches'] == ['mothers', '', '', '']
    # test illegal add - items must be first added to the root
    res = client.post('/mjs/1', headers=headers,
                     data = 'personalities.456')
    assert res.status_code == 400
    res = client.post('/mjs/1', headers=headers,
                     data = 'photoUnits.123')
    assert res.status_code == 200
    res = client.get('/mjs', headers=headers)
    assert len(res.json['items']) == 1
    item = res.json['items'][0]
    assert item['_id'] == '123'
    assert item['branches'] == [True, False, False, False]

    res = client.delete('/mjs/1/photoUnits.123', headers=headers)
    assert res.status_code == 200
    res = client.get('/mjs', headers=headers)
    assert len(res.json['items']) == 1
    item = res.json['items'][0]
    assert item['_id'] == '123'
    assert item['branches'] == [False, False, False, False]
    res = client.delete('/mjs/photoUnits.123', headers=headers)
    assert res.status_code == 200
    res = client.get('/mjs', headers=headers)
    assert len(res.json['items']) == 0
