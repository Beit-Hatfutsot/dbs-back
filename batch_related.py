#!/usr/bin/env python

import datetime
import logging

import redis
from elasticsearch import Elasticsearch

import api

def save_redis_list(redis, key, values):
    """A naive wrapper around rpush"""
    for v in values:
        redis.rpush(key, v)

def get_redis_list(redis, key):
    """A naive wrapper around lrange"""
    try:
        return redis.lrange(key, 0, -1)
    except AttributeError:
        # Key not found
        return None

def get_now_str():
    format = '%d.%h-%H:%M:%S'
    now = datetime.datetime.now()
    now_str = datetime.datetime.strftime(now, format)
    return now_str

def es_mlt_search(index_name, doc_type, doc_id, doc_fields, target_doc_type, limit):
    '''Build an mlt query and execute it'''
    query = {'query':
                {'mlt':
                    {'docs': [
                        {'_id': doc_id,
                        '_index': index_name,
                        '_type': doc_type}],
                    'fields': doc_fields
                    }
                }
            }
    es = Elasticsearch('localhost')
    results = es.search(doc_type=target_doc_type, body=query, size=limit)
    if len(results['hits']['hits']) > 0:
        result_doc_ids = ['{}.{}'.format(h['_type'], h['_source']['_id']) for h in results['hits']['hits']]
        return result_doc_ids
    else:
        return None

if __name__ == '__main__':
    collections = api.SEARCHABLE_COLLECTIONS
    api.logger.setLevel(logging.INFO)
    db = api.data_db
    index_name = 'bhp10'
    related_fields = ['Header.En', 'UnitText1.En', 'Header.He', 'UnitText1.He']
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    for collection in collections:
        if collection == 'movies':
            continue
        started = datetime.datetime.now()
        count = db[collection].count()
        print 'Starting to work on {} at {}'.format(collection, get_now_str())
        print 'Collection {} has {} documents.'.format(collection, count)
        for doc in db[collection].find({}, snapshot=True):
            key = '{}.{}'.format(collection, doc['_id'])
            ##related = api.get_bhp_related(doc)
            related = []
            for c in collections:
                found_related = es_mlt_search(index_name, collection, doc['_id'], related_fields, c, 1)
                if found_related:
                    related.extend(found_related)
            if not related:
                print 'No related items found for {}'.format(key)
                continue
            else:
                doc['related'] = related
                db[collection].save(doc)
                #save_redis_list(r, key, related)
                #related = get_redis_list(r, key)
                #related_list = [rr[2:-2] for rr in related]


        finished = datetime.datetime.now()
        per_doc_time = (finished - started).total_seconds()/count
        print '''Finished working on {} at {}.
Related took {:.2f} seconds per document.'''.format(
        collection, get_now_str(), per_doc_time)

