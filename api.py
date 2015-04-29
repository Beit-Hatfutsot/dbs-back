#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import timedelta
import json
from bson import json_util
import re
import urllib
import mimetypes
import magic

from flask import Flask, request, abort
from flask.ext.mongoengine import MongoEngine, ValidationError
from flask.ext.security import Security, MongoEngineUserDatastore, \
    UserMixin, RoleMixin, login_required
from flask.ext.security.utils import encrypt_password, verify_password
from flask.ext.cors import CORS
from flask_jwt import JWT, JWTError, jwt_required, verify_jwt
from  flask.ext.jwt import current_user

from werkzeug import secure_filename

import pymongo
import jinja2

from bhs_common.utils import get_conf, gen_missing_keys_error, binarize_image
from utils import get_logger, upload_file, get_oid, jsonify, send_gmail
import phonetic

import pdb

# Create app
app = Flask(__name__)

# Specify the bucket name for user generated content
ugc_bucket = 'bhs-ugc'

# Specify the email address of the editor for UGC moderation
#editor_address = 'pavel.suchman@gmail.com'
editor_address = 'pavel.suchman@bh.org.il,dannyb@bh.org.il'

# Get configuration from file
must_have_keys = set(['secret_key',
                    'security_password_hash',
                    'security_password_salt',
                    'user_db_host',
                    'user_db_port',
                    'user_db_name',
                    'data_db_host',
                    'data_db_port',
                    'data_db_name'])

conf = get_conf('/etc/bhs/config.yml', must_have_keys)

# Set app config
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = conf.secret_key
app.config['SECURITY_PASSWORD_HASH'] = conf.security_password_hash
app.config['SECURITY_PASSWORD_SALT'] = conf.security_password_salt
app.config['JWT_EXPIRATION_DELTA'] = timedelta(days=1)

# DB Config
app.config['MONGODB_DB'] = conf.user_db_name
app.config['MONGODB_HOST'] = conf.user_db_host
app.config['MONGODB_PORT'] = conf.user_db_port

# Logging config
logger = get_logger()

#allow CORS
cors = CORS(app, origins=['*'], headers=['content-type', 'accept', 'Authorization'])

# Set up the JWT Token authentication
jwt = JWT(app)
@jwt.authentication_handler
def authenticate(username, password):
    # We must use confusing email=username alias until the flask-jwt
    # author merges request #31
    # https://github.com/mattupstate/flask-jwt/pull/31
    user_obj = user_datastore.find_user(email=username)
    if not user_obj:
        logger.debug('User {} not found'.format(username))
        return None

    if verify_password(password, user_obj.password):
        # make user.id jsonifiable
        user_obj.id = str(user_obj.id)
        return user_obj
    else:
        logger.debug('Wrong password for {}'.format(username))
        return None

@jwt.user_handler
def load_user(payload):
    user_obj = user_datastore.find_user(id=payload['user_id'])
    return user_obj

# Create database connection object
db = MongoEngine(app)
data_db = pymongo.Connection(conf.data_db_host, conf.data_db_port, slaveOK=True)[conf.data_db_name]

class Role(db.Document, RoleMixin):
    name = db.StringField(max_length=80, unique=True)
    description = db.StringField(max_length=255)

class User(db.Document, UserMixin):
    email = db.StringField(max_length=255)
    password = db.StringField(max_length=255)
    name = db.StringField(max_length=255)
    active = db.BooleanField(default=True)
    confirmed_at = db.DateTimeField()
    roles = db.ListField(db.ReferenceField(Role))

class Mjs(db.Document):
    mjs = db.DictField()

class Ugc(db.Document):
    ugc = db.DictField()

# Ensure we have a user to test with
@app.before_first_request
def setup_users():
    for role_name in ('user', 'admin'):
        if not user_datastore.find_role(role_name):
            logger.debug('Creating role %s' % role_name)
            user_datastore.create_role(name=role_name)

    user_role = user_datastore.find_role('user')
    if not user_datastore.get_user('tester@example.com'):
        logger.debug('Creating test user.')
        user_datastore.create_user(email='tester@example.com',
                                   name='Test User',
                                   password=encrypt_password('password'),
                                   roles=[user_role])

# Setup Flask-Security
user_datastore = MongoEngineUserDatastore(db, User, Role)
security = Security(app, user_datastore)


# Stubs for custom error handlers
@app.errorhandler(400)
def custom_400(error):
    # Bad Request
    response = humanify({'error': error.description})
    return response, 400

@app.errorhandler(403)
def custom_403(error):
    # Forbidden
    response = humanify({'error': error.description})
    return response, 403

@app.errorhandler(404)
def custom_404(error):
    # Not Found
    response = humanify({'error': error.description})
    return response, 404

@app.errorhandler(405)
def custom_405(error):
    # Method not allowed
    response = humanify({'error': error.description})
    return response, 405

@app.errorhandler(409)
def custom_409(error):
    # Conflict
    response = humanify({'error': error.description})
    return response, 409

@app.errorhandler(415)
def custom_415(error):
    # Unsupported Media Type
    response = humanify({'error': error.description})
    return response, 415

@app.errorhandler(500)
def custom_500(error):
    # Internal Server Error
    response = humanify({'error': error.description})
    return response, 500

# Utility functions
def humanify(obj):
    'Adds newline to Json responses to make CLI debugging easier'
    # jsonify function doesn't work with lists
    if type(obj) == list:
        return json.dumps(obj, default=json_util.default, indent=2) + '\n'
    elif type(obj) == pymongo.cursor.Cursor:
        rv = []
        for doc in obj:
            doc['_id'] = str(doc['_id'])
            rv.append(json.dumps(doc, default=json_util.default, indent=2))
        return '[' + ',\n'.join(rv) + ']' + '\n'
    else:
        resp = jsonify(obj)
        resp.set_data(resp.data+'\n')
        return resp

def is_admin(flask_user_obj):
    if flask_user_obj.has_role('admin'):
        return True
    else:
        return False

def mask_dict(from_dict, allowed_keys):
    'Return only allowed keys'
    rv = {}
    for key in allowed_keys:
        if from_dict.has_key(key):
            rv[key] = from_dict[key]
    return rv

def dictify(m_engine_object):
    # ToDo: take care of $oid conversion to string
    return json.loads(m_engine_object.to_json())

# User management
def user_handler(user_id, method, data):
    if data:
        try:
            data = json.loads(data)
            if type(data) != dict:
                abort(400, 'Only dict like objects are supported for user management')
        except ValueError:
            e_message = 'Could not decode JSON from data'
            logger.debug(e_message)
            abort(400, e_message)

    if method == 'GET':
        return humanify(get_user(user_id))

    elif method == 'POST':
        if not data:
            abort(400, 'No data provided')
        return humanify(create_user(data))

    elif method == 'PUT':
        if not data:
            abort(400, 'No data provided')
        return humanify(update_user(user_id, data))

    elif method == 'DELETE':
        return humanify(delete_user(user_id))

def _get_user_or_error(user_id):
    user = user_datastore.get_user(user_id)
    if user:
        return user
    else:
        raise abort(404, 'User not found')

def _clean_user(user_obj):
    user_dict = dictify(user_obj)
    allowed_fields = ['email', 'name']
    masked_user_dict = mask_dict(user_dict, allowed_fields)
    return masked_user_dict

def get_user(user_id):
    user_obj = _get_user_or_error(user_id)
    return _clean_user(user_obj)

def delete_user(user_id):
    user = _get_user_or_error(user_id)
    if is_admin(user):
        return {'error': 'God Mode!'}
    else:
        user.delete()
        return {}

def create_user(user_dict):
    try:
        email = user_dict['email']
        name = user_dict['name']
        enc_password = encrypt_password(user_dict['password'])
    except KeyError as e:
        e_message = '%s key is missing from data' % e
        logger.debug(e_message)
        abort(400, e_message)

    user_exists = user_datastore.get_user(email)
    if user_exists:
        e_message = 'User %s with email %s already exists' % (str(user_exists.id), email)
        logger.debug(e_message)
        abort(409, e_message)

    created = user_datastore.create_user(email=email,
                                        name=name,
                                        password=enc_password)
    # Add default role to a newly created user
    user_datastore.add_role_to_user(created, 'user')

    return _clean_user(created)

def update_user(user_id, user_dict):
    user_obj = _get_user_or_error(user_id)
    if 'email' in user_dict.keys():
        user_obj.email = user_dict['email']
    if 'name' in user_dict.keys():
        user_obj.email = user_dict['name']
    if 'password' in user_dict.keys():
        enc_password = encrypt_password(user_dict['password'])
        user_obj.password = enc_password

    user_obj.save()
    return _clean_user(user_obj)

######################################################################################

def get_mjs(user_oid):
    mjs = Mjs.objects(id=user_oid).first()
    if mjs:
        return dictify(mjs)
    else:
        logger.debug('Mjs not found for user {}'.format(str(user_oid)))
        return {'mjs':{}}

def update_mjs(user_oid, data):
    new_mjs = Mjs(id=user_oid, mjs = data)
    try:
        new_mjs.save()
        return new_mjs
    except ValidationError as e:
        logger.debug('Error occured while saving mjs data for user {}'.format(str(user_oid)))
        logger.debug(e.message) 
        abort(500, e.message)

def _init_mjs():
    return {'assigned': [],
            'unassigned': []}

def fetch_items(item_list):
    if len(item_list) == 1:
        return _fetch_item(item_list[0])
    else:
        rv = []
        for item in item_list:
            if item: # Drop empty items
                rv.append( _fetch_item(item))
        return rv

def _fetch_item(item_id):
    if not '.' in item_id: # Need colection.id to unpack
        return {}
    collection, _id = item_id.split('.')[:2]
    oid = get_oid(_id)
    if not oid:
        return {}
    if collection == 'ugc':
        item = dictify(Ugc.objects(id=oid).first())
        if item:
            item_id = item['_id']
            item = item['ugc']
            item['_id'] = item_id
            if (type(item['_id']) == dict and item['_id'].has_key('$oid')):
                item['_id'] = item['_id']['$oid']
    else:
        item = data_db[collection].find_one(oid)

    if item:
        if item.has_key('Header'):
            # Only add related and thumbnail if our item has header
            # HACK TO GET RELATED WHILE THERE IS NO REAL DATA
            item['related'] = _get_related(item)
            # HACK TO GET THUMBNAIL
            if not 'thumbnail' in item.keys():
                item['thumbnail'] = _get_thumbnail(item)

        return _make_serializable(item)
    else:
        return {}

def _get_related(doc, max_items=5):
    """
    THIS IS A HACK TO MOCK REAL RELATED DATA
    """
    related = []
    collections = ['familyNames',
                   'places',
                   'photoUnits']

    if doc['UnitType'] == 1:
        # Don't look for related items in photo units (UnitType 1)
        return []

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
            # No headers at all
            return []
        # Create text indices for text search to work:
        # db.YOUR_COLLECTION.createIndex({"UnitText1.En": "text", "UnitText1.He": "text"})
        cursor = col.find({'$text': {'$search': headers}}).limit(max_items)
        if cursor:
            for related_item in cursor:
                related_item = _make_serializable(related_item)
                if not _make_serializable(doc)['_id'] == related_item['_id']:
                    related_string = collection_name + '.' + related_item['_id']
                    related.append(related_string)
    
    return related

def _get_picture(picture_id):
    found = data_db['photos'].find_one({'PictureId': picture_id})
    return found

def _get_thumbnail(doc):
    thumbnail = ''
    path = ''
    if 'Pictures' in doc.keys():
        for pic in doc['Pictures']:
            if 'IsPreview' in pic.keys() and 'PictureId' in pic.keys() and pic['IsPreview'] == '1':
                picture = _get_picture(pic['PictureId'])
                if not picture.has_key('bin'):
                    return {}
                thumbnail = picture['bin']
                if 'PictureFileName' in picture.keys():
                    path = picture['PicturePath']
    elif 'RelatedPictures' in doc.keys():
        for pic in doc['RelatedPictures']:
            if 'IsPreview' in pic.keys() and 'PictureId' in pic.keys() and pic['IsPreview'] == '1':
                picture = _get_picture(pic['PictureId'])
                if not picture.has_key('bin'):
                    return {}
                thumbnail = picture['bin']
                if 'PictureFileName' in picture.keys():
                    path = picture['PicturePath']
    
    return {
        'data': urllib.quote(thumbnail.encode('base-64')), 
        'path': urllib.quote(path.replace('\\', '/'))
    }

def _make_serializable(obj):
    # ToDo: Replace with json.dumps with default setting and check
    # Make problematic fields Json serializable
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
            if lang['values'].has_key(bhp6_to_ugc[key]):
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

def search_by_header(string, collection):
    if not string: # Support empty strings
        return {}
    if phonetic.is_hebrew(string):
        lang = 'He'
    else:
        lang = 'En'
    header_regex = re.compile(string, re.IGNORECASE)
    lang_header = 'Header.{}'.format(lang)
    unit_text = 'UnitText1.{}'.format(lang)
    # Search only for docs with right status
    show_filter = {'StatusDesc': 'Completed',
                   'RightsDesc': 'Full',
                   unit_text: {"$nin": [None, '']}}
    header_search_ex = {lang_header: header_regex}
    header_search_ex.update(show_filter)
    item = data_db[collection].find_one(header_search_ex)
    
    if item:
        # HACK TO GET RELATED WHILE THERE IS NO REAL DATA
        item['related'] = _get_related(item)
        # HACK TO GET THUMBNAIL
        item['thumbnail'] = _get_thumbnail(item)

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
        regex = re.compile('^%s' % string, re.IGNORECASE)
    else:
        regex = re.compile(string, re.IGNORECASE)

    found = []
    header = 'Header.{}'.format(lang)
    unit_text = 'UnitText1.{}'.format(lang)
    show_filter = {'StatusDesc': 'Completed',
                   'RightsDesc': 'Full',
                   unit_text: {"$nin": ['', None]}}
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

def fsearch(max_results=5000,**kwargs):
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
                abort(400, "Sex must be on of 'm', 'f'")
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
                  'GTN': 1,   # GenTree Number
                  'LN': 1,   # Last name
                  'FN': 1,   # First Name
                  'IBLN': 1, # Maiden name
                  'BD': 1,   # Birth date
                  'BP': 1,   # Birth place
                  'DD': 1,   # Death date
                  'DP': 1,   # Death place
                  'G': 1,    # Gender
                  'MD': 1,   # Marriage dates as comma separated string
                  'MP': 1}   # Marriage places as comma separated string

    if 'debug' in search_dict.keys():
        projection = None

    results = collection.find(search_query, projection).limit(max_results)
    if results.count() > 0:
        logger.debug('Found {} results'.format(results.count()))
        return results
    else:
        return []

def _generate_year_range(year, fudge_factor=0):
    maximum = int(str(year + fudge_factor) + '9999')
    minimum = int(str(year - fudge_factor) + '0000')
    return {'min': minimum, 'max': maximum}


# Views
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
            return user_handler(None, request.method, request.data)
        else:
            logger.debug(e.description)
            abort(403)

    if user_id:
        # admin access_mode
        if is_admin(current_user):
            return user_handler(user_id, request.method, request.data)
        else:
            logger.debug('Non-admin user %s tried to access user id %s' % (
                                                current_user.email, user_id))
            abort(403)
    else:
        # user access_mode
        user_id = str(current_user.id)
        # Deny POSTing to logged in non-admin users to avoid confusion with PUT
        if request.method == 'POST':
            abort(400, 'POST method is not supported for logged in users.')
        return user_handler(user_id, request.method, request.data)

@app.route('/mjs', methods=['GET', 'PUT'])
@jwt_required()
def manage_jewish_story():
    '''Logged in user may GET or PUT their mjs metadata - a dict
    with the following structure:
    {
      'assigned': [
        {'name': 'branch_name_1', 'items': []},
        {'name': 'branch_name_2', 'items': []}, etc...
      ],
      'unassigned': []
    }
    Each metadata member is a string in form of "collection_name.id".
    A PUT request must include ALL the metadata, not just the new object!
    The data is saved as an object in the mjs collection while its _id
    equals to this of the updating user.
    '''
    user_oid = current_user.id
    if request.method == 'GET':
        mjs = get_mjs(user_oid)
        return humanify(mjs['mjs'])

    elif request.method == 'PUT':
        try:
            data = json.loads(request.data)
            # Enforce mjs structure:
            if not type(data) == dict:
                abort(400, 'Expecting an object')
            must_have_keys = set(['assigned', 'unassigned'])
            keys = data.keys()
            missing_keys = list(must_have_keys.difference(set(keys)))
            if missing_keys != []:
                e_message = gen_missing_keys_error(missing_keys)
                abort(400, e_message)

        except ValueError:
            e_message = 'Could not decode JSON from data'
            logger.debug(e_message)
            abort(400, e_message)

        return humanify(update_mjs(user_oid, data)['mjs'])

@app.route('/upload', methods=['POST'])
@jwt_required()
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
    saved_uri = upload_file(file_obj, bucket, file_oid, full_md) 
    user_email = current_user.email
    user_name = current_user.name
    if saved_uri:
        console_uri = 'https://console.developers.google.com/m/cloudstorage/b/{}/o/{}'
        http_uri = console_uri.format(bucket, file_oid)
        mjs = get_mjs(user_oid)['mjs']
        if mjs == {}:
            logger.debug('Creating mjs for user {}'.format(user_email))
            mjs = _init_mjs()
        mjs['unassigned'].append('ugc.{}'.format(str(file_oid)))
        update_mjs(user_oid, mjs)
        # Send an email to editor
        subject = 'New UGC submission'
        with open('editors_email_template') as fh:
            template = jinja2.Template(fh.read())
        body = template.render({'uri': http_uri,
                                'metadata': clean_md,
                                'user_email': user_email,
                                'user_name': user_name})
        sent = send_gmail(subject, body, editor_address)
        if not sent:
            logger.error('There was an error sending an email to {}'.format(editor_address))
        clean_md['item_page'] = '/item/ugc.{}'.format(str(file_oid))
        return humanify({'md': clean_md})
    else:
        abort(500, 'Failed to save %s' % filename)

@app.route('/search')
def general_search():
    pass

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

    place_doc = search_by_header(place, 'places')
    name_doc = search_by_header(name, 'familyNames')
    # fsearch() expects a dictionary of lists and returns Mongo cursor
    ftree_args = {}
    if name:
        ftree_args['last_name'] = [name]
    if place:
        ftree_args['birth_place'] = [place]
        
    # We turn the cursor to list in order to serialize it
    family_trees = list(fsearch(**ftree_args))
    rv = {'place': place_doc, 'name': name_doc, 'individuals': family_trees}
    return humanify(rv)

@app.route('/suggest/<collection>/<string>')
def get_suggestions(collection,string):
    '''
    This view returns a Json with 3 fields:
    "complete", "starts_with", "phonetic".
    Each field holds a list of up to 5 strings.
    '''
    rv = {}
    rv['starts_with'] = get_completion(collection, string)
    rv['contains'] = get_completion(collection, string, False)
    rv['phonetic'] = get_phonetic(collection, string)
    return humanify(rv)


@app.route('/item/<item_id>')
def get_items(item_id):
    '''
    This view returns either Json representing an item or a list of such Jsons.
    The expected item_id string is in form of "collection_name.item_id"
    and could be  split by commas - if there is only one id, the view will return
    a single Json. 
    Only the first 10 ids will be returned for the list view to prevent abuse.
    '''
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
    if items:
        # Cast items to list
        if type(items) != list:
            items = [items]
        # Check that each of the ugc_items is accessible by the logged in user
        for ugc_item_id in [item_id[4:] for item_id in ugc_items]:
            for item in items:
                if item['_id'] == ugc_item_id and item.has_key('owner') and item['owner'] != unicode(user_oid):
                    abort(403, 'You are not authorized to access item ugc.{}'.format(str(item['_id'])))
        return humanify(items)
    else:
        abort(404, 'Nothing found ;(')

@app.route('/fsearch')
def ftree_search():
    '''
    This view searches for gedcom formatted family tree files using
    genTreeIndividuals collection for the files index.
    The search supports numerous fields and unexact values for search terms.
    '''
    args = request.args
    keys = args.keys()
    if not ('last_name' in keys or 'birth_place' in keys or 'individual_id' in keys):
        em = "At least one of 'last_name', 'birth_place' or 'individual_id' fields is required"
        abort(400, em)
    results = fsearch(**args)
    return humanify(results)

@app.route('/get_ftree_url/<tree_number>')
def fetch_tree(tree_number):
    try:
        tree_number = int(tree_number)
    except ValueError:
        abort(400, 'Tree number must be an integer')
    gtrees_bucket_url = 'https://storage.googleapis.com/bhs-familytrees'
    collection = data_db['genTreeIndividuals']
    tree = collection.find_one({'GTN': tree_number})
    if tree:
        tree_path = tree['GenTreePath']
        tree_fn = tree_path.split('/')[-1]
        rv = {'tree_file': '{}/{}'.format(gtrees_bucket_url, tree_fn)}
        return humanify(rv)
    else:
        abort(404, 'Tree {} not found'.format(tree_number))


if __name__ == '__main__':
    app.run('0.0.0.0')
