import os
import inspect
from datetime import timedelta
import pymongo
import elasticsearch
from flask import Flask
from flask.ext.mongoengine import MongoEngine
from flask.ext.cors import CORS
from flask.ext.autodoc import Autodoc
from bhs_api.utils import get_logger, get_conf

CONF_FILE = '/etc/bhs/config.yml'
DEFAULT_CONF_FILE = 'conf/dev.yaml'

SEARCHABLE_COLLECTIONS = ('places',
                          'familyNames',
                          'photoUnits',
                          'personalities',
                          'movies')

# Create app
app = Flask(__name__)
# Initialize autodoc - https://github.com/acoomans/flask-autodoc
autodoc = Autodoc(app)
# Specify the bucket name for user generated content
ugc_bucket = 'bhs-ugc'
# Specify the email address of the editor for UGC moderation
editor_address = 'inna@bh.org.il,bennydaon@bh.org.il'
# Get configuration from file
must_have_keys = set(['secret_key',
                      'security_password_hash',
                      'security_password_salt',
                      'user_db_host',
                      'user_db_port',
                      'elasticsearch_host',
                      'user_db_name',
                      'data_db_host',
                      'data_db_port',
                      'data_db_name',
                      'image_bucket_url',
                      'video_bucket_url'])
# load the conf file. use local copy if nothing in the system
if os.path.exists(CONF_FILE):
    conf = get_conf(CONF_FILE, must_have_keys)
else:
    current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) # script directory
    conf = get_conf(os.path.join(current_dir, 'conf', 'bhs_config.yaml'),
                    must_have_keys)

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
# allow CORS
# TODO: add throttling for protection from attacks
cors = CORS(app, origins=['*'], headers=['content-type', 'accept',
                                         'Authorization'])

# Create database connection object
db = MongoEngine(app)
client_data_db = pymongo.MongoClient(conf.data_db_host, conf.data_db_port,
                read_preference=pymongo.ReadPreference.SECONDARY_PREFERRED)
data_db = client_data_db[conf.data_db_name]

# Create the elasticsearch connection
es = elasticsearch.Elasticsearch(conf.elasticsearch_host)

from bhs_api.views import *

