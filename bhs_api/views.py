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
import requests

from bhs_api import app, db, logger, data_db, autodoc, conf, es
from bhs_common.utils import (get_conf, gen_missing_keys_error, binarize_image,
                              get_unit_type, SEARCHABLE_COLLECTIONS)
from utils import (get_logger, upload_file, send_gmail, humanify,
                   get_referrer_host_url, dictify)
from bhs_api.user import (get_user_or_error, clean_user, send_activation_email,
            user_handler, is_admin, get_mjs, add_to_my_story, set_item_in_branch,
            remove_item_from_story)
from bhs_api.item import (fetch_items, search_by_header, get_image_url,
                          SHOW_FILTER)
from bhs_api.fsearch import fsearch

import phonetic


def get_activation_link(user_id):
    s = URLSafeSerializer(app.secret_key)
    payload = s.dumps(user_id)
    return url_for('activate_user', payload=payload, _external=True)

# While searching for docs, we always need to filter results by their work
# status and rights.
# We also filter docs that don't have any text in the 'UnitText1' field.
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

'''
def custom_error(error):
    return humanify({'error': error.description}, error.code)
for i in [400, 403, 404, 405, 409, 415, 500]:
    app.error_handler_spec[None][i] = custom_error
'''


def es_search(q, collection=None, size=14, from_=0):
    body = es_show_filter
    query_body = body['query']['filtered']['query']['query_string']
    query_body['query'] = q
    # Boost the header by  2:
    # https://www.elastic.co/guide/en/elasticsearch/reference/1.7/query-dsl-query-string-query.html
    query_body['fields'] = ['Header.En^2', 'Header.He^2', 'UnitText1.En', 'UnitText1.He']
    try:
        try:
            collection = collection.split(',')
        except:
            pass
        results = es.search(index=data_db.name, body=body, doc_type=collection, size=size, from_=from_)
    except elasticsearch.exceptions.ConnectionError as e:
        logger.error('Error connecting to Elasticsearch: {}'.format(e.error))
        return None
    return results

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
    show_filter = SHOW_FILTER.copy()
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
    The item_id argument is in the form of "collection_name.item_slug", like
    "personalities.albert_einstein" and could contain multiple IDs split
    by commas.
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
    factor signified by a collon, like 1907:2
    The query for birth_year 1907 will match the records from this year only,
    while the query for 1907:2 will match the records from 1905, 1906, 1907
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
    items = fsearch(**args)
    return humanify({"items": items, "total": items.count()})

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

@app.route('/person/<tree_number>/<node_id>')
@autodoc.doc()
def person_view(tree_number, node_id):
    '''
    This view returns a part of family tree starting with a given tree number
    and node id.
    '''
    person = data_db['genTreeIndividuals'].find_one({'GTN': int(tree_number),
                                                'II': node_id})
    # TODO: who cleans the living? should be here if not part of the migration
    if not person:
        abort(404, 'person not found')
    return humanify(person)

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

@app.route('/newsletter', methods=['POST'])
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
