#!/usr/bin/env python
import argparse

import pymongo

from bhs_api import create_app
from bhs_api.utils import SEARCHABLE_COLLECTIONS
from bhs_api.item import get_collection_id_field, get_item_slug


def parse_args():
    parser = argparse.ArgumentParser(description=
                    'copy the slugs from one db to another.\
The mongo host is specified in app_server.yaml')
    parser.add_argument('--fromdb',
                        help='the db from which to copy the slugs')
    return parser.parse_args()

if __name__ == '__main__':

    args = parse_args()
    app, conf = create_app()
    fromdb = app.client_data_db[args.fromdb]
    todb = app.data_db


    for c_name in SEARCHABLE_COLLECTIONS:
        if c_name != "persons":
            # TODO: add support for persons, at the moment it's not working due to the persons not having a single unique id field
            print("starting work on " + c_name)
            # in the process we might create duplicate index so remove them for now
            try:
                todb[c_name].drop_index('Slug.He_1')
            except pymongo.errors.OperationFailure:
                pass
            try:
                todb[c_name].drop_index('Slug.En_1')
            except pymongo.errors.OperationFailure:
                pass
            id_field = get_collection_id_field(c_name)
            # loop on all docs with a slug
            for from_doc in fromdb[c_name].find({'Slug': {'$exists': True,
                                                         '$ne': {}}}):
                to_doc = app.data_db[c_name].find_one(
                    {id_field: from_doc[id_field]})
                if not to_doc:
                    print("missing {}".format(get_item_slug(from_doc)))
                    continue
                if from_doc['Slug'] != to_doc['Slug']:
                    try:
                        todb[c_name].update_one({'_id': to_doc['_id']},
                                                    {'$set':
                                                        {'Slug': from_doc['Slug']}
                                                    })
                    except pymongo.errors.DuplicateKeyError as e:
                        import pdb; pdb.set_trace()
                    print('changed {} to {}'
                        .format(get_item_slug(to_doc).encode('utf8'),
                                get_item_slug(from_doc).encode('utf8')))
            todb[c_name].create_index("Slug.He", unique=True, sparse=True)
            todb[c_name].create_index("Slug.En", unique=True, sparse=True)

