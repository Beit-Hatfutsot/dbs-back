#!/usr/bin/env python

# This script generates the ES river config files for BHS collections

import argparse
import json

def generate_river_config(template, db, collection, generate_file=False):
    """Generate a json with river configuration for
    the given db and collection names"""
    template['mongodb']['db'] = template['index']['name'] = db
    template['mongodb']['collection'] = template['index']['type'] = collection

    if generate_file:
        fn = '{}.json'.format(collection)
        with open(fn, 'w') as fh:
            json.dump(template, fh, indent=2)
    else:
        print json.dumps(template, indent=2)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--db', default='bhp6')
    parser.add_argument('-w', '--write', action='store_true')
    return parser.parse_args()


if __name__ == '__main__':

    collections = ['movies',
                   'places',
                   'personalities',
                   'familyNames',
                   'photoUnits']

    template = {
      "type": "mongodb",
      "mongodb": {
        "servers": [
          { "host": "127.0.0.1", "port": 27017 }
        ],
        "db": "",
        "collection": "",
        "options": {"secondary_read_preference": True},
        "gridfs": False
      },
      "index": {
        "name": "",
        "type": ""
      }
    }

    args = parse_args()

    for c in collections:
        generate_river_config(template, args.db, c, args.write)

