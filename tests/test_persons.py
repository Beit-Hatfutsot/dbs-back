import json
import logging
import pytest
from datetime import datetime

from bhs_api.fsearch import fsearch, clean_person

# The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

def test_fsearch_api(mock_db):
    for i in [{
            'name_lc': ['albert', 'einstein'],
            'deceased': True,
            'tree_num': 2,
            'tree_version': 0,
            'id': 'I3',
            'archived': True,
            'Slug': {'En': 'person_1;0.I2'},
        },{
            'name_lc': ['albert', 'einstein'],
            'deceased': True,
            'tree_num': 2,
            'tree_version': 1,
            'id': 'I7',
            'Slug': {'En': 'person_1;0.I7'},
            'BIRT_PLAC_lc': "acapulco"
        },{
            'name_lc': ['cookie', 'monster'],
            'deceased': False,
            'tree_num': 2,
            'tree_version': 1,
            'id': 'I9',
            'Slug': {'En': 'person_1;0.I9'},
            'BIRT_PLAC_lc': "acapulco"
        }]:
            mock_db['persons'].insert(i)
    total, persons = fsearch(last_name=['Einstein'], db=mock_db)
    assert total == 1
    assert persons[0]['tree_version'] == 1
    # searching with living person details should not return any living persons
    total, persons = fsearch(birth_place=["Acapulco"], db=mock_db)
    assert total == 1
    assert persons[0]['id'] == "I7"

def test_clean_person(mock_db):
    # two cases for cleaning up the personal info
    cleaned = clean_person({
            'name_lc': ['yossi', 'cohen'],
            'deceased': False,
            'id': 'I1',
            'Slug': {'En': 'person_1;0.I7'},
            'bio': 'yossi is a big boy'
        })
    assert 'bio' not in cleaned

    cleaned = clean_person({
            'name_lc': ['yossi', 'cohen'],
            'birth_year': datetime.now().year-20,
            'id': 'I1',
            'Slug': {'En': 'person_1;0.I7'},
            'bio': 'yossi is a big boy'
        })
    assert 'bio' not in cleaned

    # and one for the dead
    cleaned = clean_person({
            'name_lc': ['yossi', 'cohen'],
            'birth_year': 1900,
            'id': 'I1',
            'Slug': {'En': 'person_1;0.I1'},
            'bio': 'yossi is a big boy'
        })
    assert 'bio' in cleaned

    # test case using year in float + with BIRT_DATE field
    cleaned = clean_person({
            'name_lc': ['yossi', 'cohen'],
            'birth_year': float(datetime.now().year-70),
            'id': 'I1',
            'Slug': {'En': 'person_1;0.I1'},
            'bio': 'yossi is a big boy',
            'deceased': False,
            'BIRT_DATE': "Jan 15, 1972"
        })
    assert 'BIRT_DATE' not in cleaned

    # deceased person should be deceased regardless of birth year
    cleaned = clean_person({
        'name_lc': ['yossi', 'cohen'],
        'birth_year': float(datetime.now().year - 5),
        'id': 'I1',
        'Slug': {'En': 'person_1;0.I1'},
        'bio': 'yossi is a little dead boy',
        'deceased': True,
        'BIRT_DATE': "Jan 15, 1972"
    })
    assert 'bio' in cleaned


def test_get_persons(client, mock_db):
    mock_db['persons'].insert({
            'name_lc': ['yossi', 'cohen'],
            'birth_year': 2000,
            'id': 'I1',
            'Slug': {'En': 'person_1;0.I1'},
            'bio': 'yossi is a big boy'
            })
    res = client.get('/v1/item/person_1;0.I1')
    assert res.status_code == 200
    assert res.json[0]['id'] == 'I1'
    assert 'bio' not in res.json[0] # this will FAIL in the year 2100
    assert 'birth_year' not in res.json[0] # this will FAIL in the year 2100
    mock_db['persons'].drop()
    mock_db['persons'].insert({
            'name_lc': ['yossi', 'cohen'],
            'birth_year': 1800,
            'id': 'I1',
            'Slug': {'En': 'person_1;0.I1'},
            'bio': 'yossi is a big boy'
            })
    res = client.get('/v1/item/person_1;0.I1')
    assert res.status_code == 200
    assert res.json[0]['bio'] == 'yossi is a big boy' # this will FAIL in the year 2100
