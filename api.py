#!/usr/bin/env python

from datetime import timedelta

from flask import Flask, jsonify, request
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
    roles = db.ListField(db.ReferenceField(Role), default=['user'])

# Ensure we have a user to test with
@app.before_first_request
def create_user():
    if not user_datastore.get_user('dannybmail@gmail.com'):
        logger.debug('Creating test user.')
        user_datastore.create_user(email='dannybmail@gmail.com', password=encrypt_password('password'))

# Setup Flask-Security
user_datastore = MongoEngineUserDatastore(db, User, Role)
security = Security(app, user_datastore)

def humanify(obj):
    'Adds newline to Json responses to make CLI debugging easier'
    resp = jsonify(obj)
    resp.set_data(resp.data+'\n')
    return resp

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
@jwt_required()
def manage_user(user_id=None):
    if request.method == 'GET':
        user_obj = current_user
        user_obj.id = str(user_obj.id)
        return humanify({'id': user_obj.id,
                         'email': user_obj.email})

if __name__ == '__main__':
    logger.debug('Starting api')
    app.run()
