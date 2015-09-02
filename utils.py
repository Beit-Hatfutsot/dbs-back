import logging
import json
import datetime
import os
import getpass

import yaml
import boto
import gcs_oauth2_boto_plugin
import bson
import soundcloud
import gmail
from bson.objectid import ObjectId
from bson import json_util
from werkzeug import Response

# Set default GCE project id
project_id = 'bh-org-01'

class MongoJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        elif isinstance(obj, ObjectId):
            return unicode(obj)
        return json.JSONEncoder.default(self, obj)

def jsonify(*args, **kwargs):
    """ jsonify with support for MongoDB ObjectId
        See https://gist.github.com/akhenakh/2954605
    """
    return Response(json.dumps(dict(*args, **kwargs),
                    default=json_util.default,
                    indent=2,
                    cls=MongoJsonEncoder),
                    mimetype='application/json')

class Struct:
    def __init__(self, **entries): 
        self.__dict__.update(entries)

def get_oid(id_str):
    try:
        return bson.objectid.ObjectId(id_str)
    except bson.errors.InvalidId:
        return None

def get_conf(config_file='/etc/bhs/config.yml', must_have_keys=set()):
    '''Read the configuration file and return config dict.
    Check that all the necessary options are present.
    Raise meaningful exceptions on errors'''
    fh = open(config_file)
    try:
        conf = yaml.load(fh)
        if not conf:
            raise ValueError('Empty config file')
        # Check that all the must_have_keys are present
        config_keys = set(conf.keys())
        missing_keys = list(must_have_keys.difference(config_keys))
        if missing_keys != []:
            keys_message = gen_missing_keys_error(missing_keys)
            error_message = 'Invalid configuration file: ' + keys_message
            raise ValueError(error_message)

        return Struct(**conf) # Enables dot access

    except yaml.scanner.ScannerError, e:
        raise yaml.scanner.ScannerError(e.problem+str(e.problem_mark))

def gen_missing_keys_error(missing_keys):
    if len(missing_keys) == 1:
        s = ''
        verb = 'is'
        missing = missing_keys[0]
    else:
        s = 's'
        verb = 'are'
        missing = ', '.join(missing_keys)
    error_message = 'Key{} {} {} missing.'.format(s, missing, verb)
    return error_message

def get_logger(app_name='bhs_api', fn='bhs_api.log'):
    logger = logging.getLogger(app_name)
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(fn)
    ch = logging.StreamHandler()
    #ch.setLevel(logging.ERROR)
    # Output in debug level to console while developing
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

def upload_file(file_obj, bucket, file_oid, object_md):
    '''
    Upload the file object to a bucket using credentials and object metadata.
    Object name is a part of its metadata.
    '''
    if getpass.getuser() == 'bhs':
        boto_cred_file = '/home/bhs/.boto'
    else:
        boto_cred_file = os.path.expanduser('~') + '/.boto'

    fn = str(file_oid)
    dest_uri = boto.storage_uri(bucket + '/' + fn, 'gs')
    try:
        new_key = dest_uri.new_key()
    except boto.exception.NoAuthHandlerFound as e:
        print e.message
        return None

    new_key.update_metadata(object_md)
    try:
        new_key.set_contents_from_file(file_obj)
    except boto.exception.GSResponseError as e:
        # Do we have the credentials file set up?
        if not os.path.exists(boto_cred_file):
            print('Credentials file {} was not found.'.format(boto_cred_file))

        return None

    return str(dest_uri)

def get_yaml_conf(fn):
    fh = open(fn)
    conf = yaml.load(fh)
    fh.close()
    return conf

def get_sc_client(fn):
    conf = get_yaml_conf(fn)
    client = soundcloud.Client(**conf)
    return client

def upload_to_soundcloud(sc_client, fn):
    '''
    Upload the file from fn path to soundcloud using a client object.
    Save it as a track with the same name.
    Return the id generated for uploaded track.
    '''
    track = sc_client.post('/tracks', track={
         'title': fn,
         'sharing': 'private',
         'asset_data': open(fn, 'rb')
         })
    return track.obj

def send_gmail(subject, body, address, message_mode='text'):
    must_have_keys = set(['email_username',
                    'email_password',
                    'email_from'])

    conf = get_conf('/etc/bhs/config.yml', must_have_keys)

    my_gmail = gmail.GMail(conf.email_username, conf.email_password)
    if message_mode == 'html':
        msg = gmail.Message(subject, html=body, to=address, sender=conf.email_from)
    else:
        msg = gmail.Message(subject, text=body, to=address, sender=conf.email_from)
    try:
        my_gmail.send(msg) 
    except  gmail.gmail.SMTPAuthenticationError as e:
        print e.smtp_error
        return False

    return True
