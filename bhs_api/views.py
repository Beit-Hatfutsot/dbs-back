#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from datetime import timedelta, datetime
import re
import urllib
import mimetypes
import magic
from uuid import UUID

from flask import Flask, request, abort, url_for
from flask_jwt import JWTError, jwt_required, verify_jwt
from flask.ext.jwt import current_user
from itsdangerous import URLSafeSerializer, BadSignature

from werkzeug import secure_filename, Response
from werkzeug.exceptions import NotFound, Forbidden, BadRequest
import elasticsearch

import pymongo
import jinja2

from bhs_api import app, db, logger, data_db, autodoc, conf
from bhs_common.utils import (get_conf, gen_missing_keys_error, binarize_image,
                              get_unit_type, SEARCHABLE_COLLECTIONS)
from utils import (get_logger, upload_file, send_gmail, humanify,
                   get_referrer_host_url, dictify)
from bhs_api.user import (get_user_or_error, clean_user, send_activation_email,
            user_handler, is_admin, get_mjs, add_to_my_story, set_item_in_branch,
            remove_item_from_story)
import phonetic


def get_activation_link(user_id):
    s = URLSafeSerializer(app.secret_key)
    payload = s.dumps(user_id)
    return url_for('activate_user', payload=payload, _external=True)

# While searching for docs, we always need to filter results by their work
# status and rights.
# We also filter docs that don't have any text in the 'UnitText1' field.
show_filter = {
                'StatusDesc': 'Completed',
                'RightsDesc': 'Full',
                'DisplayStatusDesc':  {'$nin': ['Internal Use']},
                '$or':
                    [{'UnitText1.En': {'$nin': [None, '']}}, {'UnitText1.He': {'$nin': [None, '']}}]
                }

es_show_filter = {
  'query': {
    'filtered': {
      'filter': {
        'bool': {
          'should': [
            {
              'and': [
                {
                  'exists': {
                    'field': 'UnitText1.En'
                  }
                },
                {
                  'script': {
                    'script': "doc['UnitText1.En'].empty == false"
                  }
                }
              ]
            },
            {
              'and': [
                {
                  'exists': {
                    'field': 'UnitText1.He'
                  }
                },
                {
                  'script': {
                    'script': "doc['UnitText1.He'].empty == false"
                  }
                }
              ]
            }
          ],
          'must_not': [
            {
              'regexp': {
                'DisplayStatusDesc': 'internal'
              }
            }
          ],
          'must': [
            {
              'term': {
                'StatusDesc': 'completed'
              }
            },
            {
              'term': {
                'RightsDesc': 'full'
              }
            }
          ]
        }
      },
      'query': {
        'query_string': {
          'query': '*'
        }
      }
    }
  }
}

class Ugc(db.Document):
    ugc = db.DictField()

def custom_error(error):
    return humanify({'error': error.description}, error.code)
for i in [400, 403, 404, 405, 409, 415, 500]:
    app.error_handler_spec[None][i] = custom_error


def fetch_items(item_list):
    '''
    # Fetch 2 items - 1 good and 1 bad
    >>> movie_id = data_db.movies.find_one(show_filter, {'_id': 1})['_id']
    >>> item_id = 'movies.{}'.format(movie_id)
    >>> items = fetch_items([item_id, 'places.00000'])
    >>> len(items)
    2
    >>> int(items[0]['_id']) ==  int(movie_id)
    True
    >>> items[1]['error_code']
    404
    '''

    rv = []
    for item_id in item_list:
        try:
            item = _fetch_item(item_id)
            rv.append(item)
        except (Forbidden, NotFound) as e:
            rv.append({'item_id': item_id, 'error_code': e.code, 'msg': e.description})
    return rv


def _fetch_item(item_id):
    """
    Gets item_id string and return an item
    If item_id is bad or item is not found, raises an exception.

    # A regular non-empty item - setup
    >>> movie_id = data_db.movies.find_one(show_filter, {'_id': 1})['_id']
    >>> item_id = 'movies.{}'.format(movie_id)
    >>> item = _fetch_item(item_id)
    >>> item != {}
    True

    >>> _fetch_item('unknown.')
    Traceback (most recent call last):
        ...
    NotFound: 404: Not Found
    >>> _fetch_item('places.00000')
    Traceback (most recent call last):
        ...
    NotFound: 404: Not Found

    # Item that doesn't pass filter
    >>> bad_filter_id = data_db.movies.find_one({"StatusDesc": "Edit"}, {'_id': 1})['_id']
    >>> bad_filter_item_id = 'movies.{}'.format(bad_filter_id)
    >>> _fetch_item(bad_filter_item_id)
    Traceback (most recent call last):
        ...
    Forbidden: 403: Forbidden

    """

    if not '.' in item_id: # Need colection.id to unpack
        raise NotFound, "missing a dot in item's id"
    collection, _id = item_id.split('.')[:2]
    if collection == 'ugc':
        item = dictify(Ugc.objects(id=_id).first())
        if item:
            item = enrich_item(item)
            item_id = item['_id']
            item = item['ugc'] # Getting the dict out from  mongoengine
            item['_id'] = item_id
            if type(item['_id']) == dict and '$oid' in item['_id']:
                item['_id'] = item['_id']['$oid']
            return _make_serializable(item)
        else:
            raise NotFound
    else:
        try:
            _id = long(_id) # Check that we are dealing with a right id format
        except ValueError:
            logger.debug('Bad id: {}'.format(_id))
            raise NotFound, "id has to be numeric"

        item = filter_doc_id(_id, collection)
        item = enrich_item(item)

        return _make_serializable(item)

def enrich_item(item):
    if 'related' not in item or not item['related']:
        m = 'Hit bhp related in enrich_item - {}'.format(get_item_name(item))
        logger.debug(m)
    if not 'thumbnail' in item.keys():
        item['thumbnail'] = _get_thumbnail(item)
    if not 'main_image_url' in item.keys():
        try:
            main_image_id = [image['PictureId'] for image in item['Pictures'] if image['IsPreview'] == '1'][0]
            item['main_image_url'] = get_image_url(main_image_id)
        except (KeyError, IndexError):
            item['main_image_url'] = None
    video_id_key = 'MovieFileId'
    if video_id_key in item:
        # Try to fetch the video URL
        video_id = item[video_id_key]
        video_url = get_video_url(video_id)
        if video_url:
            item['video_url'] = video_url
        else:
            return {}
            #abort(404, 'No video URL was found for this movie item.')
    return item

def get_text_related(doc, max_items=3):
    """Look for documents in `collections` where one or more of the words
    from the headers (English and Hebrew) of the given `doc` appear inside
    UnitText1 field.
    """
    related = []
    collections = SEARCHABLE_COLLECTIONS
    en_header = doc['Header']['En']
    if en_header == None:
        en_header = ''
    he_header = doc['Header']['He']
    if he_header == None:
        he_header = ''

    for collection_name in collections:
        col = data_db[collection_name]
        headers = en_header + ' ' + he_header
        if headers == ' ':
            # No headers at all - empty doc - no relateds
            return []
        # Create text indices for text search to work:
        # db.YOUR_COLLECTION.createIndex({"UnitText1.En": "text", "UnitText1.He": "text"})
        header_text_search = {'$text': {'$search': headers}}
        header_text_search.update(show_filter)
        projection = {'score': {'$meta': 'textScore'}}
        sort_expression = [('score', {'$meta': 'textScore'})]
        # http://api.mongodb.org/python/current/api/pymongo/cursor.html
        cursor = col.find(header_text_search, projection).sort(sort_expression).limit(max_items)
        if cursor:
            try:
                for related_item in cursor:
                    related_item = _make_serializable(related_item)
                    if not _make_serializable(doc)['_id'] == related_item['_id']:
                        # Exclude the doc iteself from its relateds
                        related_string = collection_name + '.' + related_item['_id']
                        related.append(related_string)
            except pymongo.errors.OperationFailure as e:
                # Create a text index
                logger.debug('Creating a text index for collection {}'.format(collection_name))
                col.ensure_index([('UnitText1.En', pymongo.TEXT), ('UnitText1.He', pymongo.TEXT)])
                continue
        else:
            continue

    return related

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
    for item_name in related:
        collection, _id = item_name.split('.')[:2]
        try:
            filter_doc_id(_id, collection)
        except (Forbidden, NotFound):
            continue
        related.append(filtered)
    return related

def uuids_to_str(doc):
    for k,v in doc.items():
        if type(v) == UUID:
            doc[k] = str(v)

def es_mlt_search(index_name, doc, doc_fields, target_collection, limit):
    '''Build an mlt query and execute it'''


    query = {'query':
              {'mlt':
                {'fields': doc_fields,
                'docs':
                  [
                    {'doc': doc}
                  ],
                }
              }
            }
    try:
        results = es.search(doc_type=target_collection, body=query, size=limit)
    except elasticsearch.exceptions.SerializationError:
        # UUID fields are causing es to crash, turn them to strings
        uuids_to_str(doc)
        results = es.search(doc_type=target_collection, body=query, size=limit)
    except elasticsearch.exceptions.ConnectionError as e:
        logger.error('Error connecting to Elasticsearch: {}'.format(e.error))
        raise e

    if len(results['hits']['hits']) > 0:
        result_doc_ids = ['{}.{}'.format(h['_type'], h['_source']['_id']) for h in results['hits']['hits']]
        return result_doc_ids
    else:
        return None

def es_search(q, collection=None, size=14, from_=0):
    body = es_show_filter
    query_body = body['query']['filtered']['query']['query_string']
    query_body['query'] = q
    # Boost the header by  2:
    # https://www.elastic.co/guide/en/elasticsearch/reference/1.7/query-dsl-query-string-query.html
    query_body['fields'] = ['Header.En^2', 'Header.He^2', 'UnitText1.En', 'UnitText1.He']
    try:
        results = es.search(index=data_db.name, body=body, doc_type=collection, size=size, from_=from_)
    except elasticsearch.exceptions.ConnectionError as e:
        logger.error('Error connecting to Elasticsearch: {}'.format(e.error))
        return None
    return results

def get_bhp_related(doc, max_items=6, bhp_only=False, delimeter='|'):
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
        logger.debug('Unknown collection')
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
                related_value_list = [i['PlaceIds'] for i in related_value]
            else:
                related_value_list = related_value.split(delimeter)

            for i in related_value_list:
                if not i:
                    continue
                else:
                    i = int(i)
                    try:
                        filter_doc_id(i, collection)
                    except (Forbidden, NotFound):
                        continue
                    rv.append(collection + '.' + i)

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

def filter_doc_id(unit_id, collection):
    '''
    Try to return Mongo _id for the given unit_id and collection name.
    Raise HTTP exception if the _id is NOTFound or doesn't pass the show filter
    and therefore Forbidden.
    '''
    search_query = {'_id': unit_id}
    search_query.update(show_filter)
    item = data_db[collection].find_one(search_query)
    if item:
        if collection == 'movies':
            video_id = item['MovieFileId']
            video_url = get_video_url(video_id)
            if not video_url:
                logger.debug('No video for {}.{}'.format(collection, unit_id))
                return None
            else:
                return item
        else:
            return item
    else:
        search_query = {'_id': unit_id}
        item = data_db[collection].find_one(search_query)
        if item:
            msg = ['filter failed for {}.{}'.format(collection, unit_id)]
            if item['StatusDesc'] != 'Completed':
                msg.append("Status Description is not 'Completed'")
            if item['RightsDesc'] != 'Full':
                msg.append("The  Rights of the Item are not 'Full'")
            if item['DisplayStatusDesc'] == 'Internal Use':
                msg.append("Display Status is 'Internal Use'")
            if item['UnitText1']['En'] in [None, ''] and \
               item['UnitText1']['He'] in [None, '']:
                msg.append('Empty Text (description) in both Heabrew and English')
            raise Forbidden('\n'.join(msg))
        else:
            raise NotFound

def get_collection_name(doc):
    if 'UnitType' in doc:
        unit_type = doc['UnitType']
    else:
        return None
    return get_unit_type(unit_type)

def get_item_name(doc):
    collection_name = get_collection_name(doc)
    item_name = '{}.{}'.format(collection_name, doc['_id'])
    return item_name

def _get_picture(picture_id):
    found = data_db['photos'].find_one({'PictureId': picture_id})
    return found

def _get_thumbnail(doc):
    thumbnail = ''
    path = ''

    try:
        if 'Pictures' in doc.keys():
            for pic in doc['Pictures']:
                if pic['IsPreview'] == '1':
                    picture = _get_picture(pic['PictureId'])
                    thumbnail = picture['bin']
                    if 'PictureFileName' in picture.keys():
                        path = picture['PicturePath']
        elif 'RelatedPictures' in doc.keys():
            for pic in doc['RelatedPictures']:
                if pic['IsPreview'] == '1':
                    picture = _get_picture(pic['PictureId'])
                    thumbnail = picture['bin']
                    if 'PictureFileName' in picture.keys():
                        path = picture['PicturePath']

        return {
            'data': urllib.quote(thumbnail.encode('base-64')),
            'path': urllib.quote(path.replace('\\', '/'))
        }

    except (KeyError, TypeError):
        return {}

def _make_serializable(obj):
    # ToDo: Replace with json.dumps with default setting and check
    # Make problematic fields json serializable
    if obj.has_key('_id'):
        obj['_id'] = str(obj['_id'])
    if obj.has_key('UpdateDate'):
        obj['UpdateDate'] = str(obj['UpdateDate'])
    return obj

def _generate_credits(fn='credits.html'):
    try:
        fh = open(fn)
        credits = fh.read()
        fh.close()
        return credits
    except:
        logger.debug("Couldn't open credits file {}".format(fn))
        return '<h1>No credits found</h1>'

def _convert_meta_to_bhp6(upload_md, file_info):
    '''Convert language specific metadata fields to bhp6 format.
    Use file_info to set the unit type.
    The bhp6 format is as follows:
    {
      "Header": { # title
        "En": "nice photo",
        "HE": "תמונה נחמדה"
      },
      "UnitType": 1, # photo unit type
      "UnitText1": { # description
        "En": "this is a very nice photo",
        "He": "זוהי תמונה מאוד נחמדה"
      },
      "UnitText2": { # people_present
        "En": "danny and pavel",
        "He": "דני ופבל"
      }
    }
    '''
    # unit_types dictionary
    unit_types = {
        'image data': 1,
        'GEDCOM genealogy': 4
        }
    # Sort all the metadata fields to Hebrew, English and no_lang
    he = {'code': 'He', 'values': {}}
    en = {'code': 'En', 'values': {}}
    no_lang = {}
    for key in upload_md:
        if key.endswith('_en'):
            # Add the functional part of key name to language dict
            en['values'][key[:-3]] = upload_md[key]
        elif key.endswith('_he'):
            he['values'][key[:-3]] = upload_md[key]
        else:
            no_lang[key] = upload_md[key]

    bhp6_to_ugc = {
        'Header': 'title',
        'UnitText1': 'description',
        'UnitText2': 'people_present'
    }

    rv = {
        'Header': {'He': '', 'En': ''},
        'UnitText1': {'He': '', 'En': ''},
        'UnitText2': {'He': '', 'En': ''}
    }

    for key in rv:
        for lang in [he, en]:
            if bhp6_to_ugc[key] in lang['values']:
                rv[key][lang['code']] = lang['values'][bhp6_to_ugc[key]]
            else:
                rv[key][lang['code']] = ''

    # Add Unit type to rv
    ut_matched = False
    for ut in unit_types:
        if ut in file_info:
           rv['UnitType'] = unit_types[ut]
           ut_matched = True
    if not ut_matched:
        rv['UnitType'] = 0
        logger.debug('Failed to match UnitType for "{}"'.format(file_info))
    # Add the raw upload data to rv
    rv['raw'] = no_lang
    return rv

def search_by_header(string, collection, starts_with=True):
    if not string: # Support empty strings
        return {}
    if phonetic.is_hebrew(string):
        lang = 'He'
    else:
        lang = 'En'
    string_re = re.escape(string)
    if starts_with:
        header_regex = re.compile(u'^'+string_re, re.IGNORECASE)
    else:
        header_regex = re.compile(u'^{}$'.format(string_re), re.IGNORECASE)
    lang_header = 'Header.{}'.format(lang)
    unit_text = 'UnitText1.{}'.format(lang)
    # Search only for non empty docs with right status
    show_filter[unit_text] = {"$nin": [None, '']}
    header_search_ex = {lang_header: header_regex}
    header_search_ex.update(show_filter)
    item = data_db[collection].find_one(header_search_ex)

    if item:
        item = enrich_item(item)
        return _make_serializable(item)
    else:
        return {}

def _validate_filetype(file_info_str):
    allowed_filetypes = [
                          'PNG image data',
                          'JPEG image data',
                          'Adobe Photoshop Image',
                          'GEDCOM genealogy'
    ]

    for filetype in allowed_filetypes:
        if filetype in file_info_str:
            return True

    return False

def get_completion(collection, string, search_prefix=True, max_res=5):
    '''Search in the headers of bhp6 compatible db documents.
    If `search_prefix` flag is set, search only in the beginning of headers,
    otherwise search everywhere in the header.
    Return only `max_res` results.
    '''
    collection = data_db[collection]
    if phonetic.is_hebrew(string):
        lang = 'He'
    else:
        lang = 'En'

    if search_prefix:
        regex = re.compile('^'+re.escape(string), re.IGNORECASE)
    else:
        regex = re.compile(re.escape(string), re.IGNORECASE)

    found = []
    header = 'Header.{}'.format(lang)
    unit_text = 'UnitText1.{}'.format(lang)
    # Search only for non empty docs with right status
    show_filter[unit_text] = {"$nin": [None, '']}
    header_search_ex = {header: regex}
    header_search_ex.update(show_filter)
    projection = {'_id': 0, header: 1}
    cursor = collection.find(header_search_ex ,projection).limit(max_res)
    for doc in cursor:
        header_content = doc['Header'][lang]
        if header_content:
            found.append(header_content.lower())

    return found

def get_phonetic(collection, string, limit=5):
    collection = data_db[collection]
    retval = phonetic.get_similar_strings(string, collection)
    return retval[:limit]

def fsearch(max_results=None,**kwargs):
    '''
    Search in the genTreeIindividuals table or try to fetch a gedcom file.
    Names and places could be matched exactly, by the prefix match
    or phonetically:
    The query "first_name=yeh;prefix" will match "yehuda" and "yehoshua", while
    the query "first_name=yeh;phonetic" will match "yayeh" and "ben jau".
    Years could be specified with a fudge factor - 1907~2 will match
    1905, 1906, 1907, 1908 and 1909.
    If `tree_number` kwarg is present, return only the results from this tree.
    Return up to `max_results`
    '''
    args_to_index = {'first_name': 'FN_lc',
                     'last_name': 'LN_lc',
                     'maiden_name': 'IBLN_lc',
                     'sex': 'G',
                     'birth_place': 'BP_lc',
                     'marriage_place': 'MP_lc',
                     'death_place': 'DP_lc'}

    extra_args =    ['tree_number',
                     'birth_year',
                     'marriage_year',
                     'death_year',
                     'individual_id',
                     'debug']

    allowed_args = set(args_to_index.keys() + extra_args)
    search_dict = {}
    for key, value in kwargs.items():
        search_dict[key] = value[0]
        if not value[0]:
            abort(400, "{} argument couldn't be empty".format(key))

    keys = search_dict.keys()
    bad_args = set(keys).difference(allowed_args)
    if bad_args:
        abort(400, 'Unsupported args in request: {}'.format(', '.join(list(bad_args))))
    if 'tree_number' in keys:
        try:
            tree_number = int(search_dict['tree_number'])
        except ValueError:
            abort(400, 'Tree number must be an integer')
    else:
        tree_number = None

    collection = data_db['genTreeIndividuals']

    # Ensure there are indices for all the needed fields
    index_keys = [v['key'][0][0] for v in collection.index_information().values()]
    needed_indices = ['LN_lc', 'BP_lc', 'GTN', 'LNS', 'II']
    for index_key in needed_indices:
        if index_key not in index_keys:
             logger.info('Ensuring indices for field {} - please wait...'.format(index_key))
             collection.ensure_index(index_key)

    # Sort all the arguments to those with name or place and those with year
    names_and_places = {}
    years = {}
    # Set up optional queries
    sex_query = None
    individual_id = None

    for k in keys:
        if '_name' in k or '_place' in k:
            # The search is case insensitive
            names_and_places[k] = search_dict[k].lower()
        elif '_year' in k:
            years[k] = search_dict[k]
        elif k == 'sex':
            if search_dict[k].lower() in ['m', 'f']:
                sex_query = search_dict[k].upper()
            else:
                abort(400, "Sex must be one of 'm', 'f'")
        elif k == 'individual_id':
            individual_id = search_dict['individual_id']

    # Build a dict of all the names_and_places queries
    for search_arg in names_and_places:
        field_name = args_to_index[search_arg]
        split_arg = names_and_places[search_arg].split(';')
        search_str = split_arg[0]
        # No modifications are supported for first names because
        # firstname DMS (Soundex) values are not stored in the BHP database.
        if search_arg == 'first_name':
            qf = {field_name: search_str}
            names_and_places[search_arg] = qf
            continue
        if len(split_arg) > 1:
            if split_arg[1] == 'prefix':
                q = re.compile('^{}'.format(search_str))
                qf = {field_name: q}
            elif split_arg[1] == 'phonetic':
                q = phonetic.get_bhp_soundex(search_str)
                case_sensitive_fn = field_name.split('_lc')[0]
                field_name = case_sensitive_fn + 'S'
                qf = {field_name: q}
            # Drop wrong instructions - don't treat the part after semicolon
            else:
                qf = {field_name: search_str}
        else:
            # There is a simple string search
            qf = {field_name: search_str}

        names_and_places[search_arg] = qf

    # Build a dict of all the year queries
    for search_arg in years:
        if '~' in years[search_arg]:
            split_arg = years[search_arg].split('~')
            try:
                year = int(split_arg[0])
                fudge_factor = int(split_arg[1])
            except ValueError:
                abort(400, 'Year and fudge factor must be integers')
            years[search_arg] = _generate_year_range(year, fudge_factor)
        else:
            try:
                year = int(years[search_arg])
                years[search_arg] = year
            except ValueError:
                abort(400, 'Year must be an integer')
            years[search_arg] = _generate_year_range(year)

    year_ranges = {'birth_year': ['BSD', 'BED'],
                   'death_year': ['DSD', 'DED']}

    # Build gentree search query from all the subqueries
    search_query = {}

    for item in years:
        if item == 'marriage_year':
            # Look in the MSD array
            search_query['MSD'] = {'$elemMatch': {'$gte': years[item]['min'], '$lte': years[item]['max']}} 
            continue
        start, end = year_ranges[item]
        search_query[start] = {'$gte': years[item]['min']}
        search_query[end] = {'$lte': years[item]['max']}

    if sex_query:
        search_query['G'] = sex_query

    for item in names_and_places.values():
        for k in item:
            search_query[k] = item[k]

    if tree_number:
        search_query['GTN'] = tree_number
        # WARNING: Discarding all the other search qeuries if looking for GTN and II
        if individual_id:
            search_query = {'GTN': tree_number, 'II': individual_id}

    logger.debug('Search query:\n{}'.format(search_query))

    projection = {'II': 1,   # Individual ID
                  'GTN': 1,  # GenTree Number
                  'LN': 1,   # Last name
                  'FN': 1,   # First Name
                  'IBLN': 1, # Maiden name
                  'BD': 1,   # Birth date
                  'BP': 1,   # Birth place
                  'DD': 1,   # Death date
                  'DP': 1,   # Death place
                  'G': 1,    # Gender
                  'MD': 1,   # Marriage dates as comma separated string
                  'MP': 1,   # Marriage places as comma separated string
                  'GTF': 1,  # Tree file UUID
                  'EditorRemarks': 1}

    if 'debug' in search_dict.keys():
        projection = None

    results = collection.find(search_query, projection)
    if max_results:
        results = results.limit(max_results)
    if results.count() > 0:
        logger.debug('Found {} results'.format(results.count()))
        return results
    else:
        return []

def _generate_year_range(year, fudge_factor=0):
    maximum = int(str(year + fudge_factor) + '9999')
    minimum = int(str(year - fudge_factor) + '0000')
    return {'min': minimum, 'max': maximum}


def get_image_url(image_id):
    image_bucket_url = conf.image_bucket_url
    collection = data_db['photos']

    photo = collection.find_one({'PictureId': image_id})
    if photo:
        photo_path = photo['PicturePath']
        photo_fn = photo['PictureFileName']
        if not (photo_path and photo_fn):
            logger.debug('Bad picture path or filename - {}'.format(image_id))
            return None
        extension = photo_path.split('.')[-1].lower()
        url = '{}/{}.{}'.format(image_bucket_url, image_id, extension)
        return url
    else:
        logger.debug('UUID {} was not found'.format(image_id))
        return None


def get_video_url(video_id):
    video_bucket_url = conf.video_bucket_url
    collection = data_db['movies']
    # Search only within the movies filtered by rights, display status and work status
    video = collection.find_one({'MovieFileId': video_id,
                                 'RightsDesc': 'Full',
                                 'StatusDesc': 'Completed',
                                 'DisplayStatusDesc': {'$nin': ['Internal Use']},
                                 'MoviePath': {'$nin': [None, 'None']}})
    if video:
        extension = 'mp4'
        url = '{}/{}.{}'.format(video_bucket_url, video_id, extension)
        return url
    else:
        logger.debug('Video URL was not found for {}'.format(video_id))
        return None

# Views
@app.route('/documentation')
def documentation():
    return autodoc.html(title='My Jewish Identity API documentation')

@app.route('/')
def home():
    # Check if the user is authenticated with JWT
    try:
        verify_jwt()
        return humanify({'access': 'private'})

    except JWTError as e:
        logger.debug(e.description)
        return humanify({'access': 'public'})

@app.route('/private')
@jwt_required()
def private_space():
    return humanify({'access': 'private', 'email': current_user.email})

@app.route('/users/activate/<payload>')
def activate_user(payload):
    s = URLSafeSerializer(app.secret_key)
    try:
        user_id = s.loads(payload)
    except BadSignature:
        abort(404)

    user = get_user_or_error(user_id)
    user.confirmed_at = datetime.now()
    user.save()
    logger.debug('User {} activated'.format(user.email))
    return humanify(clean_user(user))


@app.route('/users/send_activation_email',  methods=['POST'])
@jwt_required()
def handle_activation_email_request():
    referrer = request.referrer
    if referrer:
        referrer_host_url = get_referrer_host_url(referrer)
    else:
        referrer_host_url = None
    user_id = str(current_user.id)
    return send_activation_email(user_id, referrer_host_url)


@app.route('/user', methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/user/<user_id>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_user(user_id=None):
    '''
    Manage user accounts. If routed as /user, gives access only to logged in
    user, else if routed as /user/<user_id>, allows administrative level access
    if the looged in user is in the admin group.
    POST gets special treatment, as there must be a way to register new user.
    '''
    try:
        verify_jwt()
    except JWTError as e:
        # You can create a new user while not being logged in
        # ToDo: defend this endpoint with rate limiting or similar means
        if request.method == 'POST':
            if not 'application/json' in request.headers['Content-Type']:
                abort(400, "Please set 'Content-Type' header to 'application/json'")
            return user_handler(None, request)
        else:
            logger.debug(e.description)
            abort(403)

    if user_id:
        # admin access_mode
        if is_admin(current_user):
            return user_handler(user_id, request)
        else:
            logger.debug('Non-admin user {} tried to access user id {}'.format(
                                                  current_user.email, user_id))
            abort(403)
    else:
        # user access_mode
        user_id = str(current_user.id)
        # Deny POSTing to logged in non-admin users to avoid confusion with PUT
        if request.method == 'POST':
            abort(400, 'POST method is not supported for logged in users.')
        return user_handler(user_id, request)


@app.route('/mjs/<item_id>', methods=['DELETE'])
@jwt_required()
def delete_item_from_story(item_id):
    remove_item_from_story(item_id)
    return humanify(get_mjs())
    
@app.route('/mjs/<branch_num>/<item_id>', methods=['DELETE'])
@jwt_required()
def remove_item_from_branch(item_id, branch_num=None):
    try:
        branch_num = int(branch_num)
    except ValueError:
        raise BadRequest("branch number must be an integer")

    set_item_in_branch(item_id, branch_num-1, False)
    return humanify(get_mjs())


@app.route('/mjs/<branch_num>', methods=['POST'])
@jwt_required()
def add_to_story_branch(branch_num):
    item_id = request.data
    try:
        branch_num = int(branch_num)
    except ValueError:
        raise BadRequest("branch number must be an integer")
    set_item_in_branch(item_id, branch_num-1, True)
    return humanify(get_mjs())


@app.route('/mjs/<branch_num>/name', methods=['POST'])
@jwt_required()
def set_story_branch_name(branch_num):

    name = request.data
    current_user.story_branches[int(branch_num)-1] = name
    current_user.save()
    return humanify(get_mjs())


@app.route('/mjs', methods=['GET', 'POST'])
@jwt_required()
def manage_jewish_story():
    '''Logged in user may GET or POST their jewish story links.
    the links are stored as an array of items where each item has a special
    field: `branch` with a boolean array indicating which branches this item is
    part of.
    POST requests should be sent with a string in form of "collection_name.id".
    '''
    if request.method == 'GET':
        return humanify(get_mjs(current_user))

    elif request.method == 'POST':
        try:
            data = request.data
            # Enforce mjs structure:
            if not isinstance(data, str):
                abort(400, 'Expecting a string')

        except ValueError:
            e_message = 'Could not decode JSON from data'
            logger.debug(e_message)
            abort(400, e_message)

        add_to_my_story(data)
        return humanify(get_mjs())

@app.route('/upload', methods=['POST'])
@jwt_required()
@autodoc.doc()
def save_user_content():
    '''Logged in user POSTs a multipart request that includes a binary
    file and metadata.
    The server stores the metadata in the ugc collection and uploads the file
    to a bucket.
    Only the first file and set of metadata is recorded.
    After successful upload the server sends an email to editor.
    '''
    if not request.files:
        abort(400, 'No files present!')

    must_have_key_list = ['title',
                        'description',
                        'creator_name']

    form = request.form
    keys = form.keys()

    # Check that we have a full language specific set of fields

    must_have_keys = {
        '_en': {'missing': None, 'error': None},
        '_he': {'missing': None, 'error': None}
    }
    for lang in must_have_keys:
        must_have_list = [k+lang for k in must_have_key_list]
        must_have_set = set(must_have_list)
        must_have_keys[lang]['missing'] = list(must_have_set.difference(set(keys)))
        if must_have_keys[lang]['missing']:
            missing_keys = must_have_keys[lang]['missing']
            must_have_keys[lang]['error'] = gen_missing_keys_error(missing_keys)

    if must_have_keys['_en']['missing'] and must_have_keys['_he']['missing']:
        em_base = 'You must provide a full list of keys in English or Hebrew. '
        em = em_base + must_have_keys['_en']['error'] + ' ' +  must_have_keys['_he']['error']
        abort(400, em)

    # Set metadata language(s) to the one(s) without missing fields
    md_languages = []
    for lang in must_have_keys:
        if not must_have_keys[lang]['missing']:
            md_languages.append(lang)

    user_oid = current_user.id

    file_obj = request.files['file']
    filename = secure_filename(file_obj.filename)
    metadata = dict(form)
    metadata['user_id'] = str(user_oid)
    metadata['original_filename'] = filename
    metadata['Content-Type'] = mimetypes.guess_type(filename)[0]

    # Pick the first item for all the list fields in the metadata
    clean_md = {}
    for key in metadata:
        if type(metadata[key]) == list:
            clean_md[key] = metadata[key][0]
        else:
            clean_md[key] = metadata[key]

    # Make sure there are no empty keys for at least one of the md_languages
    empty_keys = {'_en': [], '_he': []}
    for lang in md_languages:
        for key in clean_md:
            if key.endswith(lang):
                if not clean_md[key]:
                    empty_keys[lang].append(key)

    # Check for empty keys of the single language with the full list of fields
    if len(md_languages) == 1 and empty_keys[md_languages[0]]:
        abort(400, "'{}' field couldn't be empty".format(empty_keys[md_languages[0]][0]))
    # Check for existence of empty keys in ALL the languages
    elif len(md_languages) > 1:
            if (empty_keys['_en'] and empty_keys['_he']):
                abort(400, "'{}' field couldn't be empty".format(empty_keys[md_languages[0]][0]))

    # Create a version of clean_md with the full fields only
    full_md = {}
    for key in clean_md:
        if clean_md[key]:
            full_md[key] = clean_md[key]

    # Get the magic file info
    file_info_str = magic.from_buffer(file_obj.stream.read())
    if not _validate_filetype(file_info_str):
        abort(415, "File type '{}' is not supported".format(file_info_str))

    # Rewind the file object
    file_obj.stream.seek(0)
    # Convert user specified metadata to BHP6 format
    bhp6_md = _convert_meta_to_bhp6(clean_md, file_info_str)
    bhp6_md['owner'] = str(user_oid)
    # Create a thumbnail and add it to bhp metadata
    try:
        binary_thumbnail = binarize_image(file_obj)
        bhp6_md['thumbnail'] = {}
        bhp6_md['thumbnail']['data'] = urllib.quote(binary_thumbnail.encode('base64'))
    except IOError as e:
        logger.debug('Thumbnail creation failed for {} with error: {}'.format(
            file_obj.filename, e.message))

    # Add ugc flag to the metadata
    bhp6_md['ugc'] = True
    # Insert the metadata to the ugc collection
    new_ugc = Ugc(bhp6_md)
    new_ugc.save()
    file_oid = new_ugc.id

    bucket = ugc_bucket
    saved_uri = upload_file(file_obj, bucket, file_oid, full_md, make_public=True)
    user_email = current_user.email
    user_name = current_user.name
    if saved_uri:
        console_uri = 'https://console.developers.google.com/m/cloudstorage/b/{}/o/{}'
        http_uri = console_uri.format(bucket, file_oid)
        mjs = get_mjs(user_oid)['mjs']
        if mjs == {}:
            logger.debug('Creating mjs for user {}'.format(user_email))
        # Add main_image_url for images (UnitType 1)
        if bhp6_md['UnitType'] == 1:
            ugc_image_uri = 'https://storage.googleapis.com/' + saved_uri.split('gs://')[1]
            new_ugc['ugc']['main_image_url'] = ugc_image_uri
            new_ugc.save()
        # Send an email to editor
        subject = 'New UGC submission'
        with open('editors_email_template') as fh:
            template = jinja2.Template(fh.read())
        body = template.render({'uri': http_uri,
                                'metadata': clean_md,
                                'user_email': user_email,
                                'user_name': user_name})
        sent = send_gmail(subject, body, editor_address, message_mode='html')
        if not sent:
            logger.error('There was an error sending an email to {}'.format(editor_address))
        clean_md['item_page'] = '/item/ugc.{}'.format(str(file_oid))

        return humanify({'md': clean_md})
    else:
        abort(500, 'Failed to save {}'.format(filename))

@app.route('/search')
@autodoc.doc()
def general_search():
    """
    This view initiates a full text search for `request.args.q` on the
    collection(s) specified in the `request.args.collection` or on all the
    searchable collections if nothing was specified.
    To search in 2 or more but not all collections, separate the arguments
    by comma: `collection=movies,places`
    The searchable collections are: 'movies', 'places', 'personalities',
    'photoUnits' and 'familyNames'.
    In addition to `q` and `collection`, the view could be passed `from_`
    and `size` arguments.
    `from_` specifies an integer for scrolling the result set and `size` specifies
    the maximum amount of documents in response.
    The view returns a json with an elasticsearch response.
    """
    args = request.args
    parameters = {'collection': None, 'size': 14, 'from_': 0, 'q': None}
    for param in parameters.keys():
        if param in args:
            parameters[param] = args[param]
    if not parameters['q']:
        abort(400, 'You must specify a search query')
    else:
        rv = es_search(**parameters)
        if not rv:
            abort(500, 'Sorry, the search cluster appears to be down')
        return humanify(rv)

@app.route('/wsearch')
def wizard_search():
    '''
    We must have either `place` or `name` (or both) of the keywords.
    If present, the keys must not be empty.
    '''
    args = request.args
    must_have_keys = ['place', 'name']
    keys = args.keys()
    if not ('place' in keys) and not ('name' in keys):
        em = "Either 'place' or 'name' key must be present and not empty"
        abort(400, em)

    validated_args = {'place': None, 'name': None}
    for k in must_have_keys:
        if k in keys:
            if args[k]:
                validated_args[k] = args[k]
            else:
                abort(400, "{} argument couldn't be empty".format(k))

    place = validated_args['place']
    name = validated_args['name']

    if place == 'havat_taninim' and name == 'tick-tock':
        return _generate_credits()

    place_doc = search_by_header(place, 'places', starts_with=False)
    name_doc = search_by_header(name, 'familyNames', starts_with=False)
    # fsearch() expects a dictionary of lists and returns Mongo cursor
    ftree_args = {}
    if name:
        ftree_args['last_name'] = [name]
    if place:
        ftree_args['birth_place'] = [place]

    # We turn the cursor to list in order to serialize it
    tree_found = list(fsearch(max_results=1, **ftree_args))
    if not tree_found and name and 'birth_place' in ftree_args:
        del ftree_args['birth_place']
        tree_found = list(fsearch(max_results=1, **ftree_args))
    rv = {'place': place_doc, 'name': name_doc}
    if tree_found:
        rv['ftree_args'] = ftree_args
    return humanify(rv)

@app.route('/suggest/<collection>/<string>')
def get_suggestions(collection,string):
    '''
    This view returns a json with 3 fields:
    "complete", "starts_with", "phonetic".
    Each field holds a list of up to 5 strings.
    '''
    rv = {}
    rv['starts_with'] = get_completion(collection, string)
    rv['contains'] = get_completion(collection, string, False)
    rv['phonetic'] = get_phonetic(collection, string)

    # make all the words in the suggestion start with a capital letter
    for k,v in rv.items():
        newv = []
        for i in v:
            newv.append(i.title())
        rv[k] = newv

    return humanify(rv)


@app.route('/item/<item_id>')
@autodoc.doc()
def get_items(item_id):
    '''
    This view returns a list of jsons representing one or more item(s).
    The item_id argument is in the form of "collection_name.item_id", like
    "personalities.112998" and could contain multiple IDs split by commas.
    Only the first 10 ids will be returned to prevent abuse.
    By default we don't return the documents that fail the show_filter,
    unless a `debug` argument was provided.
    '''
    args = request.args

    items_list = item_id.split(',')
    # Check if there are items from ugc collection and test their access control
    ugc_items = []
    for item in items_list:
        if item.startswith('ugc'):
            ugc_items.append(item)
    if ugc_items:
        # Check if the user is logged in
        try:
            verify_jwt()
            user_oid = current_user.id
        except JWTError as e:
            logger.debug(e.description)
            abort(403, 'You have to be logged in to access this item(s)')

    items = fetch_items(items_list[:10])
    if len(items) == 1 and items[0].has_key('error_code'):
        error = items[0]
        abort (error['error_code'],  error['msg'])
    else:
        # Cast items to list
        if type(items) != list:
            items = [items]
        # Check that each of the ugc_items is accessible by the logged in user
        for ugc_item_id in [i[4:] for i in ugc_items]:
            for item in items:
                if item['_id'] == ugc_item_id and item.has_key('owner') and item['owner'] != unicode(user_oid):
                    abort(403, 'You are not authorized to access item ugc.{}'.format(str(item['_id'])))
        return humanify(items)

@app.route('/fsearch')
@autodoc.doc()
def ftree_search():
    '''
    This view initiates a search for Beit HaTfutsot genealogical data.
    The search supports numerous fields and unexact values for search terms.
    For example, to get all individuals whose last name sounds like Abulafia
    and first name is Hanna:
    curl 'api.myjewishidentity.org/fsearch?last_name=Abulafia;phonetic&first_name=Hanna'
    The full list of fields and their possible options follows:
    _______________________________________________________________________
    first_name
    maiden_name
    last_name
    birth_place
    marriage_place
    death_place
    The *_place and *_name fields could be specified exactly,
    by the prefix (this is the only kind of "regex" we currently support)
    or phonetically.
    To match by the last name yehuda, use yehuda
    To match by the last names that start with yehud, use yehuda;prefix
    To match by the last names that sound like yehud, use yehuda;phonetic
    _______________________________________________________________________
    birth_year
    marriage_year
    death_year
    The *_year fields could be specified as an integer with an optional fudge
    factor signified by a tilda, like 1907~2
    The query for birth_year 1907 will match the records from this year only,
    while the query for 1907~2 will match the records from 1905, 1906, 1907
    1908 and 1909, making the match wider.
    _______________________________________________________________________
    sex
    The sex field value could be either m or f.
    _______________________________________________________________________
    tree_number
    The tree_number field value could be an integer with a valid tree number,
    like 7806
    '''
    args = request.args
    keys = args.keys()
    if len(keys) == 0:
        em = "At least one search field has to be specified"
        abort (400, em)
    if len(keys) == 1 and keys[0]=='sex':
        em = "Sex only is not enough"
        abort (400, em)
    results = fsearch(**args)
    return humanify(results)

@app.route('/get_ftree_url/<tree_number>')
def fetch_tree(tree_number):
    try:
        tree_number = int(tree_number)
    except ValueError:
        abort(400, 'Tree number must be an integer')
    ftree_bucket_url = conf.ftree_bucket_url
    collection = data_db['genTreeIndividuals']
    tree = collection.find_one({'GTN': tree_number})
    if tree:
        tree_path = tree['GenTreePath']
        tree_fn = tree_path.split('/')[-1]
        rv = {'tree_file': '{}/{}'.format(ftree_bucket_url, tree_fn)}
        return humanify(rv)
    else:
        abort(404, 'Tree {} not found'.format(tree_number))

@app.route('/fwalk/<tree_number>/<node_id>')
@autodoc.doc()
def ftree_walk(tree_number, node_id):
    '''
    This view returns a part of family tree starting with a given tree number
    and node id.
    '''
    dest_bucket_name = os.path.join('/data', 'bhs-familytrees-json',
                                    str(tree_number),node_id+'.json')
    try:
        fd = open(dest_bucket_name)
    except IOError, e:
        abort(404, str(e))
    data = fd.read()
    fd.close()
    resp = Response(data, mimetype='application/json')
    resp.status_code = 200
    return resp

@app.route('/get_image_urls/<image_ids>')
def fetch_images(image_ids):
    """Validate the comma separated list of image UUIDs and return a list
    of links to these images.
    Will return only 10 first results.
    """

    valid_ids = []
    image_urls = []
    image_id_list = image_ids.split(',')[:10]

    for i in image_id_list:
        if not i:
            continue
        try:
            UUID(i)
            valid_ids.append(i)
        except ValueError:
            logger.debug('Wrong UUID - {}'.format(i))
            continue

    image_urls = [get_image_url(i) for i in valid_ids]
    return humanify(image_urls)


@app.route('/get_changes/<from_date>/<to_date>')
@autodoc.doc()
def get_changes(from_date, to_date):
    '''
    This view returns the item_ids of documents that were updated during the
    date range specified by the arguments. The dates should be supplied in the
    timestamp format.
    '''
    rv = set()
    # Validate the dates
    dates = {'start': from_date, 'end': to_date}
    for date in dates:
        try:
            dates[date] = datetime.fromtimestamp(float(dates[date]))
        except ValueError:
            abort(400, 'Bad timestamp - {}'.format(dates[date]))

    log_collection = data_db['migration_log']
    query = {'date': {'$gte': dates['start'], '$lte': dates['end']}}
    projection = {'item_id': 1, '_id': 0}
    cursor = log_collection.find(query, projection)
    if not cursor:
        return humanify([])
    else:
        for doc in cursor:
            col, _id = doc['item_id'].split('.')
            if col == 'genTreeIndividuals':
                continue
            else:
                if filter_doc_id(_id, col):
                    rv.add(doc['item_id'])
    return humanify(list(rv))

if __name__ == '__main__':
    app.run('0.0.0.0')
