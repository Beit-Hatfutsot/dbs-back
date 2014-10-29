#!/usr/bin/env python

from datetime import timedelta

from flask import Flask, jsonify
from flask.ext.mongoengine import MongoEngine
from flask.ext.security import Security, MongoEngineUserDatastore, \
    UserMixin, RoleMixin, login_required
from flask.ext.security.utils import encrypt_password, verify_password

from flask.ext.cors import CORS
from flask_jwt import JWT, JWTError, jwt_required, verify_jwt


# Create app
app = Flask(__name__)

# Set app config
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'glpjht9dPBXQe8mBS9XxDMGLIoHukbpvSNU0FpnZ'
app.config['SECURITY_PASSWORD_HASH'] = 'pbkdf2_sha512'
app.config['SECURITY_PASSWORD_SALT'] = 'pjht9dPBXQe8mB'
app.config['JWT_EXPIRATION_DELTA'] = timedelta(days=1)

# DB Config
app.config['MONGODB_DB'] = 'bh'
app.config['MONGODB_HOST'] = 'localhost'
app.config['MONGODB_PORT'] = 27017

#allow CORS
cors = CORS(app, origins=['*'], headers=['content-type', 'accept', 'Authorization'])

# Set up the JWT Token authentication
jwt = JWT(app)
@jwt.authentication_handler
def authenticate(username, password):
    user_obj = user_datastore.find_user(email=username)
    if not user_obj:
        print 'User not found'
        return None

    if username == user_obj.email and verify_password(password, user_obj.password):
        
        # make user.id jsonifiable
        user_obj.id = str(user_obj.id)
        return user_obj

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
        print e.description
        return humanify({'access': 'public'})

@app.route('/private')
@jwt_required()
def private_space():
    return humanify({'access': 'private'})

if __name__ == '__main__':
    app.run()
