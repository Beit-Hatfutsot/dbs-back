#!/usr/bin/env python
# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from bhs_api import create_app
import elasticsearch
from bhs_api.constants import PIPELINES_ES_DOC_TYPE, SUPPORTED_SUGGEST_LANGS


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
            "type": "completion",
            "max_input_length": 20,
            "contexts": [{
                "name": "collection",
                "type": "CATEGORY",
                "path": "collection"
            }]
        }

    def get_dynamic_templates(self):
        return [{"title": {"match_pattern": "regex",
                           "match": "^title_..$",
                           "mapping": {"type": "text"}}},
                # currently the best option for case-insensitive search is to lower case when indexing a document
                # keyword type allows for efficient sorting
                # related issue in mojp-dbs-pipelines: https://github.com/Beit-Hatfutsot/mojp-dbs-pipelines/issues/13
                {"title_lc": {"match_pattern": "regex",
                              "match": "^title_.._lc$",
                              "mapping": {"type": "keyword"}}},
                {"slug": {"match_pattern": "regex",
                          "match": "^slug_..$",
                          "mapping": {"type": "keyword"}}}]

    def get_properties(self):
        properties = {}
        properties["period_startdate"] = {"type": "date"}
        properties["location"] = {"type": "geo_point"}
        properties["main_thumbnail_image_url"] = {"type": "keyword"}
        properties["main_image_url"] = {"type": "keyword"}
        properties["slugs"] = {"type": "keyword"}
        for lang in SUPPORTED_SUGGEST_LANGS:
            properties["title_{}_suggest".format(lang)] = self.completion_field
        return properties
        # following code is for the old schema
        # TODO: fix for the new schema (will need to add the data in the pipelines)
        # if collection == "persons":
            # properties.update({"tree_num": {"type": "integer"},
            #             "tree_version": {"type": "integer"},
            #             "person_id": {"type": "keyword"},
            #             "birth_year": {"type": "integer"},
            #             "death_year": {"type": "integer"},
            #             "marriage_years": {"type": "integer"},
            #             # these are updated in bhs_api.item.update_es functions
            #             "first_name_lc": {"type": "text"},
            #             "last_name_lc": {"type": "text"},
            #             "BIRT_PLAC_lc": {"type": "text"},
            #             "MARR_PLAC_lc": {"type": "text"},
            #             "DEAT_PLAC_lc": {"type": "text"},
            #             "gender": {"type": "keyword"}})
        # if collection == "familyNames":
        #     properties["dm_soundex"] = {
        #         "type": "completion",
        #         "max_input_length": 20,
        #         "contexts": [{
        #             "name": "collection",
        #             "type": "CATEGORY",
        #             "path": "_type"
        #         }]
        #     }


    def _get_index_body(self):
        return {"mappings": {PIPELINES_ES_DOC_TYPE: {"properties": self.get_properties(),
                                                     "dynamic_templates": self.get_dynamic_templates()}}}

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
