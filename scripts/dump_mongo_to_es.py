#!/usr/bin/env python

import datetime
from uuid import UUID
import argparse

import elasticsearch

from bhs_api import create_app
from bhs_api import phonetic
from bhs_api.utils import uuids_to_str, SEARCHABLE_COLLECTIONS
from bhs_api.item import SHOW_FILTER


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--collection',
                        help='run only on collection')
    parser.add_argument('-r', '--remove', action = "store_true",
                        help='remove the current index')
    parser.add_argument('--db',
                        help='the db to run on defaults to the value in /etc/bhs/config.yml')
    return parser.parse_args()



class MongoToEsDumper(object):

    def __init__(self, es, es_index_name, mongo_db):
        self.es = es
        self.es_index_name = es_index_name
        self.mongo_db = mongo_db

    @property
    def completion_field(self):
        return {
            "type": "text",
            "fields": {
                "suggest": {
                    "type": "completion",
                    "max_input_length": 20,
                    "contexts": [{
                        "name": "collection",
                        "type": "CATEGORY",
                        "path": "_type"
                    }]
                }
            },
        }

    @property
    def header_mapping(self):
        ret = {
            "properties": {}
        }
        for lang in ["En", "He"]:
            ret["properties"][lang] = self.completion_field
            # currently the best option for case-insensitive search is to lower case when indexing a document
            # type keyword allows for efficient sorting
            ret["properties"]["{}_lc".format(lang)] = {"type": "keyword"}
        return ret

    def _get_index_body(self):
        body = {
            "mappings": {
                collection: {
                    "properties": {
                        "Header": self.header_mapping,
                    }
                }
                for collection in SEARCHABLE_COLLECTIONS
            }
        }
        body["mappings"]["familyNames"]["properties"]["dm_soundex"] = {
            "type": "completion",
            "max_input_length": 20,
            "contexts": [{
                "name": "collection",
                "type": "CATEGORY",
                "path": "_type"
            }]
        }
        return body


    def create_es_index(self, delete_existing=False):
        if self.es.indices.exists(self.es_index_name):
            if delete_existing:
                self.es.indices.delete(self.es_index_name)
            else:
                raise Exception()
        # set the mapping to support completion fields
        self.es.indices.create(self.es_index_name, body=self._get_index_body())

    def _process_collection(self, collection):
        started = datetime.datetime.now()
        for doc in self.mongo_db[collection].find(SHOW_FILTER):
            self._process_doc(collection, doc)
        finished = datetime.datetime.now()
        print 'Collection {} took {}'.format(collection, finished - started)

    def _add_phonetics(self, doc):
        if doc['Header']['En']:
            s = phonetic.get_english_dms(doc['Header']['En'])
        elif doc['Header']['He']:
            s = phonetic.get_hebrew_dms(doc['Header']['He'])
        else:
            s = 'BADWOLF'
        options = s.split(' ')
        doc['dm_soundex'] = options

    def _process_doc(self, collection, doc):
        _id = doc['_id']
        del doc['_id']
        del doc['UnitHeaderDMSoundex']
        # un null the fields that are used for completion
        if collection in ('places', 'familyNames'):
            self._add_phonetics(doc)
        # fill empty headers as es completion fails on null values
        header = doc['Header']
        for lang in ('En', 'He'):
            if not header[lang]:
                header[lang] = '1234567890'
            header["{}_lc".format(lang)] = header[lang].lower()
        res = None
        try:
            res = app.es.index(index=self.es_index_name, doc_type=collection, id=_id, body=doc)
        except elasticsearch.exceptions.SerializationError:
            # UUID fields are causing es to crash, turn them to strings
            uuids_to_str(doc)
            try:
                res = app.es.index(index=self.es_index_name, doc_type=collection, id=_id, body=doc)
            except elasticsearch.exceptions.SerializationError as e:
                import pdb
                pdb.set_trace()
        except elasticsearch.exceptions.RequestError as e:
            import pdb
            pdb.set_trace()
        return res

    def main(self, collections, delete_existing=False):
        self.create_es_index(delete_existing=delete_existing)
        for collection in collections:
            self._process_collection(collection)


if __name__ == '__main__':

    args = parse_args()
    app, conf = create_app()
    db = app.data_db if not args.db else app.client_data_db[args.db]
    collections = SEARCHABLE_COLLECTIONS if not args.collection else [args.collection]
    MongoToEsDumper(es=app.es, es_index_name=db.name, mongo_db=db).main(delete_existing=args.remove, collections=collections)
