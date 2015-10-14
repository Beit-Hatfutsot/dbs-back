#!/usr/bin/env python

import datetime
import logging
import json
import sys

import api


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

def sort_related(related_items):
    '''Put the more diverse items in the beginning'''
    # Sort the related ids by collection names...
    by_collection = {}
    rv = []
    for item_name in related_items:
        collection, _id = item_name.split('.')
        if by_collection.has_key(collection):
            by_collection[collection].append(item_name)
        else:
            by_collection[collection] = [item_name]

    # And pop 1 item form each collection as long as there are items
    while [v for v in by_collection.values() if v]:
        for c in by_collection:
            if by_collection[c]:
                rv.append(by_collection[c].pop())
    return rv

if __name__ == '__main__':
    collections = api.SEARCHABLE_COLLECTIONS
    api.logger.setLevel(logging.INFO)
    db = api.data_db
    show_filter = api.show_filter

    api.logger.info('Pass 1 - Collecting bhp related')
    direct_related_list = []
    for collection in collections:
        for doc in db[collection].find(show_filter, modifiers={"$snapshot": "true"}):
            related = api.get_bhp_related(doc, max_items=6, bhp_only=True)
            if not related:
                continue
            else:
                item_name = api.get_item_name(doc)
                direct_related_list.append({item_name: related})

    api.logger.info('Pass 1 finished')
    # Inverting the direction of related structures and adding the result
    # to original
    reverse_related_list = reverse_related(direct_related_list)
    unified_related_list = unify_related_lists(direct_related_list, reverse_related_list)


    #with open('ur.json') as fh:
    #    unified_related_list = json.load(fh)

    api.logger.info('Pass 2 - Applying bhp related')

    for item in unified_related_list:
        key = item.keys()[0]
        value = item.values()[0]
        collection, str_id = key.split('.')
        _id = int(str_id)
        doc = db[collection].find_one({'_id': _id})
        if doc:
            doc['bhp_related'] = value
            db[collection].save(doc)
        else:
            api.logger.info('Problem with {}'.format(key))
            sys.exit(1)

    api.logger.info('Pass 2 finished')

    api.logger.info('Pass 3 - Completing related')
    for collection in collections:
        started = datetime.datetime.now()
        count = db[collection].count(show_filter)
        api.logger.info('Starting to work on {}'.format(collection))
        api.logger.info('Collection {} has {} valid documents.'.format(collection, count))
        for doc in db[collection].find(show_filter, modifiers={"$snapshot": "true"}):
            item_name = api.get_item_name(doc)
            if not doc.has_key('bhp_related') or not doc['bhp_related']:
                # No bhp_related, get everything from es
                related = api.get_es_text_related(doc, items_per_collection=2)
            elif len(doc['bhp_related']) < 6:
                # Not enough related items, get an addition from es
                es_related = api.get_es_text_related(doc, items_per_collection=1)
                bhp_related = doc['bhp_related']
                bhp_related.extend(es_related)
                related = list(set(bhp_related))[:6]
            else:
                #  Sort and cut bhp_related
                related = sort_related(doc['bhp_related'])[:6]

            if not related:
                api.logger.debug('No related items found for {}'.format(item_name))
            doc['related'] = related
            db[collection].save(doc)

        finished = datetime.datetime.now()
        per_doc_time = (finished - started).total_seconds()/count
        api.logger.info("""Finished working on {}.
Related took {:.2f} seconds per document.""".format(
        collection, per_doc_time))

    api.logger.info('Pass 3 finished')
