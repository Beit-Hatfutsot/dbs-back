#!/usr/bin/env python
'''
    Usage: `python scripts/publicize_thumbs.py`

    This scripts looks for thumbnails and makes them public.
    Run this when you have issues with thumbnails being non-public
'''


import boto
import gcs_oauth2_boto_plugin
from argparse import ArgumentParser

def parse_args():
    parser = ArgumentParser(description="makes all the objects in a bucket public")
    parser.add_argument("bucket", help="the bucket whose files will be public")
    return parser.parse_args()

def get_bucket_list(bucket_name):
    uri = boto.storage_uri(bucket_name, 'gs')
    for obj in uri.get_bucket():
        yield obj.name

if __name__ == '__main__':
    args = parse_args()
    for i in get_bucket_list(args.bucket):
        thumb = boto.storage_uri('{}/{}'.format(args.bucket, i),
                                   'gs')
        thumb.get_key().make_public()
