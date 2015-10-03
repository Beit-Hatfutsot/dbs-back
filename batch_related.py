#!/usr/bin/env python

import datetime
import logging

import api


def get_now_str():
    format = '%d.%h-%H:%M:%S'
    now = datetime.datetime.now()
    now_str = datetime.datetime.strftime(now, format)
    return now_str


if __name__ == '__main__':
    collections = api.SEARCHABLE_COLLECTIONS
    api.logger.setLevel(logging.INFO)
    db = api.data_db
    for collection in collections:
        started = datetime.datetime.now()
        count = db[collection].count()
        api.logger.info('Starting to work on {} at {}'.format(collection, get_now_str()))
        api.logger.info('Collection {} has {} documents.'.format(collection, count))
        for doc in db[collection].find({}, modifiers={"$snapshot": "true"}):
            key = '{}.{}'.format(collection, doc['_id'])
            related = api.get_bhp_related(doc)
            if not related:
                api.logger.debug('No related items found for {}'.format(key))
                doc['related'] = []
                db[collection].save(doc)
                continue
            else:
                doc['related'] = related
                db[collection].save(doc)

        finished = datetime.datetime.now()
        per_doc_time = (finished - started).total_seconds()/count
        api.logger.info('''Finished working on {} at {}.
Related took {:.2f} seconds per document.'''.format(
        collection, get_now_str(), per_doc_time))

