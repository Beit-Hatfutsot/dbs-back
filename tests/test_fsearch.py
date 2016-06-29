import json
import logging
import pytest

from pytest_flask.plugin import client
from bhs_api.fsearch import get_person

# The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

def test_get_person(client):
    person = get_person(7846, 'I5')
    assert person['LN'] == 'Gurfinkel'
    assert person['BP'] == ''

    res = client.get('/v1/person/7846/I5')
    assert res.json['LN'] == 'Gurfinkel'
    assert res.json['BP'] == ''

def test_fsearch_api(client):
    res = client.get('/v1/person?last_name=Cohen')
    assert 'items' in res.json
    assert int(res.json['total']) > 10000
