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

from bhs_api.item import fetch_items

def hebrew_slug(val):
    return urllib2.quote(val.encode('utf8'))

def test_single_collection(client):

    items = [{'Slug': {'En': 'personality.tester',
                       'He': hebrew_slug(u'אישיות.בודק'),
                      },
              'StatusDesc': 'Completed',
              'RightsDesc': 'Full',
              'DisplayStatusDesc':  'free',
              'UnitText1': {'En': 'tester',
                            'He': 'בודק',
                            }
             },
             {'Slug': {'En': 'personality.another-tester',
                       'He': hebrew_slug(u'אישיות.עוד-בודק'),
                      },
              'StatusDesc': 'Completed',
              'RightsDesc': 'Full',
              'DisplayStatusDesc':  'free',
              'UnitText1': {'En': 'another tester',
                            'He': 'עוד בודק',
                            }
             }]
    db = mongomock.MongoClient().db
    persons = db.create_collection('personality')
    for item in items:
        item['_id'] = persons.insert(item)

    res = fetch_items(['personality.tester'], db)
    assert res[0]['Slug']['En'] == 'personality.tester'
    res = fetch_items([hebrew_slug(u'אישיות.בודק')], db)
    assert res[0]['Slug']['En'] == 'personality.tester'

    res = fetch_items(['personality.tester','personality.another-tester'], db)
    assert len(res) == 2

    res = fetch_items(['personality.no-one'], db)
    assert res[0]['error_code'] == 404

    res = fetch_items(['unknown.unknown'], db)
    assert res[0]['error_code'] == 404

    res = fetch_items(['hello'], db)
    assert res[0]['error_code'] == 404

def test_multi_collections(client):
    pass
