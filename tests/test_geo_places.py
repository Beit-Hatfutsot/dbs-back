from common import given_local_elasticsearch_client_with_test_data, assert_client_get
from mocks import PLACES_BOURGES
from copy import deepcopy

def test_get_geo_places_no_hits(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    points = assert_client_get(client, u"/v1/geo/places"
                               u"?ne_lat=11.41976382669737"    # north
                               u"&ne_lng=11.42976382669737"    # east
                               u"&sw_lat=10.31973404047173"    # south
                               u"&sw_lng=10.195556640625002")  # west
    assert len(points) == 0

def test_get_geo_places_hit(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert PLACES_BOURGES["location"] == {"lat": 10.01, "lon": 49.5}
    assert PLACES_BOURGES["title_en"] == "BOURGES"
    points = assert_client_get(client, u"/v1/geo/places"
                               u"?ne_lat=14.01"  # north
                               u"&ne_lng=51.5"   # east
                               u"&sw_lat=9.01"  # south
                               u"&sw_lng=45.5")  # west
    assert len(points) == 1
    assert points[0]["title_en"] == "BOURGES"

def test_get_geo_places_bad_param_value(client, app):
    res = assert_client_get(client, u"/v1/geo/places"
                                    u"?ne_lat=badstring"  # north
                                    u"&ne_lng=51.5"       # east
                                    u"&sw_lat=9.01"       # south
                                    u"&sw_lng=45.5",      # west
                               500)
    assert res == {u'error': u'could not convert string to float: badstring'}

def test_get_geo_places_bad_param_key(client, app):
    res = assert_client_get(client, u"/v1/geo/places"
                                    u"?ne_lat=33.2"  # north
                                    u"&invalid_lng=51.5"  # east
                                    u"&sw_lat=9.01"  # south
                                    u"&sw_lng=45.5",  # west
                            500)
    assert res == {u'error': u'required argument: ne_lng'}

def test_geo_places_should_return_only_places(client, app):
    # add a copy of BOURGES but under photoUnits collection
    # this ensures we only get places, even if there are other matching itesm with geo data
    bourges_photo = deepcopy(PLACES_BOURGES)
    bourges_photo.update(collection="photoUnits", source_id=192347)
    given_local_elasticsearch_client_with_test_data(app,
                                                    "test_geo_places::should_return_only_places",
                                                    additional_index_docs={"photoUnits": [bourges_photo]})
    points = assert_client_get(client, u"/v1/geo/places"
                               u"?ne_lat=14.01"  # north
                               u"&ne_lng=51.5"   # east
                               u"&sw_lat=9.01"  # south
                               u"&sw_lng=45.5")  # west
    assert len(points) == 1
    assert points[0]["collection"] == "places"
