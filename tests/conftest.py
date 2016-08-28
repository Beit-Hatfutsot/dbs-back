import sys
import os
import json

import pytest
from pytest_flask.plugin import client, config

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                             os.pardir)))

from bhs_api import create_app


@pytest.fixture
def get_auth_header(app, tester):
    return {'Authentication-Token': tester.get_auth_token()}



@pytest.fixture(scope="session")
def app():
    app, conf = create_app(testing=True)
    return app


@pytest.fixture(scope="session")
def tester(app):
    user = app.user_datastore.get_user("tester@example.com")
    if not user:
        user = app.user_datastore.create_user(email='tester@example.com',
                                       name={'en': 'Test User'})

    else:
    # do some cleanup
        user.story_branches = 4*['']
        user.save()
    return user


@pytest.fixture
def tester_headers(client, get_auth_header):
    headers = {'Content-Type': 'application/json'}
    headers.update(get_auth_header)
    return headers

