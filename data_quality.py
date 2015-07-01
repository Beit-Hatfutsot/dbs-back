#!/usr/bin/env python

import re

import pymongo

from phonetic import is_hebrew

def get_bad_headers(collection_obj):
    rv = []
    for doc in collection_obj.find():
        if doc['Header']['En'] and doc['Header']['He'] and (is_hebrew(doc['Header']['En']) or is_hebrew(doc['Header']['He']) == False):
            rv.append({doc['UnitId']: doc['Header']})
    return rv

if __name__ == '__main__':
    #db = pymongo.connection.Connection('bhs-infra')['bhp6']
    db = pymongo.connection.Connection('localhost')['bhp6']
    collections = ['places',
                   'photoUnits',
                   'personalities',
                   'movies']
                   #'familyNames']
    broken = {}
    for c in collections:
        broken[c] = get_bad_headers(db[c])

    for c in broken:
        print c
        unit_ids = [str(int(i.keys()[0])) for i in broken[c]]
        print ','.join(unit_ids)
