import pytest
from flask import Response
from pytest_flask.plugin import client
from bhs_api import create_app
# The documentation for advanced pytest fixtures use is at
# http://pytest.org/latest/fixture.html#fixture

@pytest.fixture
def app():
    app, conf = create_app(testing=True)
    return app

@pytest.fixture
def get_auth_header(app):
    user = app.user_datastore.get_user("tester@example.com")
    # do some cleanup
    user.story_branches = 4*['']
    user.save()
    return {'Authentication-Token': user.get_auth_token()}



