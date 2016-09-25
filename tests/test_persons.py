import json
import logging
import pytest

from pytest_flask.plugin import client

# The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

def test_fsearch_api(client):
    res = client.get('/v1/person?last_name=Einstein')
    assert 'items' in res.json
    assert int(res.json['total']) > 5
