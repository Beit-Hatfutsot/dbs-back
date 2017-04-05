#!/usr/bin/env python
# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from bhs_api import create_app
import elasticsearch
from bhs_api.utils import SEARCHABLE_COLLECTIONS
from bhs_api.item import get_collection_id_field


class ElasticsearchCreateIndexCommand(object):

    def _parse_args(self):
        parser = ArgumentParser()
        parser.add_argument('--index', help="name of the elasticsearch index to create (defaults to index from app config)")
        parser.add_argument('--host', help="elasticsearch host to create the index in (default to host from app)")
        parser.add_argument('--force', action="store_true", help="delete existing index if exists")
        return parser.parse_args()

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
                    "properties": {"Header": self.header_mapping,}
                } for collection in SEARCHABLE_COLLECTIONS
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
        for collection_name, mapping in body["mappings"].items():
            mapping["properties"][get_collection_id_field(collection_name, is_elasticsearch=True)] = {"type": "keyword"}
        return body

    def create_es_index(self, es, es_index_name, delete_existing=False):
        if es.indices.exists(es_index_name):
            if delete_existing:
                print("deleting existing index")
                es.indices.delete(es_index_name)
            else:
                raise Exception("index already exists: {}".format(es_index_name))
        print("creating index..")
        es.indices.create(es_index_name, body=self._get_index_body())
        print("Great success!")

    def main(self):
        args = self._parse_args()
        host_name, index_name = args.host, args.index
        if not host_name or not index_name:
            # we only create the app if needed for the host name or index name
            app, conf = create_app()
        else:
            app, conf = None, None
        es = elasticsearch.Elasticsearch(host_name) if host_name else app.es
        if not index_name:
            index_name = app.es_data_db_index_name
        self.create_es_index(es, index_name, delete_existing=args.force)


if __name__ == '__main__':
    ElasticsearchCreateIndexCommand().main()
