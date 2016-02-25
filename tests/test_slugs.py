# -*- coding: utf-8 -*-
''' Testing items Slugs
    ===================
    The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

    The documentation for advanced pytest fixtures use is at
    http://pytest.org/latest/fixture.html#fixture
'''
import json
import urllib2

import pytest
import mongomock

from pytest_flask.plugin import client, config

def hebrew_url(val):
    return urllib2.quote(val.encode('utf8'))

def test_single_collection(client):

    items = [{'Slug': {'En': 'person.tester',
                       'He': hebrew_url(u'אישיות.בודק')
                      },
              'data': 'whatever',
             },
             {'Slug': {'En': 'person.another-tester',
                       'He': hebrew_url(u'אישיות.עוד-בודק')
                      },
              'data': 'whatever',
             }]
    persons = mongomock.MongoClient().db.collection
    for item in items:
        item['_id'] = persons.insert(item)

    res = client.get('/item/person.tester')
    assert res.status == 200
    res2 = client.get('/item/אישיות.בודק')
    assert res2.status == 200
    assert res == res2

    res = client.get('/item/person.tester,person.another-tester')
    assert res.status == 200
    assert len(res.json) == 2

    res = client.get('/item/person.no-one2')
    assert res.status == 404

    res = client.get('/item/unknown.unknown')
    assert res.status == 404

    res = client.get('/item/hello')
    assert res.status == 404

def test_multi_collections(client):
    pass
