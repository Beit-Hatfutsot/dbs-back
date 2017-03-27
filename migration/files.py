import os
import logging
import StringIO

import boto
import gcs_oauth2_boto_plugin
from PIL import Image

def get_basename(full_path):
    return full_path.split('/')[-1]

def upload_file(file_path, bucket, new_filename=None, thumb_bucket=None, dryrun=False):
    '''
    Upload the file object to a bucket.
    Add the original file path to its object metadata.
    '''
    if not new_filename:
        fn = get_basename(file_path)
    else:
        fn = new_filename

    dest_uri = boto.storage_uri(bucket + '/' + fn, 'gs')

    if dryrun:
        logging.info("create new key for dest_url={}".format(dest_uri))
    else:
        try:
            new_key = dest_uri.new_key()
        except boto.exception.NoAuthHandlerFound as e:
            logging.error(e)
            return None

    try:
        file_obj = open(file_path)
    except IOError as e:
        logging.error(e)
        return None

    if dryrun:
        logging.info("update_metadata file_path=".format(file_path))
    else:
        new_key.update_metadata({'path': file_path})
        try:
            new_key.set_contents_from_file(file_obj)
            new_key.make_public()
        except boto.exception.GSResponseError as e:
            logging.error(e)
            # Do we have the credentials file set up?
            boto_cred_file = os.path.expanduser('~') + '/.boto'
            if not os.path.exists(boto_cred_file):
                logging.error('Credentials file {} was not found.'.format(boto_cred_file))

            return None

    if thumb_bucket:
        file_obj.seek(0)
        im = Image.open(file_obj)
        im.thumbnail((260, 260))
        thumbnail = StringIO.StringIO()
        im.save(thumbnail, 'JPEG')
        thumb_uri = boto.storage_uri('{}/{}'.format(thumb_bucket, fn),
                                     'gs')
        if dryrun:
            logging.info("create new thumb_uri and make it public {}".format(thumb_uri))
        else:
            new_key = thumb_uri.new_key()
            # save the thumbnail
            thumbnail.seek(0)
            new_key.set_contents_from_file(thumbnail)
            new_key.make_public()

    file_obj.close()
    return str(dest_uri)


def upload_photo(doc, conf, dryrun=False):
    ''' upload a photo to google storage bucket '''
    bucket_name = getattr(conf, 'photos_bucket_name')
    mount_point = getattr(conf, 'photos_mount_point')
    uuid = doc['PictureId']
    filename = doc['PictureFileName']
    path = doc['PicturePath']
    if path and uuid and filename:
        path = path.replace('\\', '/')
        extension = path.split('.')[-1].lower()
        uuid = uuid + '.' + extension
    result = upload_file(os.path.join(mount_point, path),
                         bucket_name,
                         uuid,
                         conf.thumbnails_bucket_name,
                         dryrun=dryrun)
    if result:
        logging.info('Uploaded file result - ' + result)


