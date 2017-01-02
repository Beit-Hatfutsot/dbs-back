import json
import logging
import pytest

from pytest_flask.plugin import client

from bhs_api.fsearch import fsearch

# The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

def test_fsearch_api(client, mock_db):
    for i in  [{
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
        } ]:
        mock_db['persons'].insert(i)
    total, persons = fsearch(last_name=['Einstein'], db=mock_db)
    assert total == 1
    assert persons[0]['tree_version'] == 1
