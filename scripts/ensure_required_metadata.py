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
import elasticsearch.helpers


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
            self.app.es.update(index=self.app.es_data_db_index_name, doc_type=collection_name,
                               id=es_item["_id"], body={"doc": updates})
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

    def _process_mongo_item(self, collection_name, mongo_item):
        """
        process and update a single mongo item
         returns tuple (code, msg, processed_key)
        """
        id_field = get_collection_id_field(collection_name)  # the name of the field which stores the key for this item
        item_key = mongo_item.get(id_field, None)  # the current item's key (AKA id)
        if item_key:
            self._debug("processing mongo item {}".format(item_key))
            show_item = doc_show_filter(mongo_item)  # should this item be shown or not?
            # search for corresponding items in elasticsearch - based on the item's collection and key
            body = {"query": {"match": {id_field: item_key}}}
            try:
                res = self.app.es.search(index=self.app.es_data_db_index_name, doc_type=collection_name, body=body)
            except Exception, e:
                self._info("exception processing mongo item from collection {} ({}={}): {}".format(collection_name, id_field, item_key, str(e)))
                res = {}
                # raise
            hits = res.get("hits", {}).get("hits", [])
            if len(hits) > 1:
                raise Exception("more then 1 hit for item {}={}".format(id_field, item_key))
            elif len(hits) == 1:
                es_item = hits[0]
            else:
                es_item = None
            try:
                return self._update_item(id_field, item_key, show_item, len(hits) > 0, mongo_item, collection_name, es_item) + (item_key,)
            except Exception, e:
                if self.args.debug:
                    print_exc()
                return self.ERROR, "error while processing {} ({}={}): {}".format(collection_name, id_field, item_key, e), None
        else:
            raise Exception("invalid mongo item key")

    def _process_elasticsearch_item(self, collection_name, item, processed_mongo_keys):
        id_field = get_collection_id_field(collection_name)  # the name of the field which stores the key for this item
        item_key = item.get("_source", {}).get(id_field, None)  # the current item's key (AKA id)
        if item_key:
            self._debug("processing elasticsearch item {}".format(item_key))
            if item_key in processed_mongo_keys:
                return self.NO_UPDATE_NEEDED, "elasticsearch item exists in mongo - it would have been updated from mongo side", item_key
            else:
                self.app.es.delete(index=self.app.es_data_db_index_name, doc_type=collection_name, id = item["_id"])
                return self.DELETED_ITEM, "deleted an item which exists in elastic but not in mongo", item_key
        else:
            raise Exception("invalid elasticsearch item key")

    def _handle_process_item_results(self, num_actions, errors, results):
        """
        handles the results from process_mongo_item or process_elasticsearch_item functions
        returns the number of processed keys
        """
        code, msg, processed_key = results
        self._debug(msg)
        if code:
            num_actions[code] = num_actions.get(code, 0) + 1
            if self.args.debug:
                sys.stdout.write(".")
                sys.stdout.flush()
            return processed_key
        else:
            errors.append(msg)
            sys.stdout.write("E")
            sys.stdout.flush()
            return None

    def _process_mongo_items(self, collection_name, errors, key, num_actions, processed_keys):
        num_processed_keys = 0
        items = self.app.data_db[collection_name].find(*[{get_collection_id_field(collection_name): key}] if key else [])
        for item in items:
            processed_key = self._handle_process_item_results(num_actions, errors, self._process_mongo_item(collection_name, item))
            if processed_key:
                processed_keys.append(processed_key)
            num_processed_keys += 1
        if num_processed_keys == 0:
            self._info("no items found in mongo")
        else:
            self._info("processed {} mongo items".format(num_processed_keys))
        return num_processed_keys

    def _process_elasticsearch_items(self, collection_name, errors, key, num_actions, processed_mongo_keys, processed_elasticsearch_keys):
        num_processed_keys = 0
        items = elasticsearch.helpers.scan(self.app.es, index=self.app.es_data_db_index_name, doc_type=collection_name, scroll=u"3h",
                                           query={"query": {"match": {get_collection_id_field(collection_name): key}}} if key else None)
        for item in items:
            processed_key = self._handle_process_item_results(num_actions, errors, self._process_elasticsearch_item(collection_name, item, processed_mongo_keys))
            if processed_key:
                processed_elasticsearch_keys.append(processed_key)
            num_processed_keys += 1
        if num_processed_keys == 0:
            self._info("no items found in elasticsearch")
        else:
            self._info("processed {} elasticsearch items".format(num_processed_keys))
        return num_processed_keys


    def _process_collection(self, collection_name, key):
        self._info("processing collection {}{}".format(collection_name, " key {}".format(key) if key else ""))
        errors, processed_mongo_keys, processed_elasticsearch_keys, num_actions = [], [], [], {}
        self._process_mongo_items(collection_name, errors, key, num_actions, processed_mongo_keys)
        self._process_elasticsearch_items(collection_name, errors, key, num_actions, processed_mongo_keys, processed_elasticsearch_keys)
        self._info("total {} items were processed:".format(len(processed_mongo_keys) + len(processed_elasticsearch_keys) + len(errors)))
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
                self._process_collection(collection_name, key)


if __name__ == '__main__':
    EnsureRequiredMetadataCommand().main()
