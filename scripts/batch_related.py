#!/usr/bin/env python
import re
import datetime
import logging
import sys
import argparse

import elasticsearch
from werkzeug.exceptions import NotFound, Forbidden

from bhs_api import create_app
from bhs_api.item import (SHOW_FILTER, Slug, get_item_slug,
                          get_item_by_id, get_item, get_collection_name,
                          get_item_query)
from bhs_api.utils import uuids_to_str, SEARCHABLE_COLLECTIONS

data_db = None
es = None

def reduce_related(related_list):
    reduced = {}
    for r in related_list:
        key = r.keys()[0]
        value = r.values()[0]
        if key in reduced:
            reduced[key].extend(value)
        else:
            reduced[key] = value

    rv = []
    for key in reduced:
        rv.append({key: reduced[key]})
    return rv

def unify_related_lists(l1, l2):
    rv = l1[:]
    rv.extend(l2)
    return reduce_related(rv)

def invert_related_vector(vector_dict):
    rv = []
    key = vector_dict.keys()[0]
    for value in vector_dict.values()[0]:
        rv.append({value: [key]})
    return rv

def reverse_related(direct_related):
    rv = []
    for vector in direct_related:
        for r in invert_related_vector(vector):
            rv.append(r)

    return rv

def sort_related(related_items):
    '''Put the more diverse items in the beginning'''
    # Sort the related ids by collection names...
    by_collection = {}
    rv = []
    for item_name in related_items:
        slug = Slug(item_name)
        collection = slug.collection
        if collection in by_collection:
            by_collection[collection].append(item_name)
        else:
            by_collection[collection] = [item_name]

    # And pop 1 item form each collection as long as there are items
    while [v for v in by_collection.values() if v]:
        for c in by_collection:
            if by_collection[c]:
                rv.append(by_collection[c].pop())
    return rv

def get_bhp_related(doc, max_items=6, bhp_only=False):
    """
    Bring the documents that were manually marked as related to the current doc
    by an editor.
    Unfortunately there are not a lot of connections, so we only check the more
    promising vectors:
    places -> photoUnits
    personalities -> photoUnits, familyNames, places
    photoUnits -> places, personalities
    If no manual marks are found for the document, return the result of es mlt
    related search.
    """
    # A map of fields that we check for each kind of document (by collection)
    related_fields = {
            'places': ['PictureUnitsIds'],
            'personalities': ['PictureUnitsIds', 'FamilyNameIds', 'UnitPlaces'],
            'photoUnits': ['UnitPlaces', 'PersonalityIds']}

    # A map of document fields to related collections
    collection_names = {
            'PersonalityIds': 'personalities',
            'PictureUnitsIds': 'photoUnits',
            'FamilyNameIds': 'familyNames',
            'UnitPlaces': 'places'}

    # Check what is the collection name for the current doc and what are the
    # related fields that we have to check for it
    rv = []
    self_collection_name = get_collection_name(doc)

    if not self_collection_name:
        logger.debug('Unknown collection for {}'.format(
            get_item_slug(doc).encode('utf8')))
        return get_es_text_related(doc)[:max_items]
    elif self_collection_name not in related_fields:
        if not bhp_only:
            logger.debug(
                'BHP related not supported for collection {}'.format(
                self_collection_name))
            return get_es_text_related(doc)[:max_items]
        else:
            return []

    # Turn each related field into a list of BHP ids if it has content
    fields = related_fields[self_collection_name]
    for field in fields:
        collection = collection_names[field]
        if field in doc and doc[field]:
            related_value = doc[field]
            if type(related_value) == list:
                # Some related ids are encoded in comma separated strings
                # and others are inside lists
                related_value_list = [i.values()[0] for i in related_value]
            else:
                related_value_list = re.split('\||,', related_value)

            for i in related_value_list:
                if not i:
                    continue
                i = int(i)
                try:
                    item = get_item_by_id(i, collection)
                except (Forbidden, NotFound):
                    continue
                rv.append(get_item_slug(item))

    if bhp_only:
        # Don't pad the results with es_mlt related
        return rv
    else:
        # If we didn't find enough related items inside the document fields,
        # get more items using elasticsearch mlt search.
        if len(rv) < max_items:
            es_text_related = get_es_text_related(doc)
            rv.extend(es_text_related)
            rv = list(set(rv))
            # Using list -> set -> list conversion to avoid adding the same item
            # multiple times.
        return rv[:max_items]

def es_mlt_search(index_name, doc, doc_fields, target_collection, limit):
    '''Build an mlt query and execute it'''

    clean_doc = doc.copy()
    del clean_doc['_id']
    query = {'query':
              {'mlt':
                {'fields': doc_fields,
                'docs':
                  [
                    {'doc': clean_doc}
                  ],
                }
              }
            }
    try:
        results = es.search(index=data_db.name, doc_type=target_collection, body=query, size=limit)
    except elasticsearch.exceptions.SerializationError:
        # UUID fields are causing es to crash, turn them to strings
        uuids_to_str(clean_doc)
        results = es.search(index=data_db.name, doc_type=target_collection,
                            body=query, size=limit)
    except elasticsearch.exceptions.ConnectionError as e:
        logger.error('Error connecting to Elasticsearch: {}'.format(e.error))
        raise e

    if len(results['hits']['hits']) > 0:
        ret = []
        for h in results['hits']['hits']:
            try:
                slug = get_item_slug(h['_source'])
            except KeyError:
                logger.error("couldn't find slug for {},{}".format(h['_source']['_id'],
                                                                h['_source']['UnitType']))
                continue
            ret.append(slug)
        return ret
    else:
        return None

def get_es_text_related(doc, items_per_collection=1):
    related = []
    related_fields = ['Header.En', 'UnitText1.En', 'Header.He', 'UnitText1.He']
    collections = SEARCHABLE_COLLECTIONS
    self_collection = get_collection_name(doc)
    if not self_collection:
        logger.info('Unknown collection for document {}'.format(doc['_id']))
        return []
    for collection_name in collections:
        found_related = es_mlt_search(
                                    data_db.name,
                                    doc,
                                    related_fields,
                                    collection_name,
                                    items_per_collection)
        if found_related:
            related.extend(found_related)
    # Filter results
    ret = []
    for item_name in related:
        slug = Slug(item_name)
        filtered = None
        try:
            filtered = get_item(slug, data_db)
        except (Forbidden, NotFound):
            continue
        if filtered:
            ret.append(item_name)
    return ret

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d',
                        '--debug',
                        help='Save the unified related in a file',
                        action="store_true")
    parser.add_argument('-f',
                        '--filename',
                        help='The name of debug output file',
                        default='unified_related_list.json')
    parser.add_argument('-s',
                        '--slug',
                        help='limit the run to a specifc slug')
    parser.add_argument('--db',
                        help='the db to run on defaults to the value in /etc/bhs/config.yml')

    return parser.parse_args()


if __name__ == '__main__':

    args = parse_args()
    app, conf = create_app(testing=True)
    es = app.es
    logger = app.logger
    collections = SEARCHABLE_COLLECTIONS
    logger.setLevel(logging.INFO)
    if args.db:
        data_db = app.client_data_db[args.db]
    else:
        data_db = app.data_db

    query = SHOW_FILTER.copy()
    if args.slug:
        if args.slug[0] >= 'a' and args.slug[0] <= 'z':
            query.update({"Slug.En": args.slug})
        else:
            query.update({"Slug.He": args.slug})

    with app.app_context():
        logger.info('Pass 1 - Collecting bhp related')
        direct_related_list = []
        for collection in collections:
            for doc in data_db[collection].find(query,
                                                modifiers={"$snapshot": "true"}):
                related = get_bhp_related(doc, max_items=6, bhp_only=True)
                if not related:
                    continue
                else:
                    item_slug = get_item_slug(doc)
                    direct_related_list.append({item_slug: related})

        logger.info('Pass 1 finished')

        # Inverting the direction of related structures and adding the result
        # to original
        reverse_related_list = reverse_related(direct_related_list)
        unified_related_list = unify_related_lists(direct_related_list,
                                                   reverse_related_list)

        # Save the related info for debug
        if args.debug:
            with open(args.filename, 'w') as fh:
                import json
                json.dump(unified_related_list, fh, indent=2)

        logger.info('Pass 2 - Applying bhp related')

        for item in unified_related_list:
            key = item.keys()[0]
            value = item.values()[0]
            slug = Slug(key)
            try:
                doc = get_item(slug)
            except (Forbidden, NotFound):
                    continue
            if doc:
                data_db[collection].update_one(get_item_query(slug),
                                            {'$set': {'bhp_related': value}})
            else:
                logger.info('Problem with {}'.format(key))
                sys.exit(1)

        logger.info('Pass 2 finished')

        logger.info('Pass 3 - Completing related and enriching documents')
        for collection in collections:
            started = datetime.datetime.now()
            count = data_db[collection].count(SHOW_FILTER)
            logger.info('Starting to work on {}'.format(collection))
            logger.info('Collection {} has {} valid documents.'
                        .format(collection, count))
            for doc in data_db[collection].find(query,
                                                modifiers={"$snapshot": "true"}):
                slug = get_item_slug(doc)
                if not doc.has_key('bhp_related') or not doc['bhp_related']:
                    # No bhp_related, get everything from es
                    related = sort_related(get_es_text_related(doc,
                                                items_per_collection=2))[:6]
                elif len(doc['bhp_related']) < 6:
                    # Not enough related items, get an addition from es
                    es_related = get_es_text_related(doc, items_per_collection=1)
                    bhp_related = doc['bhp_related']
                    bhp_related.extend(es_related)
                    related = sort_related(list(set(bhp_related)))[:6]
                else:
                    #  Sort and cut bhp_related
                    related = sort_related(list(set(doc['bhp_related'])))[:6]

                if not related:
                    logger.debug('No related items found for {}'.format(
                        slug.encode('utf8')))
                doc['related'] = related
                data_db[collection].update_one(get_item_query(slug),
                                            {'$set': {'related': related}})

            finished = datetime.datetime.now()
            try:
                per_doc_time = (finished - started).total_seconds()/count
                logger.info("""Finished working on {}.
    Related took {:.2f} seconds per document.""".format(
            collection, per_doc_time))
            except ZeroDivisionError:
                logger.warn("count is zero")

        logger.info('Pass 3 finished')
