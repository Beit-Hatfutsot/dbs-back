''' Testing items Slugs
    ===================
    The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

    The documentation for advanced pytest fixtures use is at
    http://pytest.org/latest/fixture.html#fixture
'''
import json

import pytest

from pytest_flask.plugin import client, config


def test_single_collection(client):

    items = [{'Slug': {'En': 'person.tester',
                       'He': 'אישיות.בודק'
                      },
              'data': 'whatever',
             },
             {'Slug': {'En': 'person.another-tester',
                       'He': 'אישיות.עוד-בודק'
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

def test_multi_collections(client, items_with_slugs):
    pass
