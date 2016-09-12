import logging
import json
import datetime
import os
import getpass
from bson.json_util import dumps

from uuid import UUID

import yaml
import boto
import gcs_oauth2_boto_plugin
import bson
import soundcloud
import gmail
import pymongo
from bson.objectid import ObjectId
from bson import json_util
from werkzeug import Response
from PIL import Image

CONF_FILE = '/etc/bhs/config.yml'
DEFAULT_CONF_FILE = 'conf/dev.yaml'
SEARCHABLE_COLLECTIONS = ('places',
                          'familyNames',
                          'photoUnits',
                          'personalities',
                          'movies')
# TODO: delete the next 3 lines
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

def dictify(m_engine_object):
    # ToDo: take care of $oid conversion to string
    return json.loads(m_engine_object.to_json())

class Struct:
    def __init__(self, **entries): 
        self.__dict__.update(entries)

def get_oid(id_str):
    try:
        return bson.objectid.ObjectId(id_str)
    except bson.errors.InvalidId:
        return None

def get_conf(config_file=CONF_FILE, must_have_keys=set()):
    ''' Read the configuration file and return config dict.  Check that all
        the necessary options are present. If the configuration file is
        missing, use the one in `conf/dev.yaml`.
    '''
    try:
        fh = open(config_file)
    except IOError:
        fh = open(DEFAULT_CONF_FILE)

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

def upload_file(file_obj, bucket, file_oid, object_md, make_public=False):
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
        if make_public:
            new_key.make_public()
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

def fail_show_filter(show_filter, doc):
    """Return a list of (key, value) tuples of offending values if the `doc`
    fails `show_filter` or an empty list if the `doc` passes the filter.
    """
    rv = []
    for k in show_filter.keys():
        if k == '$or':
            if (not doc['UnitText1']['En']) and (not doc['UnitText1']['He']):
                rv.append(('UnitText1', doc['UnitText1']))
        elif k == 'DisplayStatusDesc':
            if doc[k] == show_filter[k]['$nin'][0]:
                rv.append((k, doc[k]))
        else:
            if doc[k] != show_filter[k]:
                rv.append((k, doc[k]))
    return rv

def send_gmail(subject, body, address, message_mode='text'):
    must_have_keys = set(['email_username',
                    'email_password',
                    'email_from'])

    conf = get_conf()

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



def get_referrer_host_url(referrer):
    """Return referring host url for valid links or None"""
    for protocol in ['http://', 'https://']:
        if referrer.startswith(protocol):
            return protocol + referrer.split(protocol)[1].split('/')[0]
    return None


# Utility functions
def humanify(obj, status_code=200):
    """ Gets an obj and possibly a status code and returns a flask Resonse
        with a jsonified obj, with newlines.
    >>> humanify({"a": 1})
    <Response 13 bytes [200 OK]>
    >>> humanify({"a": 1}, 404)
    <Response 13 bytes [404 NOT FOUND]>
    >>> humanify({"a": 1}).get_data()
    '{\\n  "a": 1\\n}\\n'
    >>> humanify([1,2,3]).get_data()
    '[\\n  1, \\n  2, \\n  3\\n]\\n'
    """
    # jsonify function doesn't work with lists
    if type(obj) == list:
        data = json.dumps(obj, default=json_util.default, indent=2) + '\n'
    elif type(obj) == pymongo.cursor.Cursor:
        rv = []
        for doc in obj:
            doc['_id'] = str(doc['_id'])
            rv.append(dumps(doc, indent=2))
        data = '[' + ',\n'.join(rv) + ']' + '\n'
    else:
        data = dumps(obj,
                          default=json_util.default,
                          indent=2,
                          cls=MongoJsonEncoder)
        data += '\n'
    resp = Response(data, mimetype='application/json')
    resp.status_code = status_code
    return resp

def uuids_to_str(doc):
    for k,v in doc.items():
        if type(v) == UUID:
            doc[k] = str(v)


def slugs_to_urls(slug):
    ''' gets the slug dictionary, conataining `He` and `En` slug and returning
        a dict with URLs
    '''

    r = {}
    for k, v in slug.items():
        c, s = v.split('_')
        if k == 'He':
            u = u'http://dbs.bh.org.il/he/{}/{}'.format(s, c)
        else:
            u = u'http://dbs.bh.org.il/{}/{}'.format(c, s)
        r[k] = u
    return r

def collection_to_csv(coll, f):
    '''
        dumps a collection to a csv files.
        the file includes the URL of the hebrew page, its title,
        the url of the english page and its title.
    '''
    from bhs_api.item import SHOW_FILTER
    for i in coll.find(SHOW_FILTER):
        url = slugs_to_urls(i['Slug'])
        try:
            line = ','.join([url['He'], i['Header']['He'].replace(',','|')])
        except KeyError:
            line = ','
        try:
            line = ','.join([line, url['En'], i['Header']['En'].replace(',','|')])
        except KeyError:
            line = ','.join([line, '', ''])
        line += '\n'
        f.write(line.encode('utf8'))

def binarize_image(image):
    binary = None

    try:
        im = Image.open(image)
        thumb = im.copy()
        thumb.thumbnail((260, 260))
        image_buffer = StringIO()
        thumb.save(image_buffer, "JPEG")
        binary = Binary(image_buffer.getvalue(), BINARY_SUBTYPE)

    # if image is a file object, rewind it
    finally:
        try:
            image.seek(0)
        except AttributeError:
            pass

    return binary

