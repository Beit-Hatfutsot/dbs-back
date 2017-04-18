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
from itertools import chain, islice


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
        parser.add_argument('--add', action="store_true", help="add missing items to elasticsearch")
        parser.add_argument('--debug', action="store_true", help="show more debug logs")
        parser.add_argument('--legacy', action="store_true", help="sync with legacy collections as well (for development/testing purposes only)")
        parser.add_argument('--limit', type=int, help="process up to LIMIT results - good for development / testing")
        return parser.parse_args()

    def _debug(self, msg):
        if self.args.debug:
            print(msg)

    def _info(self, msg):
        print(msg)

    def _ensure_correct_item_required_metadata(self, item_key, mongo_item, collection_name, es_item):
        elasticsearch_id_field = get_collection_id_field(collection_name, is_elasticsearch=True)
        updates = {}
        if es_item["_source"].get("Slug") != mongo_item.get("Slug"):
            updates["Slug"] = mongo_item.get("Slug")
        if "geometry" in mongo_item:
            updates["geometry"] = mongo_item.get("geometry")
        src_show = doc_show_filter(collection_name, mongo_item)
        es_show = doc_show_filter(collection_name, es_item["_source"])
        if es_show != src_show:
            if not src_show:
                raise Exception("should not ensure metadata if mongo item should not be shown")
            else:
                # src item should be shown - but according to es metadata it shouldn't be shown
                # need to copy the relevant metadata for deciding whether to show the item
                updates.update(get_show_metadata(collection_name, mongo_item))
        if len(updates) > 0:
            self.app.es.update(index=self.app.es_data_db_index_name, doc_type=collection_name,
                               id=es_item["_id"], body={"doc": updates})
            return self.UPDATED_METADATA, "updated {} keys in elasticsearch ({}={})".format(len(updates), elasticsearch_id_field, item_key)
        else:
            return self.NO_UPDATE_NEEDED, "item has correct metadata, no update needed: ({}={})".format(elasticsearch_id_field, item_key)

    def _add_item(self, item_key, mongo_item, collection_name, es_item):
        elasticsearch_id_field = get_collection_id_field(collection_name, is_elasticsearch=True)
        is_ok, msg = update_es(collection_name, mongo_item, is_new=True, app=self.app)
        if is_ok:
            self._debug(msg)
            return self.ADDED_ITEM, "added item to es: ({}={})".format(elasticsearch_id_field, item_key)
        else:
            return self.ERROR, "error adding item ({}={}): {}".format(elasticsearch_id_field, item_key, msg)

    def _del_item(self, item_key, mongo_item, collection_name, es_item):
        elasticsearch_id_field = get_collection_id_field(collection_name, is_elasticsearch=True)
        self.app.es.delete(index=self.app.es_data_db_index_name, doc_type=collection_name, id=es_item["_id"])
        return self.DELETED_ITEM, "deleted item: ({}={})".format(elasticsearch_id_field, item_key)

    def _update_item(self, item_key, show_item, exists_in_elasticsearch, mongo_item, collection_name, es_item):
        elasticsearch_id_field = get_collection_id_field(collection_name, is_elasticsearch=True)
        if show_item:
            if exists_in_elasticsearch:
                return self._ensure_correct_item_required_metadata(item_key, mongo_item, collection_name, es_item)
            elif self.args.add:
                return self._add_item(item_key, mongo_item, collection_name, es_item)
            else:
                return self.ERROR, "could not find item in elasticsearch ({}={})".format(elasticsearch_id_field, item_key)
        else:
            # item should not be shown
            if exists_in_elasticsearch:
                return self._del_item(item_key, mongo_item, collection_name, es_item)
            else:
                return self.NO_UPDATE_NEEDED, "item should not be shown and doesn't exist in ES - no action needed ({}={})".format(elasticsearch_id_field, item_key)

    def _process_mongo_item(self, collection_name, mongo_item):
        """
        process and update a single mongo item
         returns tuple (code, msg, processed_key)
        """
        # the name of the field which stores the key for this item
        # it is different
        mongo_id_field = get_collection_id_field(collection_name, is_elasticsearch=False)
        elasticsearch_id_field = get_collection_id_field(collection_name, is_elasticsearch=True)
        item_key = mongo_item.get(mongo_id_field, None)  # the current item's key (AKA id)
        if self.args.legacy and not item_key and collection_name == "persons":
            item_key = mongo_item.get("ID", None)
        if item_key:
            self._debug("processing mongo item {}".format(item_key))
            show_item = doc_show_filter(collection_name, mongo_item)  # should this item be shown or not?
            # search for corresponding items in elasticsearch - based on the item's collection and key
            # we don't rely on elasticsearch natural id field because we want to support legacy elasticsearch documents
            # also, to prevent duplicates
            body = {"query": {"term": {elasticsearch_id_field: item_key}}}
            try:
                res = self.app.es.search(index=self.app.es_data_db_index_name, doc_type=collection_name, body=body)
            except Exception, e:
                self._info("exception processing mongo item from collection {} ({}={}): {}".format(collection_name, mongo_id_field, item_key, str(e)))
                res = {}
                # raise
            hits = res.get("hits", {}).get("hits", [])
            if len(hits) > 1:
                raise Exception("more then 1 hit for item {}={}".format(mongo_id_field, item_key))
            elif len(hits) == 1:
                es_item = hits[0]
            else:
                es_item = None
            try:
                return self._update_item(item_key, show_item, len(hits) > 0, mongo_item, collection_name, es_item) + (item_key,)
            except Exception, e:
                if self.args.debug:
                    print_exc()
                return self.ERROR, "error while processing mongo item {} ({}={}): {}".format(collection_name, mongo_id_field, item_key, e), None
        else:
            raise Exception("invalid mongo item key for collection {} mongo_id_field {}: {}".format(collection_name, mongo_id_field, mongo_item))

    def _process_elasticsearch_item(self, collection_name, item, processed_mongo_keys):
        id_field = get_collection_id_field(collection_name, is_elasticsearch=True)  # the name of the field which stores the key for this item
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

    def _handle_process_item_results(self, num_actions, errors, results, collection_name):
        """
        handles the results from process_mongo_item or process_elasticsearch_item functions
        returns the number of processed keys
        """
        # collection_name param is used in tests/test_migration.py
        code, msg, processed_key = results
        self._debug(msg)
        if code:
            num_actions[code] = num_actions.get(code, 0) + 1
            if self.args.debug:
                sys.stdout.write(".")
                sys.stdout.flush()
            elif num_actions[code] == 1 or num_actions[code]%1000 == 0:
                self._info("processed {} items with code {}: {}".format(num_actions[code], code, msg))
            return processed_key
        else:
            errors.append(msg)
            sys.stdout.write("E")
            sys.stdout.flush()
            return None

    def _filter_legacy_mongo_genTreeIndividuals_items(self, items):
        for item in items:
            yield item

    def _limit(self, items):
        if self.args.limit:
            return islice(items, 0, self.args.limit)
        else:
            return items

    def _get_mongo_items(self, collection_name, key):
        items = self._limit(self.app.data_db[collection_name].find(*[{get_collection_id_field(collection_name): key}] if key else []))
        if collection_name == "genTreeIndividuals":
            items = self._limit(self._filter_legacy_mongo_genTreeIndividuals_items(items))
        return items

    def _process_mongo_items(self, collection_name, errors, key, num_actions, processed_keys):
        num_processed_keys = 0
        items = self._get_mongo_items(collection_name, key)
        if self.args.legacy and collection_name == "persons":
            # persons data used to be in genTreeIndividuals, in legacy mode we process those items as well
            self._info("processing legacy genTreeIndividuals items as well")
            items = chain(items, self._get_mongo_items("genTreeIndividuals", key))
        for item in items:
            processed_key = self._handle_process_item_results(num_actions, errors, self._process_mongo_item(collection_name, item), collection_name)
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
                                           query={"query": {"match": {get_collection_id_field(collection_name, is_elasticsearch=True): key}}} if key else None)
        items = self._limit(items)
        for item in items:
            processed_key = self._handle_process_item_results(num_actions, errors, self._process_elasticsearch_item(collection_name, item, processed_mongo_keys), collection_name)
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
