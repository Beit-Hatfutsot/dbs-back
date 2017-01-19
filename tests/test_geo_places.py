import json
import pytest
from pytest_flask.plugin import client
import urllib

places_tester = [{
        'UnitId': 1000,
        'UnitText1': {'En': 'The Geo Place'},
        'Header': {'En': 'test_place'},
        'UnitPlaces': [{'PlaceIds': 3}],
        'StatusDesc': 'Completed',
        'RightsDesc': 'Full',
        'DisplayStatusDesc':  'free',
        'PlaceTypeDesc': {'En': "Country"},
        'geometry': {'type': 'Point',
                     'coordinates': [10.01, 49.5]}
        },{
            'UnitId': 2000,
            'UnitText1': {'En': 'The Geoless Place'},
            'Header': {'En': 'test_geoless_place'},
            'UnitPlaces': [{'PlaceIds': 3}],
            'PlaceTypeDesc': {'En': "Country"},
            'StatusDesc': 'Completed',
            'RightsDesc': 'Full',
            'DisplayStatusDesc':  'free'
        }]

def test_get_geo_places(client, app):
    app.data_db['places'].insert(places_tester)

    url = '/v1/geo/places'
    parameters = {
        'ne_lat': '51.41976382669737',
        'ne_lng': '12.579345703125002',
        'sw_lat': '48.31973404047173',
        'sw_lng': '9.195556640625002'
    }
    parameters = urllib.urlencode(parameters)
    ful_url = url + '?' + parameters
    with app.app_context():
        res = client.get(ful_url)
    assert res.status_code == 200
    assert len(res.json) == 1
    assert res.json[0]['Header']['En'] == 'test_place'

def test_get_geo_places_bad_param_value(client, app):
    app.data_db['places'].insert(places_tester)

    url = '/v1/geo/places'
    parameters = {
        'ne_lat': 'badstring',
        'ne_lng': '12.579345703125002',
        'sw_lat': '48.31973404047173',
        'sw_lng': '9.195556640625002'
    }
    parameters = urllib.urlencode(parameters)
    ful_url = url + '?' + parameters
    with app.app_context():
        res = client.get(ful_url)
    assert res.status_code == 400

def test_get_geo_places_bad_param_key(client, app):
    app.data_db['places'].insert(places_tester)

    url = '/v1/geo/places'
    parameters = {
        'ne_lat': '51.41976382669737',
        'bad_key': '12.579345703125002',
        'sw_lat': '48.31973404047173',
        'sw_lng': '9.195556640625002'
    }
    parameters = urllib.urlencode(parameters)
    ful_url = url + '?' + parameters
    with app.app_context():
        res = client.get(ful_url)
    assert res.status_code == 400


