import json
import logging
import pytest
from datetime import datetime

from bhs_api.fsearch import fsearch, clean_person, build_query, build_search_dict

# The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

# TODO: re-enable once we have persons in new ES
def skip_test_fsearch_api(mock_db):
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

# TODO: re-enable once we have persons in new ES
def skip_test_fsearch_range(mock_db):
    for i in [{
        'name_lc': ['albert', 'einstein'],
        'deceased': True,
        'tree_num': 2,
        'tree_version': 0,
        'id': 'I3',
        'archived': True,
        'Slug': {'En': 'person_1;0.I2'},
        'birth_year': 1863,
    }, {
        'name_lc': ['albert', 'einstein'],
        'deceased': True,
        'tree_num': 2,
        'tree_version': 1,
        'id': 'I7',
        'Slug': {'En': 'person_1;0.I7'},
        'birth_year': 1860,
        "marriage_years": [1875, 1888]
    }]:
        mock_db['persons'].insert(i)
    total, persons = fsearch(birth_year=["1862:2"], db=mock_db)
    assert total == 1
    assert persons[0]["birth_year"] == 1860
    total, persons = fsearch(marriage_year=["1876:2"], db=mock_db)
    assert total == 1
    assert persons[0]["id"] == "I7"
    assert persons[0]["marriage_years"] == [1875, 1888]

# TODO: re-enable once we have persons in new ES
def skip_test_fsearch_results_limit(mock_db):
    mock_db['persons'].remove()
    for i in range(0, 100):
        mock_db['persons'].insert({
            'name_lc': ['firstname{}'.format(i), 'lastname{}'.format(i)],
            'deceased': True,
            'tree_num': 2,
            'tree_version': 0,
            'id': 'I26{}'.format(i),
            'Slug': {'En': 'person_{};0.I26{}'.format(i, i)},
        })
    total, persons = fsearch(max_results=3, db=mock_db)
    assert total == 100
    assert len(persons) == 3
    total, persons = fsearch(max_results=3, max_count_results=5, db=mock_db)
    assert total == 5
    assert len(persons) == 3


# TODO: re-enable once we have persons in new ES
def skip_test_fsearch_build_search_dict():
    res = build_search_dict(birth_year=["1862:2"], death_year=["1899:3"], marriage_year=["1856:2"])
    assert sorted(res.items()) == [("birth_year", "1862:2"), ("death_year", "1899:3"), ("marriage_year", "1856:2")]


# TODO: re-enable once we have persons in new ES
def skip_test_fsearch_build_query():
    # use json in the expected respons to allow copy-pasting directly to mongo to test the queries
    # e.g.:
    #
    assert build_query({
        "birth_year": "1862:2",
        "death_year": "1899:3",
        "marriage_year": "1856:2"
    }) == json.loads("""{
        "archived": {"$exists": false},
        "death_year": {"$lte": 1902, "$gte": 1896},
        "marriage_years": {"$lte": 1858, "$gte": 1854},
        "deceased": true,
        "birth_year": {"$lte": 1864, "$gte": 1860}
    }""")
    assert build_query({"last_name": "cohen"}) == json.loads("""{
        "archived": {"$exists": false},
        "name_lc.1": "cohen"
    }""")

# TODO: re-enable once we have persons in new ES
def skip_test_clean_person(mock_db):
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
    # also, testing unknown fields - should also be removed (we have white-list of fields for living persons)
    cleaned = clean_person({
            'name_lc': ['yossi', 'cohen'],
            'birth_year': float(datetime.now().year-70),
            'id': 'I1',
            'Slug': {'En': 'person_1;0.I1'},
            'bio': 'yossi is a big boy',
            'deceased': False,
            'BIRT_DATE': "Jan 15, 1972",
            "FOO": "bar"
        })
    # ensure all fields are removed except the white-listed fields
    assert sorted(cleaned) == ['Slug', 'deceased', 'id', 'name_lc']

    # deceased person should be deceased regardless of birth year
    # also, ensure that unknown fields are not removed
    cleaned = clean_person({
        'name_lc': ['yossi', 'cohen'],
        'birth_year': float(datetime.now().year - 5),
        'id': 'I1',
        'Slug': {'En': 'person_1;0.I1'},
        'bio': 'yossi is a little dead boy',
        'deceased': True,
        'BIRT_DATE': "Jan 15, 1972",
        "FOO": "bar"
    })
    assert 'bio' in cleaned
    assert "FOO" in cleaned

# TODO: re-enable once we have persons in new ES
def skip_test_get_persons(client, mock_db):
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
