#!/usr/bin/env python

import datetime
from uuid import UUID
import argparse

import elasticsearch

from bhs_api import create_app
from bhs_api.utils import uuids_to_str, SEARCHABLE_COLLECTIONS
from bhs_api.item import SHOW_FILTER


def parse_args():
    parser = argparse.ArgumentParser()
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

    for collection in SEARCHABLE_COLLECTIONS:
        started = datetime.datetime.now()
        for doc in db[collection].find(SHOW_FILTER):
            _id = doc['_id']
            del doc['_id']
            try:
                res = app.es.index(index=index_name, doc_type=collection, id=_id, body=doc)
            except elasticsearch.exceptions.SerializationError:
                # UUID fields are causing es to crash, turn them to strings
                uuids_to_str(doc)
                try:
                    res = app.es.index(index=index_name, doc_type=collection, id=_id, body=doc)
                except elasticsearch.exceptions.SerializationError as e:
                    import pdb; pdb.set_trace()
        finished = datetime.datetime.now()
        print 'Collection {} took {}'.format(collection, finished-started)
