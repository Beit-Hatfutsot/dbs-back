#!/usr/bin/env python
import argparse

import pymongo

from bhs_api import create_app
from bhs_api.item import Slug


def parse_args():
    parser = argparse.ArgumentParser(description=
                                     'fix revisionless story item in user db')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    app, conf = create_app()
    users = pymongo.MongoClient(conf.user_db_host, conf.user_db_port)[conf.user_db_name]["user"]

    for user in users.find():
        dirty = False
        if 'story_items' not in user:
            continue
        for item in user['story_items']:
            slug = item['id']
            if item['id'].startswith('person'):
                s = Slug(slug)
                if s.full != slug:
                    print "{} is now {}".format(item['id'], s.full)
                    item['id'] = s.full
                    dirty = True
        if dirty:
            users.update_one({'email': user['email']},
                            {'$set': {'story_items': user['story_items']}})
            print "<<< updated story of " + user['email']
