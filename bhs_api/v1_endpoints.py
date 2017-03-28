#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import cPickle
from datetime import timedelta, datetime
import re
import urllib
import mimetypes
from uuid import UUID
import json

from flask import Flask, Blueprint, request, abort, url_for, current_app
from flask.ext.security import auth_token_required
from flask.ext.security import current_user
from itsdangerous import URLSafeSerializer, BadSignature
from werkzeug import secure_filename, Response
from werkzeug.exceptions import NotFound, Forbidden, BadRequest
import elasticsearch
import pymongo
import jinja2
import requests

from bhs_api import SEARCH_CHUNK_SIZE
from bhs_api.utils import (get_conf, gen_missing_keys_error, binarize_image,
                           upload_file, send_gmail, humanify, SEARCHABLE_COLLECTIONS)
from bhs_api.user import collect_editors_items
from bhs_api.item import (fetch_items, search_by_header, get_image_url,
                          enrich_item, SHOW_FILTER)
from bhs_api.fsearch import fsearch
from bhs_api.user import get_user

from bhs_api import phonetic

v1_endpoints = Blueprint('v1', __name__)

def get_activation_link(user_id):
    s = URLSafeSerializer(current_app.secret_key)
    payload = s.dumps(user_id)
    return url_for('activate_user', payload=payload, _external=True)


'''
class Ugc(db.Document):
    ugc = db.DictField()

def custom_error(error):
    return humanify({'error': error.description}, error.code)
for i in [400, 403, 404, 405, 409, 415, 500]:
    app.error_handler_spec[None][i] = custom_error
'''


def es_search(q, size, collection=None, from_=0, sort=None):
    # body = {"query": { "match" : { "_all": {"query": q, "operator": "and"} }}}
    body = {"query": { "query_string" : {
        "fields": ['Header.En^2', 'Header.He^2', 'UnitText1.En', 'UnitText1.He'],
        "query": q,
        "default_operator": "and"
    }}}
    if sort == "abc":
        if phonetic.is_hebrew(q.strip()):
            # hebrew alphabetical sort
            body["sort"] = [{"Header.He_lc": "asc"}, "_score"]
        else:
            # english alphabetical sort
            body["sort"] = [{"Header.En_lc": "asc"}, "_score"]
    elif sort == "rel":
        # relevance sort
        body["sort"] = ["_score"]
    elif sort == "year" and collection == "photoUnits":
        body["sort"] = [{"UnitPeriod.PeriodStartDate.keyword": "asc"}, "_score"]
    try:
        try:
            collection = collection.split(',')
        except:
            pass
        current_app.logger.debug("es.search index={}, doc_type={} body={}".format(current_app.es_data_db_index_name, collection, json.dumps(body)))
        results = current_app.es.search(index=current_app.es_data_db_index_name, body=body,
                            doc_type=collection, size=size, from_=from_)
    except elasticsearch.exceptions.ConnectionError as e:
        current_app.logger.error('Error connecting to Elasticsearch: {}'.format(e.error))
        return None
    return results

def _generate_credits(fn='credits.html'):
    try:
        fh = open(fn)
        credits = fh.read()
        fh.close()
        return credits
    except:
        current_app.logger.debug("Couldn't open credits file {}".format(fn))
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
        current_app.logger.debug('Failed to match UnitType for "{}"'.format(file_info))
    # Add the raw upload data to rv
    rv['raw'] = no_lang
    return rv

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

def get_completion_all_collections(string, size=7):
    text_completion_result = {}
    phonetic_result = {}
    for collection in SEARCHABLE_COLLECTIONS:
        text_completion_result[collection], phonetic_result[collection] = get_completion(collection, string, size)
    return text_completion_result, phonetic_result

def get_completion(collection, string, size=7):
    '''Search in the elastic search index for completion options.
    Returns tuple of (text_completion_results, phonetic_results)
    Where each array contains up to `size` results.
    '''
    # currently we only do a simple starts with search, without contains or phonetics
    # TODO: fix phonetics search, some work was done for that
    # see https://github.com/Beit-Hatfutsot/dbs-back/blob/2e79c363e40472f28fd07f8a344fe55ab77198ee/bhs_api/v1_endpoints.py#L189
    lang = "He" if phonetic.is_hebrew(string) else "En"
    q = {
        "_source": ["Slug", "Header"],
        "suggest": {
            "header" : {
                "prefix": string,
                "completion": {
                    "field": "Header.{}.suggest".format(lang),
                    "size": size,
                    "contexts": {
                        "collection": collection,
                    }
                }
            },
        }
    }
    q["suggest"]["header"]["completion"]["contexts"] = {"collection": collection}
    results = current_app.es.search(index=current_app.es_data_db_index_name, body=q, size=0)
    try:
        header_options = results['suggest']['header'][0]['options']
    except KeyError:
        header_options = []
    try:
        phonetic_options = results['suggest']['phonetic'][0]['options']
    except KeyError:
        phonetic_options = []
    return  [i['_source']['Header'][lang] for i in header_options], [i['_source']['Header'][lang] for i in phonetic_options]


def get_phonetic(collection, string, limit=5):
    collection = current_app.data_db[collection]
    retval = phonetic.get_similar_strings(string, collection)
    return retval[:limit]


@v1_endpoints.route('/upload', methods=['POST'])
@auth_token_required
def save_user_content():
    import magic

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
        current_app.logger.debug('Thumbnail creation failed for {} with error: {}'.format(
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
        mjs = current_user.get_mjs()['mjs']
        if mjs == {}:
            current_app.logger.debug('Creating mjs for user {}'.format(user_email))
        # Add main_image_url for images (UnitType 1)
        if bhp6_md['UnitType'] == 1:
            ugc_image_uri = 'https://storage.googleapis.com/' + saved_uri.split('gs://')[1]
            new_ugc['ugc']['main_image_url'] = ugc_image_uri
            new_ugc.save()
        # Send an email to editor
        subject = 'New UGC submission'
        with open('templates/editors_email_template') as fh:
            template = jinja2.Template(fh.read())
        body = template.render({'uri': http_uri,
                                'metadata': clean_md,
                                'user_email': user_email,
                                'user_name': user_name})
        sent = send_gmail(subject, body, editor_address, message_mode='html')
        if not sent:
            current_app.logger.error('There was an error sending an email to {}'.format(editor_address))
        clean_md['item_page'] = '/item/ugc.{}'.format(str(file_oid))

        return humanify({'md': clean_md})
    else:
        abort(500, 'Failed to save {}'.format(filename))

@v1_endpoints.route('/search')
def general_search():
    args = request.args
    parameters = {'collection': None, 'size': SEARCH_CHUNK_SIZE, 'from_': 0, 'q': None, 'sort': None}
    for param in parameters.keys():
        if param in args:
            parameters[param] = args[param]
    if not parameters['q']:
        abort(400, 'You must specify a search query')
    else:
        rv = es_search(**parameters)
        if not rv:
            abort(500, 'Sorry, the search cluster appears to be down')
        else:
            for item in rv['hits']['hits']:
                enrich_item(item['_source'], collection_name=item['_type'])
        return humanify(rv)

@v1_endpoints.route('/wsearch')
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
    ''' TODO: restore family trees
    tree_found = list(fsearch(max_results=1, **ftree_args))
    if not tree_found and name and 'birth_place' in ftree_args:
        del ftree_args['birth_place']
        tree_found = list(fsearch(max_results=1, **ftree_args))
    '''
    rv = {'place': place_doc, 'name': name_doc}
    ''' TODO: restore family trees
    if tree_found:
        rv['ftree_args'] = ftree_args
    '''
    return humanify(rv)

@v1_endpoints.route('/suggest/<collection>/<string>')
def get_suggestions(collection,string):
    '''
    This view returns a json with 3 fields:
    "complete", "starts_with", "phonetic".
    Each field holds a list of up to 5 strings.
    '''
    rv = {}
    try:
        if collection == "*":
            rv['starts_with'], rv['phonetic'] = get_completion_all_collections(string)
            rv['contains'] = {}
            # make all the words in the suggestion start with a capital letter
            rv = {k: {kk: [i.title() for i in vv] for kk, vv in v.items()} for k, v in rv.items()}
            return humanify(rv)
        else:
            rv['starts_with'], rv['phonetic'] = get_completion(collection, string)
            rv['contains'] = []
            # make all the words in the suggestion start with a capital letter
            rv = {k: [i.title() for i in v] for k, v in rv.items()}
            return humanify(rv)
    except Exception, e:
        return humanify({"error": "unexpected exception getting completion data: {}".format(e)}, 500)



@v1_endpoints.route('/item/<slugs>')
def get_items(slugs):
    if slugs:
        items_list = slugs.split(',')
    elif request.is_json:
        items_list = request.get_json()

    # Check if there are items from ugc collection and test their access control
    ugc_items = []
    for item in items_list:
        if item.startswith('ugc'):
            ugc_items.append(item)
    user_oid = current_user.is_authenticated and current_user.id

    items = fetch_items(items_list)
    if len(items) == 1 and 'error_code' in items[0]:
        error = items[0]
        abort(error['error_code'],  error['msg'])
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

@v1_endpoints.route('/person')
def ftree_search():
    args = request.args
    keys = args.keys()
    if len(keys) == 0:
        em = "At least one search field has to be specified"
        abort (400, em)
    if len(keys) == 1 and keys[0]=='sex':
        em = "Sex only is not enough"
        abort (400, em)
    total, items = fsearch(**args)
    return humanify({"items": items, "total": total})

@v1_endpoints.route('/get_image_urls/<image_ids>')
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
            current_app.logger.debug('Wrong UUID - {}'.format(i))
            continue

    image_urls = [get_image_url(i) for i in valid_ids]
    return humanify(image_urls)


@v1_endpoints.route('/get_changes/<from_date>/<to_date>')
def get_changes(from_date, to_date):
    rv = set()
    # Validate the dates
    dates = {'start': from_date, 'end': to_date}
    for date in dates:
        try:
            dates[date] = datetime.fromtimestamp(float(dates[date]))
        except ValueError:
            abort(400, 'Bad timestamp - {}'.format(dates[date]))

    log_collection = current_app.data_db['migration_log']
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

@v1_endpoints.route('/newsletter', methods=['POST'])
def newsletter_register():
    data = request.json
    for lang in data['langs']:
        res = requests.post(
            "https://webapi.mymarketing.co.il/Signup/PerformOptIn.aspx",
            data={'mm_userid': 59325,
                'mm_key': lang,
                'mm_culture': 'he',
                'mm_newemail': data['email'],
                }
        )
        if res.status_code == 200:
            return ''

        abort(500, """Got status code {} from https://webapi.mymarketing.co.il
                      when trying to register {} for {}""".format(
                          res.status_code, data['email'], date['langs'])
             )
        log = open("var/log/bhs/newsletters.log", "a")
        log.write("  ".join([res.status_code, data['email'], date['langs']]))
        log.close()


@v1_endpoints.route('/collection/<name>')
def get_collection(name):
    items = collect_editors_items(name)
    return humanify ({'items': items})

@v1_endpoints.route('/story/<hash>')
def get_story(hash):
    user = get_user(hash)
    del user['email']
    return humanify (user)

@v1_endpoints.route('/geo/places')
def get_geocoded_places():
    args = request.args
    filters = SHOW_FILTER.copy()
    filters['geometry'] = {'$exists': True}
    filters['Header.En'] = {'$nin' : [None, '']}
    try:
        filters['geometry.coordinates.1'] = {'$gte': float(args['sw_lat']), '$lte': float(args['ne_lat'])}
        filters['geometry.coordinates.0'] = {'$gte': float(args['sw_lng']), '$lte': float(args['ne_lng'])}
    except KeyError:
        abort(400, 'Please specify a box using sw_lat, sw_lng, ne_lat, ne_lng')
    except ValueError:
        abort(400, 'Please specify a box using floats in sw_lat, sw_lng, ne_lat, ne_lng')
    points = current_app.data_db['places'].find(filters, {'Header': True,
        'Slug': True, 'geometry': True, 'PlaceTypeDesc': True})
    ret = humanify(list(points))
    return ret

