import logging
import os
import inspect
from datetime import timedelta
import pymongo
import elasticsearch
import redis
from flask import Flask
from flask.ext.mongoengine import MongoEngine
from flask.ext.cors import CORS
from flask.ext.mail import Mail
from flask.ext.security import Security, MongoEngineUserDatastore
from bhs_api.utils import get_conf

SEARCH_CHUNK_SIZE = 15
# Create app
def create_app(testing=False, live=False):
    from bhs_api.models import User, Role
    from bhs_api.forms import LoginForm

    app = Flask(__name__)
    app.testing = testing

    # load the config file
    conf = get_conf()
    app.conf = conf
    # Our config - need to move everything here
    app.config['VIDEO_BUCKET_URL'] = "https://storage.googleapis.com/bhs-movies"
    app.config['IMAGE_BUCKET_URL'] = "https://storage.googleapis.com/bhs-flat-pics"

    # Set app config
    app.config['DEBUG'] = True
    app.config['FRONTEND_SERVER'] = conf.frontend_server
    app.config['DEFAULT_NEXT'] = '/mjs'
    # Security Config
    app.config['SECRET_KEY'] = conf.secret_key
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SECURITY_PASSWORDLESS'] = True
    app.config['SECURITY_EMAIL_SENDER'] = 'BH Databases<support@bh.org.il>'
    app.config['SECURITY_USER_IDENTITY_ATTRIBUTES'] = 'email'
    app.config['SECURITY_EMAIL_SUBJECT_PASSWORDLESS'] = 'Login link for Your Jewish Story'
    app.config['SECURITY_POST_LOGIN_VIEW'] = '/mjs'
    app.config['SECURITY_USER_IDENTITY_ATTRIBUTES'] = ('email', 'username', 'hash')
    # Mail Config
    app.config['MAIL_SERVER'] = conf.mail_server
    app.config['MAIL_PORT'] = conf.mail_port
    # Mail optional username and password
    try:
        app.config['MAIL_USERNAME'] = conf.mail_username
        app.config['MAIL_PASSWORD'] = conf.mail_password
    except AttributeError:
        pass

    # DB Config
    app.config['MONGODB_DB'] = conf.user_db_name
    app.config['MONGODB_HOST'] = conf.user_db_host
    app.config['MONGODB_PORT'] = conf.user_db_port
    # Redis
    app.config['REDIS_HOST'] = conf.redis_host
    app.config['REDIS_PORT'] = conf.redis_port
    app.config['REDIS_PASSWORD'] = getattr(conf, 'redis_password', None)

    # CACHING
    app.config['CACHING_TTL'] = conf.caching_ttl

    #opencagedata
    app.config['GEOCODER_KEY'] = conf.geocoder_key

    app.mail = Mail(app)
    app.db = MongoEngine(app)
    app.user_datastore = MongoEngineUserDatastore(app.db, User, Role)
    app.security = Security(app, app.user_datastore,
                            passwordless_login_form=LoginForm)
    # Create database connection object
    app.client_data_db = pymongo.MongoClient(conf.data_db_host, conf.data_db_port,
                    read_preference=pymongo.ReadPreference.SECONDARY_PREFERRED)
    app.data_db = app.client_data_db[conf.data_db_name]

    # Create the elasticsearch connection
    app.es = elasticsearch.Elasticsearch(conf.elasticsearch_host)
    # Add the user's endpoints
    from bhs_api.user import user_endpoints
    app.register_blueprint(user_endpoints)
    # Add the v1 endpoint
    from bhs_api.v1_endpoints import v1_endpoints
    app.register_blueprint(v1_endpoints, url_prefix='/v1')
    # Initialize autodoc - https://github.com/acoomans/flask-autodoc
    #allow CORS
    cors = CORS(app, origins=['*'], headers=['content-type', 'accept',
                                            'authentication-token', 'Authorization'])
    # logging
    if live:
        app.config['PROPAGATE_EXCEPTIONS'] = True
        try:
            fh = logging.FileHandler(conf.log_file)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            fh.setFormatter(formatter)
            app.logger.addHandler(fh)
        except AttributeError:
            pass

    # redis
    try:
        app.redis = redis.StrictRedis(host=conf.redis_host,
                                      port=conf.redis_port,
                                      password = app.config['REDIS_PASSWORD'],
                                      db=0)
    except AttributeError:
        app.redis = None

    return app, conf

# Specify the bucket name for user generated content
ugc_bucket = 'bhs-ugc'

# Specify the email address of the editor for UGC moderation
editor_address = 'inna@bh.org.il,bennydaon@bh.org.il'
