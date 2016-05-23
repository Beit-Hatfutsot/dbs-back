import sys
import os
import json

import pytest
from pytest_flask.plugin import client, config

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                             os.pardir)))

from bhs_api import create_app

# See pytest-flask plugin documentation at https://pypi.python.org/pypi/pytest-flask

@pytest.fixture(scope="session")
def app():
    test_app, conf = create_app(True)
    # Enable exception propagation to the test context
    return test_app

