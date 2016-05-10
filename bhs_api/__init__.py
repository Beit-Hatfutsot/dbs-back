import os
import inspect
from datetime import timedelta
import pymongo
import elasticsearch
from flask import Flask
from flask.ext.mongoengine import MongoEngine
from flask.ext.cors import CORS
from flask.ext.mail import Mail
from flask.ext.security import Security, MongoEngineUserDatastore
from bhs_common.utils import get_conf
from bhs_api.utils import get_logger

SEARCH_CHUNK_SIZE = 15
CONF_FILE = '/etc/bhs/config.yml'
# Create app
def create_app(testing=False):
    from bhs_api.models import User, Role

    app = Flask(__name__)
    app.testing = testing

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

    # Our config - need to move everything here
    app.config['VIDEO_BUCKET_URL'] = "https://storage.googleapis.com/bhs-movies"
    app.config['IMAGE_BUCKET_URL'] = "https://storage.googleapis.com/bhs-flat-pics"

    # Set app config
    app.config['DEBUG'] = True
    app.config['SECURITY_PASSWORDLESS'] = True
    app.config['SECURITY_EMAIL_SENDER'] = 'support@bh.org.il'
    app.config['SECURITY_USER_IDENTITY_ATTRIBUTES'] = 'email'
    app.config['SECURITY_EMAIL_SUBJECT_PASSWORDLESS'] = 'BH Login Instructions'
    app.config['SECRET_KEY'] = conf.secret_key
    # app.config['SECURITY_PASSWORD_HASH'] = conf.security_password_hash
    # app.config['SECURITY_PASSWORD_SALT'] = conf.security_password_salt
    app.config['MAIL_SERVER'] = 'localhost'
    app.config['MAIL_PORT'] = 33333
    # app.config['MAIL_USE_SSL'] = False
    # app.config['MAIL_USERNAME'] = 'username'
    # app.config['MAIL_PASSWORD'] = 'password'
    # DB Config
    app.config['MONGODB_DB'] = conf.user_db_name
    app.config['MONGODB_HOST'] = conf.user_db_host
    app.config['MONGODB_PORT'] = conf.user_db_port

    app.mail = Mail(app)
    app.db = MongoEngine(app)
    app.user_datastore = MongoEngineUserDatastore(app.db, User, Role)
    app.security = Security(app, app.user_datastore)
    # Create database connection object
    app.client_data_db = pymongo.MongoClient(conf.data_db_host, conf.data_db_port,
                    read_preference=pymongo.ReadPreference.SECONDARY_PREFERRED)
    app.data_db = app.client_data_db[conf.data_db_name]

    # Create the elasticsearch connection
    app.es = elasticsearch.Elasticsearch(conf.elasticsearch_host)
    # Add the views
    from bhs_api.views import blueprint, autodoc
    app.register_blueprint(blueprint)
    # Initialize autodoc - https://github.com/acoomans/flask-autodoc
    autodoc.init_app(app)
    #allow CORS
    cors = CORS(app, origins=['*'], headers=['content-type', 'accept',
                                            'Authorization'])
    return app, conf

app, conf = create_app()
# Specify the bucket name for user generated content
ugc_bucket = 'bhs-ugc'

# Specify the email address of the editor for UGC moderation
editor_address = 'inna@bh.org.il,bennydaon@bh.org.il'

# Logging config
logger = app.logger



