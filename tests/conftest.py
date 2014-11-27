import sys
import json

import pytest
from pytest_flask.plugin import client, config

sys.path.append('..')

import api

# See pytest-flask plugin documentation at https://pypi.python.org/pypi/pytest-flask

@pytest.fixture(scope="session")
def app():
    test_app = api.app
    # Enable exception propagation to the test context
    test_app.testing = True
    return test_app

