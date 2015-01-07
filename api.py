#!/usr/bin/env python

from datetime import timedelta
import json
from bson import json_util
import re

from flask import Flask, jsonify, request, abort
from flask.ext.mongoengine import MongoEngine, ValidationError
from flask.ext.security import Security, MongoEngineUserDatastore, \
    UserMixin, RoleMixin, login_required
from flask.ext.security.utils import encrypt_password, verify_password
from flask.ext.cors import CORS
from flask_jwt import JWT, JWTError, jwt_required, verify_jwt
from  flask.ext.jwt import current_user

from werkzeug import secure_filename

import pymongo

from utils import get_conf, get_logger, gen_missing_keys_error, upload_file, \
    get_oid
import phonetic


# Create app
app = Flask(__name__)

# Get configuration from file
conf = get_conf()

# Set app config
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = conf.secret_key
app.config['SECURITY_PASSWORD_HASH'] = conf.security_password_hash
app.config['SECURITY_PASSWORD_SALT'] = conf.security_password_salt
app.config['JWT_EXPIRATION_DELTA'] = timedelta(days=1)

# DB Config
app.config['MONGODB_DB'] = conf.db_name
app.config['MONGODB_HOST'] = conf.db_host
app.config['MONGODB_PORT'] = conf.db_port

# Logging config
logger = get_logger()

#allow CORS
cors = CORS(app, origins=['*'], headers=['content-type', 'accept', 'Authorization'])

# Set up the JWT Token authentication
jwt = JWT(app)
@jwt.authentication_handler
def authenticate(username, password):
    user_obj = user_datastore.find_user(email=username)
    if not user_obj:
        logger.debug('User %s not found' % username)
        return None

    if verify_password(password, user_obj.password):
        # make user.id jsonifiable
        user_obj.id = str(user_obj.id)
        return user_obj
    else:
        logger.debug('Wrong password for %s' %  username)
        return None

@jwt.user_handler
def load_user(payload):
    user_obj = user_datastore.find_user(id=payload['user_id'])
    return user_obj

# Create database connection object
db = MongoEngine(app)
data_db = pymongo.Connection()['bhp6']

class Role(db.Document, RoleMixin):
    name = db.StringField(max_length=80, unique=True)
    description = db.StringField(max_length=255)

class User(db.Document, UserMixin):
    email = db.StringField(max_length=255)
    password = db.StringField(max_length=255)
    active = db.BooleanField(default=True)
    confirmed_at = db.DateTimeField()
    roles = db.ListField(db.ReferenceField(Role))

class Mjs(db.Document):
    mjs = db.DictField()

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
                                   password=encrypt_password('password'),
                                   roles=[user_role])

# Setup Flask-Security
user_datastore = MongoEngineUserDatastore(db, User, Role)
security = Security(app, user_datastore)


# Stubs for custom error handlers
@app.errorhandler(400)
def custom_400(error):
    response = humanify({'error': error.description})
    return response, 400

@app.errorhandler(403)
def custom_403(error):
    response = humanify({'error': error.description})
    return response, 403

@app.errorhandler(404)
def custom_404(error):
    response = humanify({'error': error.description})
    return response, 404

@app.errorhandler(405)
def custom_405(error):
    response = humanify({'error': error.description})
    return response, 405

@app.errorhandler(409)
def custom_409(error):
    response = humanify({'error': error.description})
    return response, 409

@app.errorhandler(500)
def custom_500(error):
    response = humanify({'error': error.description})
    return response, 500

# Utility functions
def humanify(obj):
    'Adds newline to Json responses to make CLI debugging easier'
    if type(obj) == list:
        return json.dumps(obj, indent=2) + '\n'
    elif type(obj) == pymongo.cursor.Cursor:
        rv = []
        for doc in obj:
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
    allowed_fields = ['email']
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
                                        password=enc_password)
    # Add default role to a newly created user
    user_datastore.add_role_to_user(created, 'user')

    return _clean_user(created)

def update_user(user_id, user_dict):
    user_obj = _get_user_or_error(user_id)
    if 'email' in user_dict.keys():
        user_obj.email = user_dict['email']
    if 'password' in user_dict.keys():
        enc_password = encrypt_password(user_dict['password'])
        user_obj.password = enc_password

    user_obj.save()
    return _clean_user(user_obj)

######################################################################################

def get_mjs(user_oid):
    mjs = Mjs.objects(id=user_oid).first()
    if mjs:
        return mjs
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

    item = data_db[collection].find_one(oid)
    if item:
        return _make_serializable(item)
    else:
        return {}

def _make_serializable(obj):
    # ToDo: Replace with json.dumps with default setting and check
    # Make problematic fields Json serializable
    if obj.has_key('_id'):
        obj['_id'] = str(obj['_id'])
    if obj.has_key('UpdateDate'):
        obj['UpdateDate'] = str(obj['UpdateDate'])
    return obj

def search_by_header(string, collection):
    if not string: # Support empty strings
        return {}
    if phonetic.is_hebrew(string):
        lang = 'He'
    else:
        lang = 'En'
    item = data_db[collection].find_one({'Header.%s' % lang: string.upper()})
    if item:
        return _make_serializable(item)
    else:
        return {}

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
    cursor = collection.find({header: regex}, {'_id': 0, header: 1}).limit(max_res)
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
    If `tree_number` kwarg is present, try to fetch the corresponding file
    directly (return the link to it or error 404).
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
                     'debug']

    allowed_args = set(args_to_index.keys() + extra_args)
    search_dict = {}
    for key, value in kwargs.items():
        search_dict[key] = value[0]

    keys = search_dict.keys()
    bad_args = set(keys).difference(allowed_args)
    if bad_args:
        abort(400, 'Unsupported args in request: {}'.format(', '.join(list(bad_args))))
    if 'tree_number' in keys:
        try:
            tree_number = int(search_dict['tree_number'])
            return fetch_tree(tree_number)
        except ValueError:
            abort(400, 'Tree number must be an integer')

    collection = data_db['genTreeIndividuals'] 
    index_keys = [v['key'][0][0] for v in collection.index_information().values()]
    needed_indices = ['LN_lc', 'BP_lc', 'ID']
    for index_key in needed_indices:
        if index_key not in index_keys:
             logger.info('Ensuring indices for field {} - please wait...'.format(index_key))
             collection.ensure_index(index_key)
    
    # Build gentree search query
    # Split all the arguments to those with name or place and those with year
    names_and_places = {}
    years = {}
    sex_query = None
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
                

    # Build a dict of all the names_and_places queries
    for search_arg in names_and_places:
        field_name = args_to_index[search_arg]
        split_arg = names_and_places[search_arg].split(';')
        search_str = split_arg[0]
        if search_arg == 'first_name':
            # No modifications are supported for first names  
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

    logger.debug('Search query:\n{}'.format(search_query))

    projection = {'_id': 0,
                  'II': 1,   # Individual ID
                  'GT': 1,   # GenTree ID
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
    # Pretty print cursor.explain for index debugging
    #print json.dumps(results.explain(), default=json_util.default, indent=2)
    if results.count() > 0:
        logger.debug('Found {} results'.format(results.count()))
        return results
    else:
        return {}

def fetch_tree(tree_number):
    gtrees_bucket_url = 'https://storage.googleapis.com/bhs-familytrees'
    collection = data_db['genTreeIndividuals']
    tree = collection.find_one({'ID': tree_number})
    if tree:
        tree_path = tree['GenTreePath']
        tree_fn = tree_path.split('/')[-1]
        return {'tree_file': '{}/{}'.format(gtrees_bucket_url, tree_fn)}
    else:
        abort(404, 'Tree {} not found'.format(tree_number))

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
    return humanify({'access': 'private'})

@app.route('/user', methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/user/<user_id>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_user(user_id=None):
    '''
    Manage user accounts. If routed as /user, gives access only to logged in
    user, if routed as /user/<user_id>, allows administrative level access
    if the looged in user is in the admin group.
    POST gets special treatment, as there must be a way to register new user.
    '''
    try:
        verify_jwt()
    except JWTError as e:
        # You can create a new user while not being logged in
        # Will have to defend this endpoint with rate limiting or similar means
        if request.method == 'POST':
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
    The server stores the metadata in a ugc collection and uploads the file
    to a bucket.
    '''
    if not request.files:
        abort(400, 'No files present!')

    must_have_keys = set(['title',
                        'description',
                        'location',
                        'date',
                        'creator_name',
                        'people_present'])

    form = request.form
    keys = form.keys()
    missing_keys = list(must_have_keys.difference(set(keys)))
    if missing_keys != []:
        e_message = gen_missing_keys_error(missing_keys)
        abort(400, e_message)

    user_oid = current_user.id
    file_obj = request.files['file']
    filename = secure_filename(file_obj.filename)
    metadata = dict(form)
    metadata['user_id'] = str(user_oid)
    metadata['filename'] = filename

    bucket = 'test_bucket'
    creds = ('foo', 'bar')
    saved = upload_file(file_obj, bucket, creds, metadata)
    if saved:
        return humanify({'md': metadata})
    else:
        abort(500, 'Failed to save %s' % filename)

@app.route('/search')
def general_search():
    pass

@app.route('/wsearch')
def wizard_search():
    args = request.args
    must_have_keys = set(['place', 'name'])
    keys = args.keys()
    missing_keys = list(must_have_keys.difference(set(keys)))
    if missing_keys != []:
        e_message = gen_missing_keys_error(missing_keys)
        abort(400, e_message)

    place_doc = search_by_header(args['place'], 'places')
    name_doc = search_by_header(args['name'], 'familyNames')
    return humanify({'place': place_doc, 'name': name_doc})



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
    items = fetch_items(items_list[:10])
    if items:
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
    if not ('last_name' in keys or 'birth_place' in keys):
        em = "At least one of 'last_name' or 'birth_place' fields is required"
        abort(400, em)
    results = fsearch(**args)
    return humanify(results)


if __name__ == '__main__':
    app.run('0.0.0.0')
