#!/usr/bin/env python

import glob
import os

import pymongo

import utils

config_file = '/home/bhs/.soundcloud'

sc_client = utils.get_sc_client(config_file)

db = pymongo.Connection()['bh']
collection = db['uploaded_music']

music_dir = '/home/bhs/bhp_storage/Music'

os.chdir(music_dir)
for fn in glob.glob("*.mp3"):
    saved = collection.find_one({'filename': fn})
    if saved and not saved.has_key('Exception'):
        print 'File {} was already uploaded - skipping it'.format(fn)
        continue
    try:
        track = utils.upload_to_soundcloud(sc_client, fn)
        track['filename'] = fn
        print 'Uploaded {} to soundcloud - got id {} at {}'.format(fn, track['id'], track['permalink_url'])
        collection.insert(track)
    except Exception as e:
        print 'Error uploading {} to Soundcloud: {}'.format(fn, e.message)
        collection.insert({'filename': fn, 'Exception': e.message})
