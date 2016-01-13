import os
import json
import StringIO
import boto
import gcs_oauth2_boto_plugin


def fwalk(tree_number, node_id):
    # a temporary solution, using local files
    dest_bucket_name = os.path.join('/data', 'bhs-familytrees-json',
                                    str(tree_number),node_id+'.json')
    fd = open(dest_bucket_name)
    ret = json.load(fd)
    fd.close()
    return ret
