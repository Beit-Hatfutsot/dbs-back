# -*- coding: utf-8 -*-
''' Testing items' Slugs
    ===================
    The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

    The documentation for advanced pytest fixtures use is at
    http://pytest.org/latest/fixture.html#fixture
'''
import urllib2

import mongomock

from pytest_flask.plugin import client, config

from bhs_api.item import fetch_items, Slug

# TODO: fix for ES
def skip_test_single_collection(client, mock_db):
    res = fetch_items(['personality_tester'], mock_db)
    assert res[0]['Slug']['En'] == 'personality_tester'
    res = fetch_items([u'אישיות_בודק'], mock_db)
    assert res[0]['Slug']['En'] == 'personality_tester'

    res = fetch_items(['personality_tester','personality_another-tester'], mock_db)
    assert len(res) == 2
    assert res[1]['error_code'] == 403

    res = fetch_items(['personality_no-one'], mock_db)
    assert res[0]['error_code'] == 404

    res = fetch_items(['unknown_unknown'], mock_db)
    assert res[0]['error_code'] == 404

    res = fetch_items(['hello'], mock_db)
    assert res[0]['error_code'] == 404

# TODO: re-enable once persons data is in ES
def skip_test_person_collection(client, mock_db):

    res = fetch_items(['person_1;0.I2'], mock_db)
    assert res[0]['name_lc'][0] == 'tester'

    res = fetch_items(['person_1'], mock_db)
    assert res[0]['error_code'] == 404

def test_multi_collections(client):
    pass

def test_old_person_slug():
    s = Slug("person_8888.I1")
    assert s.local_slug == "8888;0.I1"
    assert s.full == "person_8888;0.I1"
