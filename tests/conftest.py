# -*- coding: utf-8 -*-
import sys
import os

import pytest
import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                             os.pardir)))

from bhs_api import create_app


@pytest.fixture
def get_auth_header(app, tester):
    return {'Authentication-Token': tester.get_auth_token()}



# TODO: refactor tests the use both app & mock_db and remove the other guy
@pytest.fixture(scope="function")
def app():
    mock.patch('elasticsearch.Elasticsearch')
    app, conf = create_app(testing=True)
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
