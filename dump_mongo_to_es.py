#!/usr/bin/env python

import datetime
from uuid import UUID

import elasticsearch

from bhs_api import data_db, es
from bhs_api.utils import uuids_to_str
from bhs_api.item import SEARCHABLE_COLLECTIONS, show_filter

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
