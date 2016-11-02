import os
import logging
import boto
import gcs_oauth2_boto_plugin

def get_basename(full_path):
    return full_path.split('/')[-1]

def upload_file(file_path, bucket, new_filename=None):
    '''
    Upload the file object to a bucket.
    Add the original file path to its object metadata.
    '''
    if not new_filename:
        fn = get_basename(file_path)
    else:
        fn = new_filename

    dest_uri = boto.storage_uri(bucket + '/' + fn, 'gs')

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
    return str(dest_uri)


def upload_photo(doc, conf):
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
                         uuid)
    if result:
        logging.info('Uploaded file result - ' + result)


