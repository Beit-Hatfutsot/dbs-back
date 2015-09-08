#!/usr/bin/env python

import datetime
import logging

import redis

import api

def save_redis_list(redis, key, values):
    """A naive wrapper around rpush"""
    for v in values:
        redis.rpush(key, v)

def get_redis_list(redis, key):
    """A naive wrapper around lrange"""
    return redis.lrange(key, 0, -1)

def get_now_str():
    format = '%d.%h-%H:%M:%S'
    now = datetime.datetime.now()
    now_str = datetime.datetime.strftime(now, format)
    return now_str


if __name__ == '__main__':
    collections = api.SEARCHABLE_COLLECTIONS
    api.logger.setLevel(logging.INFO)
    db = api.data_db
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    for collection in collections:
        if collection != 'movies':
            continue
        started = datetime.datetime.now()
        count = db[collection].count()
        print 'Starting to work on {} at {}'.format(collection, get_now_str())
        print 'Collection {} has {} documents.'.format(collection, count)
        for doc in db[collection].find():
            related = api.get_bhp_related(doc)
            key = '{}.{}'.format(collection, doc['_id'])
            save_redis_list(r, key, related)

        finished = datetime.datetime.now()
        per_doc_time = (finished - started).total_seconds()/count
        print '''Finished working on {} at {}.
Related took {} seconds per document.'''.format(
        collection, get_now_str(), per_doc_time)

