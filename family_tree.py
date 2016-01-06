import json
import StringIO
import boto
import gcs_oauth2_boto_plugin


def fwalk(tree_number, node_id):
    # Add opening and closing `#` if missing
    dest_bucket_name = 'bhs-familytrees-json/'+str(tree_number)+'/'+node_id+'.json'
    uri = boto.storage_uri(dest_bucket_name, 'gs')
    fd = StringIO.StringIO()
    uri.get_key().get_file(fd)
    fd.seek(0)
    return json.load(fd)
