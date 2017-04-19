# -*- coding: utf-8 -*-
import elasticsearch
import sys
import os
import json

import pytest
import mock
from pytest_flask.plugin import client, config
import mongomock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                             os.pardir)))

from bhs_api import create_app


@pytest.fixture
def get_auth_header(app, tester):
    return {'Authentication-Token': tester.get_auth_token()}



# TODO: refactor tests the use both app & mock_db and remove the other guy
@pytest.fixture(scope="function")
def app(mock_db):
    mock.patch('elasticsearch.Elasticsearch')
    app, conf = create_app(testing=True)
    # there should one and only one data db
    app.data_db = mock_db
    return app


@pytest.fixture(scope="function")
def tester(app):
    user = app.user_datastore.get_user("tester@example.com")
    if user:
        app.user_datastore.delete_user(user)

    user = app.user_datastore.create_user(email='tester@example.com',
                                    name={'en': 'Test User'})
    return user


@pytest.fixture(scope="function")
def tester_headers(get_auth_header):
    headers = {'Content-Type': 'application/json'}
    headers.update(get_auth_header)
    return headers


@pytest.fixture(scope="function")
def mock_db():
    ''' UnitId 1 & 2 are the tester personalities and 3 is `place_some` '''
    db = mongomock.MongoClient().db
    # add some personalities
    personalities = db.create_collection('personalities')
    for i in [{'UnitId': 1,
            'Slug': {'En': 'personality_tester',
                    'He': u'אישיות_בודק',
                    },
            'StatusDesc': 'Completed',
            'RightsDesc': 'Full',
            'DisplayStatusDesc':  'free',
            'UnitText1': {'En': 'tester',
                        'He': 'בודק',
                        }
            },
            {'UnitId': 2,
            'Slug': {'En': 'personality_another-tester',
                    'He': u'אישיות_עוד-בודק',
                    },
            'StatusDesc': 'Edit',
            'RightsDesc': 'Full',
            'DisplayStatusDesc':  'free',
            'UnitText1': {'En': 'another tester',
                        'He': 'עוד בודק',
                        },
             "Header": {"En": "Nava Schreiber, Daniella Luxemburg", "He": None}
            },
            ]:
        personalities.insert(i)
    trees = db.create_collection('trees')
    trees.insert({
        'num': 1,
        'versions': [{'file_id': 'initial',
                      'persons': 1,
                       'update_date': 'now',
                      }]
    })
    persons = db.create_collection('persons')
    # living person
    persons.insert({
            'name_lc': ['tester', 'de-tester'],
            'tree_num': 1,
            'tree_version': 0,
            'id': 'I2',
            "name": ["hoomy", "cookie"],
            'StatusDesc': 'Completed',
            'RightsDesc': 'Full',
            'DisplayStatusDesc':  'free',
            'Slug': {'En': 'person_1;0.I2'},
        })
    # dead person
    persons.insert({
        'name_lc': ['deady', 'deadead'],
        'tree_num': 1,
        'tree_version': 0,
        'id': 'I3',
        "name": ["rookie", "bloopy"],
        'Slug': {'En': 'person_1;0.I3'},
        "deceased": True,
        "BIRT_PLAC": "London"
    })
    places = db.create_collection('places')
    places.insert({'Slug': {'En': 'place_some'},
                   'UnitId': 3,
            'StatusDesc': 'Completed',
            'RightsDesc': 'Full',
            'DisplayStatusDesc':  'free',
            'UnitText1': {'En': 'just a place' }})
    return db

