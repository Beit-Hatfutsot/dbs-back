# -*- coding: utf-8 -*-
from common import *


def test_from_search_to_item(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    res = client.get("/v1/search?q=Living+Moments+in+Jewish+Spain")
    slug_en, slug_he = [res.json["hits"][0][s] for s in ["slug_en", "slug_he"]]
    # these are the slugs we get from search
    assert slug_en == u'video_living-moments-in-jewish-spain'
    assert slug_he == u'וידאו_רגעים-עם-יהודי-ספרד'
    # now, we use them to get the item details - we should get the same item for both languages
    for slug in [slug_en, slug_he]:
        items = assert_client_get(client, u"/v1/item/{}".format(slug))
        assert len(items) == 1
        item = items[0]
        assert item["collection"] == "movies"
        assert item["title_en"] == "Living Moments in Jewish Spain (English jews)"


# import pytest
# from bhs_api.item import enrich_item
# from pytest_flask.plugin import client
# The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/
# TODO: re-enable when item API is modified for new data schema
def skip_test_enrich_item(app, mock_db):
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

# TODO: re-enable when item API is modified for new data schema
def skip_test_enrich_item_no_preview(app, mock_db):
    with app.app_context():
        item = enrich_item({'Pictures':
                        [
                            { 'IsPreview': 0, 'PictureId': 'ID' },
                        ],
                    },
                    mock_db)
    assert item['main_image_url'] == \
               'https://storage.googleapis.com/bhs-flat-pics/ID.jpg'

# TODO: re-enable when item API is modified for new data schema
def skip_test_enrich_item_no_pictures(app, mock_db):
    with app.app_context():
        item = enrich_item({}, mock_db)
    assert 'main_image_url' not in item
