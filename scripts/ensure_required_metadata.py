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
        parser.add_argument('--index', help="use this Elasticsearch index instead of the index from configuration")
        return parser.parse_args()

    def _debug(self, msg):
        if self.args.debug:
            print(msg)

    def _info(self, msg):
        print(msg)

    def _get_item_header_updates(self, collection_name, mongo_item, es_item):
        updates = {}
        if collection_name == "persons":
            name = " ".join(mongo_item["name"]) if isinstance(mongo_item["name"], list) else mongo_item["name"]
            item_header = {"En": name, "He": name}
            if es_item.get("Header", {}) != item_header:
                updates["Header"] = item_header
        return updates

    def _get_item_log_identifier(self, item_key, collection_name):
        if collection_name == "persons":
            return "(tree_num,version,id={},{},{})".format(*item_key)
        else:
            return "{}={}".format(get_collection_id_field(collection_name), item_key)

    def _ensure_correct_item_required_metadata(self, item_key, mongo_item, collection_name, es_item):
        updates = {}
        if es_item.get("Slug") != mongo_item.get("Slug"):
            updates["Slug"] = mongo_item.get("Slug")
        if es_item.get("geometry") != mongo_item.get("geometry"):
            updates["geometry"] = mongo_item.get("geometry")
        updates.update(self._get_item_header_updates(collection_name, mongo_item, es_item))
        src_show = doc_show_filter(collection_name, mongo_item)
        es_show = doc_show_filter(collection_name, es_item)
        if es_show != src_show:
            if not src_show:
                raise Exception("should not ensure metadata if mongo item should not be shown")
            else:
                # src item should be shown - but according to es metadata it shouldn't be shown
                # need to copy the relevant metadata for deciding whether to show the item
                updates.update(get_show_metadata(collection_name, mongo_item))
        if len(updates) > 0:
            self.app.es.update(index=self._get_elasticsearch_index_name(),
                               doc_type=collection_name,
                               id=self._get_elasticsearch_doc_id_from_item_key(collection_name, item_key),
                               body={"doc": updates})
            return self.UPDATED_METADATA, "updated {} keys in elasticsearch ({})".format(len(updates), self._get_item_log_identifier(item_key, collection_name))
        else:
            return self.NO_UPDATE_NEEDED, "item has correct metadata, no update needed: ({})".format(self._get_item_log_identifier(item_key, collection_name))

    def _add_item(self, item_key, mongo_item, collection_name, es_item):
        is_ok, msg = update_es(collection_name, mongo_item, is_new=True, app=self.app, es_index_name=self._get_elasticsearch_index_name())
        if is_ok:
            self._debug(msg)
            return self.ADDED_ITEM, "added item to es: ({})".format(self._get_item_log_identifier(item_key, collection_name))
        else:
            return self.ERROR, "error adding item ({}): {}".format(self._get_item_log_identifier(item_key, collection_name), msg)

    def _del_item(self, item_key, mongo_item, collection_name, es_item):
        self.app.es.delete(index=self._get_elasticsearch_index_name(), doc_type=collection_name, id=self._get_elasticsearch_doc_id_from_item_key(collection_name, item_key))
        return self.DELETED_ITEM, "deleted item: ({})".format(self._get_item_log_identifier(item_key, collection_name))

    def _update_item(self, item_key, show_item, exists_in_elasticsearch, mongo_item, collection_name, es_item):
        if show_item:
            if exists_in_elasticsearch:
                return self._ensure_correct_item_required_metadata(item_key, mongo_item, collection_name, es_item)
            elif self.args.add:
                return self._add_item(item_key, mongo_item, collection_name, es_item)
            else:
                return self.ERROR, "could not find item in elasticsearch ({})".format(self._get_item_log_identifier(item_key, collection_name))
        else:
            # item should not be shown
            if exists_in_elasticsearch:
                return self._del_item(item_key, mongo_item, collection_name, es_item)
            else:
                return self.NO_UPDATE_NEEDED, "item should not be shown and doesn't exist in ES - no action needed ({})".format(self._get_item_log_identifier(item_key, collection_name))

    def _get_mongo_item_key(self, collection_name, mongo_item):
        if collection_name == "persons":
            person_id = mongo_item.get("id", None)
            if self.args.legacy and not person_id:
                person_id = mongo_item.get("ID", None)
            tree_num = mongo_item.get("tree_num", None)
            tree_version = mongo_item.get("tree_version", None)
            if person_id is not None and tree_num is not None and tree_version is not None:
                item_key = int(tree_num), int(tree_version), str(person_id)
            else:
                item_key = None
        else:
            id_field = get_collection_id_field(collection_name)
            item_key = mongo_item.get(id_field, None)
        return item_key

    def _get_elasticsearch_item_key(self, collection_name, es_item):
        if collection_name == "persons":
            person_id = es_item.get("person_id", None)
            tree_num = es_item.get("tree_num", None)
            tree_version = es_item.get("tree_version", None)
            if person_id is not None and tree_num is not None and tree_version is not None:
                item_key = int(tree_num), int(tree_version), str(person_id)
            else:
                item_key = None
        else:
            id_field = get_collection_id_field(collection_name)
            item_key = es_item.get(id_field, None)
        return item_key

    def _get_elasticsearch_doc_id_from_item_key(self, collection_name, item_key):
        if collection_name == "persons":
            return "{}_{}_{}".format(*item_key)
        else:
            return item_key

    def _get_elasticsearch_item_key_query(self, collection_name, item_key):
        if collection_name == "persons":
            tree_num, tree_version, person_id = item_key
            return {"bool": {"must": [{"term": {"tree_num": tree_num}},
                                      {"term": {"tree_version": tree_version}},
                                      {"term": {"person_id": person_id}}]}}
        else:
            return {"term": {get_collection_id_field(collection_name): item_key}}

    def _process_mongo_item(self, collection_name, mongo_item):
        """
        process and update a single mongo item
         returns tuple (code, msg, processed_key)
        """
        item_key = self._get_mongo_item_key(collection_name, mongo_item)
        if item_key:
            self._debug("processing mongo item ({})".format(self._get_item_log_identifier(item_key, collection_name)))
            show_item = doc_show_filter(collection_name, mongo_item)  # should this item be shown or not?
            body = {"query": self._get_elasticsearch_item_key_query(collection_name, item_key)}
            try:
                res = self.app.es.search(index=self._get_elasticsearch_index_name(), doc_type=collection_name, body=body)
            except Exception as e:
                self._info("exception processing mongo item from collection {} ({}): {}".format(collection_name, self._get_item_log_identifier(item_key, collection_name), str(e)))
                res = {}
                # raise
            hits = res.get("hits", {}).get("hits", [])
            if len(hits) > 1:
                raise Exception("more then 1 hit for item ({})".format(self._get_item_log_identifier(item_key, collection_name)))
            elif len(hits) == 1:
                es_item = hits[0]["_source"]
            else:
                es_item = None
            try:
                return self._update_item(item_key, show_item, len(hits) > 0, mongo_item, collection_name, es_item) + (item_key,)
            except Exception as e:
                if self.args.debug:
                    print_exc()
                return self.ERROR, "error while processing mongo item {} ({}): {}".format(collection_name, self._get_item_log_identifier(item_key, collection_name), e), None
        else:
            raise Exception("invalid mongo item key for collection {}, mongo item: {}".format(collection_name, mongo_item))

    def _process_elasticsearch_item(self, collection_name, es_item, processed_mongo_item_keys):
        item_key = self._get_elasticsearch_item_key(collection_name, es_item["_source"])
        if item_key:
            self._debug("processing elasticsearch item ({})".format(self._get_item_log_identifier(item_key, collection_name)))
            if item_key in processed_mongo_item_keys:
                return self.NO_UPDATE_NEEDED, "elasticsearch item exists in mongo - it would have been updated from mongo side", item_key
            else:
                self.app.es.delete(index=self._get_elasticsearch_index_name(), doc_type=collection_name, id=self._get_elasticsearch_doc_id_from_item_key(collection_name, item_key))
                return self.DELETED_ITEM, "deleted an item which exists in elastic but not in mongo", item_key
        else:
            raise Exception("invalid elasticsearch item key for collection {}, elasticsearch item: {}".format(collection_name, es_item))

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

    def _limit(self, items):
        if self.args.limit:
            return islice(items, 0, self.args.limit)
        else:
            return items

    def _get_mongo_items(self, collection_name, key):
        if key:
            if collection_name == "persons":
                raise NotImplementedError("persons does not support updating by key yet")
            else:
                items = self.app.data_db[collection_name].find({get_collection_id_field(collection_name): key})
        else:
            items = self.app.data_db[collection_name].find()
        items = self._limit(items)
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
        if key:
            if collection_name == "persons":
                raise NotImplementedError("no support for updating specific persons")
            else:
                body = {"query": self._get_elasticsearch_item_key_query(collection_name, key)}
                items = elasticsearch.helpers.scan(self.app.es, index=self._get_elasticsearch_index_name(), doc_type=collection_name, scroll=u"3h", query=body)
        else:
            items = elasticsearch.helpers.scan(self.app.es, index=self._get_elasticsearch_index_name(), doc_type=collection_name, scroll=u"3h")
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

    def _get_elasticsearch_index_name(self):
        if self.args.index:
            return self.args.index
        else:
            return self.app.es_data_db_index_name

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
