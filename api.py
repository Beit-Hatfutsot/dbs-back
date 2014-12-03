#!/usr/bin/env python

from datetime import timedelta
import json

from flask import Flask, jsonify, request, abort
from flask.ext.mongoengine import MongoEngine
from flask.ext.security import Security, MongoEngineUserDatastore, \
    UserMixin, RoleMixin, login_required
from flask.ext.security.utils import encrypt_password, verify_password

from flask.ext.cors import CORS
from flask_jwt import JWT, JWTError, jwt_required, verify_jwt
from  flask.ext.jwt import current_user

from utils import get_conf, get_logger



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

class Role(db.Document, RoleMixin):
    name = db.StringField(max_length=80, unique=True)
    description = db.StringField(max_length=255)

class User(db.Document, UserMixin):
    email = db.StringField(max_length=255)
    password = db.StringField(max_length=255)
    active = db.BooleanField(default=True)
    confirmed_at = db.DateTimeField()
    roles = db.ListField(db.ReferenceField(Role))

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

@app.errorhandler(409)
def custom_409(error):
    response = humanify({'error': error.description})
    return response, 409

def humanify(obj):
    'Adds newline to Json responses to make CLI debugging easier'
    resp = jsonify(obj)
    resp.set_data(resp.data+'\n')
    return resp

def is_admin(flask_user_obj):
    if flask_user_obj.has_role('admin'):
        return True
    else:
        return False

def user_handler(user_id, method, data):
    if data:
        try:
            data = json.loads(data)
        except ValueError:
            logger.debug('Could not decode JSON from data')
            abort(400)

    if method == 'GET':
        return humanify(get_user(user_id))

    elif method == 'POST':
        return humanify(create_user(data))

    elif method == 'PUT':
        return humanify(update_user(user_id, data))

    elif method == 'DELETE':
        return humanify(delete_user(user_id))

def _get_user_or_error(user_id):
    user = user_datastore.get_user(user_id)
    if user:
        return user
    else:
        raise abort(404)

def get_user(user_id):
    user = _get_user_or_error(user_id)
    return json.loads(user.to_json())

def delete_user(user_id):
    user = _get_user_or_error(user_id)
    if is_admin(user):
        return {'error': 'God Mode!'}
    else:
        user.delete()
        return {'deleted': user_id}

def create_user(user_dict):
    try:
        email = user_dict['email']
        enc_password = encrypt_password(user_dict['password'])
    except KeyError as e:
        logger.debug('%s key is missing from data' % e)
        abort(400)

    user_exists = user_datastore.get_user(email)
    if user_exists:
        logger.debug('User %s with email %s already exists' % (str(user_exists.id), email))
        abort(409)
        #return {'error': 'Email exists'}

    created = user_datastore.create_user(email=email,
                                        password=enc_password)
    # Add default role to a newly created user
    user_datastore.add_role_to_user(created, 'user')

    return {'created': str(created.id)}

def update_user(user_id, user_dict):
    user = _get_user_or_error(user_id)
    if 'email' in user_dict.keys():
        user.email = user_dict['email']
    if 'password' in user_dict.keys():
        enc_password = encrypt_password(user_dict['password'])
        user.password = enc_password

    user.save()

    return {'updated': user,
            'id': user_id}


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
        # Will have to defend this endpoint with rate limiting or similar
        if request.method == 'POST':
            return user_handler(None, request.method, request.data)
        else:
            logger.debug(e.description)
            abort(403)

    if user_id:
        # access_mode = 'admin'
        if is_admin(current_user):
            return user_handler(user_id, request.method, request.data)
        else:
            logger.debug('Non-admin user %s tried to access user id %s' % (current_user.email, user_id))
            abort(403)
    else:
        # access_mode = 'user'
        user_id = str(current_user.id)
        return user_handler(user_id, request.method, request.data)


if __name__ == '__main__':
    logger.debug('Starting api')
    app.run()
