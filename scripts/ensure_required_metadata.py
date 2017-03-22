#!/usr/bin/env python
# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from bhs_api import create_app
from bhs_api.utils import SEARCHABLE_COLLECTIONS
from bhs_api.item import get_collection_id_field
from bhs_api.item import SHOW_FILTER

if SHOW_FILTER == {'StatusDesc': 'Completed',
                   'RightsDesc': 'Full',
                   'DisplayStatusDesc': {'$nin': ['Internal Use']},
                   '$or':
                       [{'UnitText1.En': {'$nin': [None, '']}}, {'UnitText1.He': {'$nin': [None, '']}}]}:
    def doc_show_filter(doc):
        return ((doc.get('StatusDesc') == 'Completed'
                and doc.get('RightsDesc') == 'Full'
                and doc.get('DisplayStatusDesc') not in ['Internal Use']) or (doc.get("UnitText1", {}).get("En", None)
                                                                              and doc.get("UnitText1", {}).get("He", None)))
else:
    raise Exception("this script has a translation of the show filter, if the mongo show filter is modified, this logic needs to be modified as well")


class EnsureRequiredMetadataCommand(object):

    def _parse_args(self):
        parser = ArgumentParser()
        parser.add_argument('--collection', help="only run for a single collection")
        parser.add_argument('--key', help="only run for a single item key (requires collection parameter)")
        parser.add_argument('--add-to-es', action="store_true", help="add missing items to elasticsearch")
        return parser.parse_args()

    def main(self):
        args = self._parse_args()
        key = args.key
        if args.collection:
            collection_names = [args.collection]
        elif key:
            raise Exception("cannot use key param without specifying collection")
        else:
            collection_names = SEARCHABLE_COLLECTIONS
        app, conf = create_app()
        for collection_name in collection_names:
            print("processing collection {}".format(collection_name))
            errors = []
            num_processed_keys = 0
            for item in app.data_db[collection_name].find():
                id_field = get_collection_id_field(collection_name)
                item_key = item.get(id_field, None)
                if item_key:
                    show_item = doc_show_filter(item)
                    res = app.es.search(index=app.es_data_db_index_name, doc_type=collection_name, q="{}:{}".format(id_field, item_key))
                    num_hits = len(res.get("hits", {}).get("hits", []))
                    if show_item:
                        # item should be shown
                        if num_hits < 1:
                            # but isn't on elasticsearch
                            if args.add_to_es:
                                # print("add item: {}".format(item_key))
                                num_processed_keys += 1
                            else:
                                errors.append("could not find item in elasticsearch ({}={})".format(id_field, item_key))
                        else:
                            # and is on elasticsearch - need to update it
                            # print("update item: {}".format(item_key))
                            num_processed_keys += 1
                    else:
                        # item should not be shown
                        if num_hits > 0:
                            # there are hits on elasticsearch, need to delete them
                            # print("delete item: {}".format(item_key))
                            num_processed_keys += 1
                        else:
                            # no hits on elasticsearch - all is good
                            num_processed_keys += 1
                else:
                    raise Exception("invalid item key")
            print("{} errors".format(len(errors)))
            print("{} processed and updated keys".format(num_processed_keys))
            print("done processing collection {}".format(collection_name))

if __name__ == '__main__':
    EnsureRequiredMetadataCommand().main()
