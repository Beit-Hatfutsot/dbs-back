#!/usr/bin/env python

import datetime
from uuid import UUID

import elasticsearch

from bhs_api import SEARCHABLE_COLLECTIONS, data_db, show_filter, es, uuids_to_str

index_name = data_db.name

for collection in SEARCHABLE_COLLECTIONS:
    started = datetime.datetime.now()
    for doc in data_db[collection].find(show_filter):
        try:
            res = es.index(index=index_name, doc_type=collection, id=doc['_id'], body=doc)
        except elasticsearch.exceptions.SerializationError:
            # UUID fields are causing es to crash, turn them to strings
            uuids_to_str(doc)
            res = es.index(index=index_name, doc_type=collection, id=doc['_id'], body=doc)
    finished = datetime.datetime.now()
    print 'Collection {} took {}'.format(collection, finished-started)
