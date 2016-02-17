import json

import pytest
from fixtures import get_auth_header
from pytest_flask.plugin import client

@pytest.fixture
def tester_headers(client, get_auth_header):
    headers = [('Content-Type', 'application/json')]
    headers.append(get_auth_header)
    return headers

def test_mjs_in_user_data(client, request, tester_headers):
    res = client.get('/user',
                     headers=tester_headers)
    assert 'story_items' in res.json
    assert len(res.json['story_branches']) == 4

def test_add_item_to_mjs(client, request, tester_headers):
    res = client.post('/mjs',
                headers = tester_headers,
                data = 'photoUnits.123')
    assert res.status_code == 200
    assert len(res.json['story_items']) == 1
    item = res.json['story_items'][0]
    assert item['id'] == 'photoUnits.123'
    assert res.json['story_branches'] == 4*['']

def test_mjs_rename_branch(client, tester_headers):
    res = client.post('/mjs/1/name', headers=tester_headers,
                     data = 'mothers')
    assert res.status_code == 200
    assert res.json['story_branches'] == ['mothers', '', '', '']


def test_illegal_add_to_branch(client, request, tester_headers):
    res = client.post('/mjs/1', headers=tester_headers,
                     data = 'personalities.456')
    assert res.status_code == 400

def test_add_to_branch(client, request, tester_headers):
    res = client.post('/mjs/1', headers=tester_headers,
                     data = 'photoUnits.123')
    assert res.status_code == 200
    assert len(res.json['story_items']) == 1
    item = res.json['story_items'][0]
    assert item['id'] == 'photoUnits.123'
    assert item['in_branch'] == [True, False, False, False]

def test_delete_from_branch(client, request, tester_headers):
    res = client.delete('/mjs/1/photoUnits.123', headers=tester_headers)
    assert res.status_code == 200
    assert len(res.json['story_items']) == 1
    item = res.json['story_items'][0]
    assert item['id'] == 'photoUnits.123'
    assert item['in_branch'] == [False, False, False, False]

def test_delete_item_from_story(client, request, tester_headers):
    res = client.delete('/mjs/photoUnits.123', headers=tester_headers)
    assert res.status_code == 200
    assert len(res.json['story_items']) == 0
