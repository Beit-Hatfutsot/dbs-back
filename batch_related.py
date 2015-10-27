#!/usr/bin/env python

import datetime
import logging
import sys

from api import (invert_related_vector,
                reverse_related,
                reduce_related,
                unify_related_lists,
                sort_related,
                SEARCHABLE_COLLECTIONS,
                logger,
                data_db,
                show_filter,
                get_bhp_related,
                get_item_name,
                enrich_item,
                get_es_text_related)


if __name__ == '__main__':
    collections = SEARCHABLE_COLLECTIONS
    logger.setLevel(logging.INFO)
    db = data_db

    logger.info('Pass 1 - Collecting bhp related')
    direct_related_list = []
    for collection in collections:
        for doc in db[collection].find(show_filter, modifiers={"$snapshot": "true"}):
            related = get_bhp_related(doc, max_items=6, bhp_only=True)
            if not related:
                continue
            else:
                item_name = get_item_name(doc)
                direct_related_list.append({item_name: related})

    logger.info('Pass 1 finished')

    # Inverting the direction of related structures and adding the result
    # to original
    reverse_related_list = reverse_related(direct_related_list)
    unified_related_list = unify_related_lists(direct_related_list, reverse_related_list)

    logger.info('Pass 2 - Applying bhp related')

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
            logger.info('Problem with {}'.format(key))
            sys.exit(1)

    logger.info('Pass 2 finished')

    logger.info('Pass 3 - Completing related')
    for collection in collections:
        started = datetime.datetime.now()
        count = db[collection].count(show_filter)
        logger.info('Starting to work on {}'.format(collection))
        logger.info('Collection {} has {} valid documents.'.format(collection, count))
        for doc in db[collection].find(show_filter, modifiers={"$snapshot": "true"}):
            item_name = get_item_name(doc)
            if not doc.has_key('bhp_related') or not doc['bhp_related']:
                # No bhp_related, get everything from es
                related = sort_related(get_es_text_related(doc, items_per_collection=2))[:6]
            elif len(doc['bhp_related']) < 6:
                # Not enough related items, get an addition from es
                es_related = get_es_text_related(doc, items_per_collection=1)
                bhp_related = doc['bhp_related']
                bhp_related.extend(es_related)
                related = sort_related(list(set(bhp_related)))[:6]
            else:
                #  Sort and cut bhp_related
                related = sort_related(doc['bhp_related'])[:6]

            if not related:
                logger.debug('No related items found for {}'.format(item_name))
            doc['related'] = related
            enriched_doc = enrich_item(doc)
            db[collection].save(enriched_doc)

        finished = datetime.datetime.now()
        per_doc_time = (finished - started).total_seconds()/count
        logger.info("""Finished working on {}.
Related took {:.2f} seconds per document.""".format(
        collection, per_doc_time))

    logger.info('Pass 3 finished')
