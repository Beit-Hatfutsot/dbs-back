import re
import json
import logging
import pytest

from pytest_flask.plugin import client
from fixtures import get_auth_header,app

# The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

def test_api_public_view(client):
    res = client.get('/')
    assert res.json == {'access': 'public'}

def test_send_ticket(client, app):
    from bhs_api.user import send_ticket
    mail = app.extensions.get('mail')
    with mail.record_messages() as outbox:
        ticket = send_ticket({'email': 'tester@example.com'})
        assert len(outbox) == 1
        assert outbox[0].subject == "BH Login Instructions"
        urls = re.findall('http\S+', outbox[0].body)
        assert len(urls) == 1
    res = client.get(urls[0], headers={'content-type': 'application/json'})
    assert res.status_code == 302
    import pdb; pdb.set_trace()


