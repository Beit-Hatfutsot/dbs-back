import logging

import yaml
import bson


class Struct:
    def __init__(self, **entries): 
        self.__dict__.update(entries)

def get_oid(id_str):
    return bson.objectid.ObjectId(id_str)

def get_conf(config_file='/etc/bhs/config.yml'):
    '''Read the configuration file and return config dict.
    Check that all the necessary options are present.
    Raise meaningful exceptions on errors'''

    must_have_keys = set(['secret_key',
                        'security_password_hash',
                        'security_password_salt',
                        'db_host',
                        'db_port',
                        'db_name'])
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

def upload_file(file_obj, bucket, creds, object_md):
    '''
    Upload the file object to a bucket using credentials and object metadata.
    Object name is a part of its metadata.
    '''
    return True
