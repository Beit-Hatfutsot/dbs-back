#!/usr/bin/env python

import datetime
from uuid import UUID
import argparse

import elasticsearch

from bhs_api import create_app
from bhs_api.utils import uuids_to_str, SEARCHABLE_COLLECTIONS
from bhs_api.item import SHOW_FILTER

completion_field = {
                    "type": "text",
                    "fields": {
                        "suggest": {
                            "type": "completion",
                            "max_input_length": 20,
                            "contexts": [{
                                "name": "collection",
                                "type": "category",
                                "path": "_type"
                            }]
                        }
                    },
                }
completion_mapping = {
        "Header": {
            "properties": {
                "En": completion_field,
                "He": completion_field,
            }
        },
        "UnitHeaderDMSoundex": {
            "properties": {
                "En": completion_field,
                "He": completion_field,
            }
        }}

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--collection',
                        help='run only on collection')
    parser.add_argument('-r', '--remove', action = "store_true",
                        help='remove the current index')
    parser.add_argument('--db',
                        help='the db to run on defaults to the value in /etc/bhs/config.yml')
    return parser.parse_args()

if __name__ == '__main__':

    args = parse_args()
    app, conf = create_app()
    if args.db:
        db = app.client_data_db[args.db]
    else:
        db = app.data_db

    index_name = db.name
    # start with a clean index
    if args.remove:
        if app.es.indices.exists(index_name):
            app.es.indices.delete(index_name)
        # set the mapping to support completion fields
        app.es.indices.create(index_name, body={
            "mappings": {
                "places": { "properties": completion_mapping },
                "familyNames": { "properties": completion_mapping },
            }
        })

    if args.collection:
        collections = [args.collection]
    else:
        collections = SEARCHABLE_COLLECTIONS

    for collection in collections:
        started = datetime.datetime.now()
        for doc in db[collection].find(SHOW_FILTER):
            _id = doc['_id']
            del doc['_id']
            # un null the fields that are used for completion
            for key in ('Header', 'UnitHeaderDMSoundex'):
                for lang in ('En', 'He'):
                    if not doc[key][lang]:
                        doc[key][lang] = '1234567890'
            try:
                res = app.es.index(index=index_name, doc_type=collection, id=_id, body=doc)
            except elasticsearch.exceptions.SerializationError:
                # UUID fields are causing es to crash, turn them to strings
                uuids_to_str(doc)
                try:
                    res = app.es.index(index=index_name, doc_type=collection, id=_id, body=doc)
                except elasticsearch.exceptions.SerializationError as e:
                    import pdb; pdb.set_trace()
            except elasticsearch.exceptions.RequestError as e:
                import pdb; pdb.set_trace()
        finished = datetime.datetime.now()
        print 'Collection {} took {}'.format(collection, finished-started)
