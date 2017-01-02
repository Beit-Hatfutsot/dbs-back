import argparse
from bhs_api import create_app
from bhs_api.item import SHOW_FILTER
from opencage.geocoder import OpenCageGeocode
from bhs_api.utils import get_conf

conf = get_conf()
geocoder = OpenCageGeocode(conf.geocoder_key)
import requests
import urllib


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db',
                        help='the db to run on defaults to the value in /etc/bhs/config.yml')
    return parser.parse_args()


def get_geojson(doc):
    url = 'https://api.opencagedata.com/geocode/v1/geojson'
    query = doc['Header']['En']
    parameters = {}
    parameters['q'] = query
    parameters['key'] = '0ef3d3f7ec66ed4a1f0ab77bada03cff'

    str_parameters = {}
    for k, v in parameters.iteritems():
        str_parameters[k] = unicode(v).encode('utf-8')
    params = urllib.urlencode(str_parameters)
    full_url = url + '?' + params
    response = requests.get(full_url)
    result = response.json()

    if len(result['features']):
        return result['features'][0]['geometry']
    return None
    

if __name__ == '__main__':
    args = parse_args()
    app, conf = create_app()
    if args.db:
        db = app.client_data_db[args.db]
    else:
        db = app.data_db

    index_name = db.name
    filters = SHOW_FILTER.copy()
    filters['geometry'] = {'$exists': False}
    filters['Header.En'] = {'$nin' : [None, '']}

    for doc in db['places'].find(filters):
        geometry = get_geojson(doc)

        if geometry:
            db[collection].update({"Header.En": query}, {"$set": {"geometry": geometry}}, multi=True)   


