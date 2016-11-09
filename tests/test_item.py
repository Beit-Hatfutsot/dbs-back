import pytest
from bhs_api.item import enrich_item

from pytest_flask.plugin import client

# The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

def test_enrich_item(app, mock_db):
    with app.app_context():
        item = enrich_item({'Pictures':
                        [
                            { 'IsPreview': 1, 'PictureId': 'ID' },
                        ],
                    },
                    mock_db)
    assert item['main_image_url'] == \
               'https://storage.googleapis.com/bhs-flat-pics/ID.jpg'
    assert item['thumbnail_url'] == \
               'https://storage.googleapis.com/bhs-thumbnails/ID.jpg'

def test_enrich_item_no_preview(app, mock_db):
    with app.app_context():
        item = enrich_item({'Pictures':
                        [
                            { 'IsPreview': 0, 'PictureId': 'ID' },
                        ],
                    },
                    mock_db)
    assert item['main_image_url'] == \
               'https://storage.googleapis.com/bhs-flat-pics/ID.jpg'

def test_enrich_item_no_pictures(app, mock_db):
    with app.app_context():
        item = enrich_item({}, mock_db)
    assert 'main_image_url' not in item
