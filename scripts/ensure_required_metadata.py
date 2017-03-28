#!/usr/bin/env python
# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from bhs_api import create_app
from bhs_api.utils import SEARCHABLE_COLLECTIONS
from bhs_api.item import get_collection_id_field
from bhs_api.item import doc_show_filter, update_es, get_show_metadata
import sys
from datetime import datetime
from traceback import print_exc


class EnsureRequiredMetadataCommand(object):

    ERROR = False
    UPDATED_METADATA = 1
    ADDED_ITEM = 2
    DELETED_ITEM = 3
    NO_UPDATE_NEEDED = 4

    def __init__(self, app=None):
        self.args = self._parse_args()
        self.app, self.conf = create_app() if not app else (app, app.conf)

    def _parse_args(self):
        parser = ArgumentParser()
        parser.add_argument('--collection', help="only run for a single collection")
        parser.add_argument('--key', help="only run for a single item key (AKA id) - requires specifying collection as well")
        parser.add_argument('--add-to-es', action="store_true", help="add missing items to elasticsearch")
        parser.add_argument('--debug', action="store_true", help="show more debug logs")
        return parser.parse_args()

    def _debug(self, msg):
        if self.args.debug:
            print(msg)

    def _info(self, msg):
        print(msg)

    def _ensure_correct_item_required_metadata(self, id_field, item_key, src_item, collection_name, es_item):
        updates = {}
        if es_item["_source"].get("Slug") != src_item.get("Slug"):
            updates["Slug"] = src_item.get("Slug")
        src_show = doc_show_filter(src_item)
        es_show = doc_show_filter(es_item["_source"])
        if es_show != src_show:
            if not src_show:
                raise Exception("should not ensure metadata if mongo item should not be shown")
            else:
                # src item should be shown - but according to es metadata it shouldn't be shown
                # need to copy the relevant metadata for deciding whether to show the item
                updates.update(get_show_metadata(src_item))
        if len(updates) > 0:
            es_item["_source"].update(updates)
            self.app.es.update(index=self.app.es_data_db_index_name, doc_type=collection_name, id=es_item["_id"], body=es_item["_source"])
            return self.UPDATED_METADATA, "updated {} keys in elasticsearch ({}={})".format(len(updates), id_field, item_key)
        else:
            return self.NO_UPDATE_NEEDED, "item has correct metadata, no update needed: ({}={})".format(id_field, item_key)

    def _add_item(self, id_field, item_key, src_item, collection_name, es_item):
        is_ok, msg = update_es(collection_name, src_item, is_new=True, app=self.app)
        if is_ok:
            self._debug(msg)
            return self.ADDED_ITEM, "added item to es: ({}={})".format(id_field, item_key)
        else:
            return self.ERROR, "error adding item ({}={}): {}".format(id_field, item_key, msg)

    def _del_item(self, id_field, item_key, src_item, collection_name, es_item):
        self.app.es.delete(index=self.app.es_data_db_index_name, doc_type=collection_name, id=es_item["_id"])
        return self.DELETED_ITEM, "deleted item: ({}={})".format(id_field, item_key)

    def _update_item(self, id_field, item_key, show_item, exists_in_elasticsearch, item, collection_name, es_item):
        if show_item:
            if exists_in_elasticsearch:
                return self._ensure_correct_item_required_metadata(id_field, item_key, item, collection_name, es_item)
            elif self.args.add_to_es:
                return self._add_item(id_field, item_key, item, collection_name, es_item)
            else:
                return self.ERROR, "could not find item in elasticsearch ({}={})".format(id_field, item_key)
        else:
            # item should not be shown
            if exists_in_elasticsearch:
                return self._del_item(id_field, item_key, item, collection_name, es_item)
            else:
                return self.NO_UPDATE_NEEDED, "item should not be shown and doesn't exist in ES - no action needed ({}={})".format(id_field, item_key)

    def _process_item(self, collection_name, item):
        id_field = get_collection_id_field(collection_name)  # the name of the field which stores the key for this item
        item_key = item.get(id_field, None)  # the current item's key (AKA id)
        if item_key:
            self._debug("processing item {}".format(item_key))
            show_item = doc_show_filter(item)  # should this item be shown or not?
            # search for corresponding items in elasticsearch - based on the item's collection and key
            res = self.app.es.search(index=self.app.es_data_db_index_name, doc_type=collection_name, q="{}:{}".format(id_field, item_key))
            hits = res.get("hits", {}).get("hits", [])
            if len(hits) > 1:
                raise Exception("more then 1 hit for item {}={}".format(id_field, item_key))
            elif len(hits) == 1:
                es_item = hits[0]
            else:
                es_item = None
            try:
                return self._update_item(id_field, item_key, show_item, len(hits) > 0, item, collection_name, es_item)
            except Exception, e:
                if self.args.debug:
                    print_exc()
                return self.ERROR, "error while processing {} ({}={}): {}".format(collection_name, id_field, item_key, e)
        else:
            raise Exception("invalid item key")

    def _process_collection(self, collection_name):
        self._info("processing collection {}".format(collection_name))
        errors, num_processed_keys, num_actions = [], 0, {}
        for item in self.app.data_db[collection_name].find():
            code, msg = self._process_item(collection_name, item)
            self._debug(msg)
            if code:
                num_processed_keys += 1
                num_actions[code] = num_actions.get(code, 0)+1
                sys.stdout.write(".")
                sys.stdout.flush()
            else:
                errors.append(msg)
                sys.stdout.write("E")
                sys.stdout.flush()
        print("")
        self._info("total {} items were processed:".format(num_processed_keys+len(errors)))
        if len(errors) > 0:
            self._info("{} errors (see error.log for details)".format(len(errors)))
            with open("error.log", "a") as f:
                f.write("===== {}: {}: {} errors =====\n".format(datetime.now().strftime(""),
                                                               collection_name, len(errors)))
                for err in errors:
                    f.write("{}\n".format(err))
                    self._debug(err)
        for code in [self.UPDATED_METADATA, self.ADDED_ITEM, self.DELETED_ITEM, self.NO_UPDATE_NEEDED]:
            if code in num_actions:
                self._info({self.UPDATED_METADATA: "updated {} items",
                            self.ADDED_ITEM: "added {} items",
                            self.DELETED_ITEM: "deleted {} items",
                            self.NO_UPDATE_NEEDED: "{} items did not require update"}[code].format(num_actions[code]))
        self._info("done\n".format(collection_name))

    def main(self):
        key = self.args.key  # only run for this specific item key (AKA id)
        collection_names = SEARCHABLE_COLLECTIONS if not self.args.collection else [self.args.collection]
        if key and len(collection_names) != 1:
            raise Exception("cannot use key param without specifying a specific collection this key relates to")
        else:
            for collection_name in collection_names:
                self._process_collection(collection_name)


if __name__ == '__main__':
    EnsureRequiredMetadataCommand().main()
