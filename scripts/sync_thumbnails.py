#!/usr/bin/env python
'''
    Usage: `python scripts/sync_thumbails.py`

    This scripts looks for images that have no thumbnails, generates them
    and push it to the thumbnails bucket in `thumbnail_bucket_name`

'''


import os
import json
from subprocess import check_output
import logging
import StringIO

import pymongo
import boto
import gcs_oauth2_boto_plugin
from PIL import Image

from bhs_api.utils import get_conf

conf = get_conf(
		set(['photos_bucket_name',
                     'thumbnails_bucket_name']),
               '/etc/bhs/migrate_config.yaml' )

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)-15s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger('scripts.migrate')
logger.setLevel(logging.getLevelName('INFO'))

def get_bucket_list(bucket_name):
    uri = boto.storage_uri(bucket_name, 'gs')
    for obj in uri.get_bucket():
        yield obj.name


def add_thumbnail(file_name):
    ''' add a thumbnail for the specific file'''
    src_uri = boto.storage_uri('{}/{}'.format(conf.photos_bucket_name,
                                              file_name),
                               'gs')
    dest_uri = boto.storage_uri('{}/{}'.format(conf.thumbnails_bucket_name,
                                              file_name),
                               'gs')

    try:
        new_key = dest_uri.new_key()
    except boto.exception.NoAuthHandlerFound as e:
        logging.error(e)
        return None

    # Create a file-like object for holding the photo contents.
    photo = StringIO.StringIO()
    src_uri.get_key().get_file(photo)

    thumbnail = StringIO.StringIO()
    im = Image.open(photo)
    im.thumbnail((260, 260))
    im.save(thumbnail, 'JPEG')
    thumbnail.seek(0)
    # save the thumbnail
    try:
        new_key.set_contents_from_file(thumbnail)
        new_key.make_public()
    except boto.exception.GSResponseError as e:
        logging.error(e)
        # Do we have the credentials file set up?
        boto_cred_file = os.path.expanduser('~') + '/.boto'
        if not os.path.exists(boto_cred_file):
            logging.error('Credentials file {} was not found.'.format(boto_cred_file))

if __name__ == '__main__':
    photo_files = set(get_bucket_list(conf.photos_bucket_name))
    thumbnail_files = set(get_bucket_list(conf.thumbnails_bucket_name))
    missing_thumbnails = photo_files.difference(thumbnail_files)
    print len(missing_thumbnails)
    for photo in missing_thumbnails:
        add_thumbnail(photo)
        exit(-1)

