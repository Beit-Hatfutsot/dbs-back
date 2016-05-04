#!/usr/bin/env python

import datetime
from uuid import UUID
import argparse

import elasticsearch

from bhs_api import SEARCHABLE_COLLECTIONS, client_data_db, data_db, es
from bhs_api.utils import uuids_to_str
from bhs_api.item import SHOW_FILTER


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db',
                        help='the db to run on defaults to the value in /etc/bhs/config.yml')
    return parser.parse_args()

if __name__ == '__main__':

    args = parse_args()
    if args.db:
        db = client_data_db[args.db]
    else:
        db = data_db

    index_name = db.name

    for collection in SEARCHABLE_COLLECTIONS:
        started = datetime.datetime.now()
        for doc in db[collection].find(SHOW_FILTER):
            try:
                res = es.index(index=index_name, doc_type=collection, id=doc['_id'], body=doc)
            except elasticsearch.exceptions.SerializationError:
                # UUID fields are causing es to crash, turn them to strings
                uuids_to_str(doc)
                res = es.index(index=index_name, doc_type=collection, id=doc['_id'], body=doc)
        finished = datetime.datetime.now()
        print 'Collection {} took {}'.format(collection, finished-started)
