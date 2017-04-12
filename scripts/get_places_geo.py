import argparse
from flask import current_app

from bhs_api import create_app
from bhs_api.item import SHOW_FILTER

import requests
import urllib


def parse_args():
    parser = argparse.ArgumentParser(description=
"Use opencage to get a geojson for every place that doesn't have one"
                                     )
    parser.add_argument('--db',
                        help='the db to run on defaults to the value in the config file.')
    return parser.parse_args()


#TODO: move this to bhs_api.utils
def get_place_geo(doc):
    ''' tries to get the geo of a place, return None if fails '''
    url = 'https://api.opencagedata.com/geocode/v1/geojson'
    query = doc['Header']['En']
    parameters = {}
    parameters['q'] = query
    parameters['key'] = current_app.conf.opencage_key

    str_parameters = {}
    for k, v in parameters.iteritems():
        str_parameters[k] = unicode(v).encode('utf-8')
    params = urllib.urlencode(str_parameters)
    full_url = url + '?' + params
    response = requests.get(full_url)
    if response.status_code == 200:
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

    with app.app_context():
        for doc in db['places'].find(filters):
            geometry = get_place_geo(doc)
            if geometry:
                db['places'].update({"_id": doc["_id"]},
                                    {"$set": {"geometry": geometry}},
                                    multi=True)
