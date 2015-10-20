#!/usr/bin/env python

import pymongo

data_db = pymongo.MongoClient()['bhp6']
collections = ('places', 'familyNames', 'photoUnits', 'personalities', 'movies')

show_filter = {
                'StatusDesc': 'Completed',
                'RightsDesc': 'Full',
                'DisplayStatusDesc':  {'$nin': ['Internal Use']},
                '$or':
                    [{'UnitText1.En': {'$nin': [None, '']}}, {'UnitText1.He': {'$nin': [None, '']}}]
              }

movie_ids = []
for doc in data_db['movies'].find({'RightsDesc': 'Full',
                                 'StatusDesc': 'Completed',
                                 'DisplayStatusDesc': {'$nin': ['Internal Use']},
                                 'MoviePath': {'$nin': [None, 'None']}}):
    movie_ids.append(doc['_id'])

rv = {}
for c in collections:
    rv[c] = []

for c in collections:
    for _id in movie_ids:
        show_filter.update({'bhp_related': {'$in': ['movies.{}'.format(_id)]}})
        found = list(data_db[c].find(show_filter, {'related':1, 'Header.En': 1}))
        if found:
            rv[c].append(found)

for c in rv:
    for item in rv[c]:
        for i in item:
            print 'test.myjewishidentity.org/item/{}/{}'.format(c, i['_id'])
