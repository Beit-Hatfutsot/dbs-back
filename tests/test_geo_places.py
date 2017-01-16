import json
import pytest
from pytest_flask.plugin import client
import urllib

def test_get_geocoded_places(client, app):
    for i in [{
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
        } ]:
        app.data_db['places'].insert(i)

    url = '/v1/geo/places'
    parameters = {
        'northEastLat': '51.41976382669737',
        'northEastLng': '12.579345703125002',
        'southWestLat': '48.31973404047173',
        'southWestLng': '9.195556640625002'
    }
    parameters = urllib.urlencode(parameters)
    ful_url = url + '?' + parameters
    with app.app_context():
        res = client.get(ful_url)
    assert res.status_code == 200
    assert len(res.json) == 1
    assert res.json[0]['Header']['En'] == 'test_place'


