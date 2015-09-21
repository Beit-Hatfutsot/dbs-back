#!/usr/bin/env python

import pprint

from elasticsearch import Elasticsearch

'''Inside ipython:
[(r['_score'], r['_source']['Header']['En'], r['_source']['UnitTypeDesc'])for r in es.mlt(index='bhp10', doc_type='places', id=71433, mlt_fields=related_fields, search_types=['places','personalities','photoUnits','familyNames'], search_size=40)['hits']['hits']]
'''

def get_related(es, doc_id, index, doc_type, mlt_fields, target_collections, limit):
    return [(r['_score'], r['_source']['Header']['En'], r['_source']['UnitTypeDesc'])for r in es.mlt(index=index, doc_type=doc_type, id=doc_id, mlt_fields=mlt_fields, search_types=target_collections, search_size=limit)['hits']['hits']]

if __name__ == '__main__':
    es = Elasticsearch()
    mlt_fields = ['Header.En', 'UnitText1.En', 'Header.He', 'UnitText1.He']
    target_collections = ['places','personalities','photoUnits','familyNames']
    # For Paris:
    pprint.pprint (get_related(es, 72312, 'bhp10', 'places', mlt_fields, target_collections, 40))


