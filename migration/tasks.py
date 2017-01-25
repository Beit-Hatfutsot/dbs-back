import os
import json
import elasticsearch
import pymongo
from celery import Celery
from flask import current_app
from bhs_api import create_app
from bhs_api.utils import uuids_to_str
from bhs_api.item import get_collection_id_field, create_slug
from scripts.get_places_geo import get_place_geo
from scripts.batch_related import get_bhp_related


MIGRATE_MODE = os.environ.get('MIGRATE_MODE')
MIGRATE_ES = os.environ.get('MIGRATE_ES', '1')
MIGRATE_RELATED = os.environ.get('MIGRATE_RELATED', True)
INDICES = {
    'places' : ['UnitId', 'DisplayStatusDesc', 'RightsDesc', 'StatusDesc', 'Header.En', 'Header.He'],
    'familyNames' : ['UnitId', 'DisplayStatusDesc', 'RightsDesc', 'StatusDesc', 'Header.En', 'Header.He'],
    'lexicon' : ['UnitId'],
    'photoUnits' : ['UnitId', 'DisplayStatusDesc', 'RightsDesc', 'StatusDesc', 'Header.En', 'Header.He'],
    'photos' : ['PictureId', 'PictureFileName', 'PicturePath'],
    'persons' : ['name_lc.0', 'name_lc.1', 'sex', 'BIRT_PLAC_lc', 'MARR_PLAC_lc', 'tree_num', 'DEAT_PLAC_lc'],
    'synonyms': ['s_group', 'str_lc'],
    'personalities' : ['UnitId', 'DisplayStatusDesc', 'RightsDesc', 'StatusDesc', 'Header.En', 'Header.He']
}

def make_celery():
    app, conf = create_app()
    if app.config['REDIS_PASSWORD']:
        redis_broker='redis://:{}@{}:{}/0'.format(
            app.config['REDIS_PASSWORD'],
            app.config['REDIS_HOST'],
            app.config['REDIS_PORT'],
        )
    else:
        redis_broker='redis://{}:{}/0'.format(
            app.config['REDIS_HOST'],
            app.config['REDIS_PORT'],
        )
        app.logger.info('MIGRATE_MODE: {}, MIGRATE_ES: {}, Broker at {}'
                        .format(MIGRATE_MODE, MIGRATE_ES,app.config['REDIS_HOST']))
    celery = Celery(app.import_name, broker=redis_broker)
    celery.conf.update(app.config)
    celery.data_db = app.data_db
    # boiler plate to get our tasks running in the app context
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery
celery = make_celery()


def ensure_indices(collection):
    indices = INDICES.get(collection.name, set())
    for index in indices:
        collection.ensure_index(index)
    # add unique inxexes
    if collection.name == 'persons':
        collection.create_index([("tree_num", pymongo.ASCENDING),
                ("tree_version", pymongo.ASCENDING),
                ("id", pymongo.ASCENDING),
            ],
            unique=True, sparse=True)
    else:
        collection.create_index("Slug.He", unique=True, sparse=True)
        collection.create_index("Slug.En", unique=True, sparse=True)

def update_es(collection, doc, id):
    if MIGRATE_ES != '1':
        return

    index_name = current_app.data_db.name
    body = doc.copy()
    if '_id' in body:
        del body['_id']
    try:
        current_app.es.index(index=index_name,
                             doc_type=collection,
                             id=id,
                             body=body)
    except elasticsearch.exceptions.SerializationError:
        # UUID fields are causing es to crash, turn them to strings
        uuids_to_str(doc)
        try:
            current_app.es.index(index=index_name,
                                 doc_type=collection,
                                 id=id,
                                 body=doc)
        except elasticsearch.exceptions.SerializationError as e:
            current_app.logger.error("Elastic search index failed for {}:{} with {}"
                                     .format(collection, id, e))


def reslugify(collection, document):
    ''' append the document id to the slug to ensure uniquness '''
    for lang, val in document['Slug'].items():
        if val:
            doc_id = get_collection_id_field(collection.name)
            document['Slug'][lang] += '-' + str(document[doc_id])


@celery.task
def update_tree(data, db=None):
    '''  acelery task to update or create a tree '''
    if not db:
        trees = celery.data_db['trees']
        persons = celery.data_db['persons']
    else:
        trees = db['trees']
        persons = db['persons']

    num = data['num']
    tree = trees.find_one({'num': num})
    doc = data.copy()
    file_id = doc.pop('file_id')
    date = doc.pop('date')
    persons_count = doc.pop('persons')
    current_ver = {'file_id':file_id,
                   'update_date': date,
                   'persons': persons_count}
    if tree:
        # don't add the same version twice
        for i in tree['versions']:
            if i['file_id'] == file_id:
                return
        doc['versions'] = tree['versions']
        doc['versions'].append(current_ver)
        trees.update_one({'num': num},
                              {'$set': doc},
                              upsert=True)
        last_version = len(tree['versions'])-1
        current_app.logger.info('archiving persons w/ versions<{} in tree {}'
                                .format(last_version, doc['num']))
        persons.update_many(
            {'tree_num': num,
             'tree_version': {'$lt': last_version}},
            {'$set': {'archived': True}}
        )

    else:
        doc['versions'] = [current_ver]
        trees.insert_one(doc)
    current_app.redis.set('tree_vers_'+str(num),
                          json.dumps(doc['versions']),
                          300)


def find_version(tree_vers, file_id):
    ''' finding the version index based on an array of version and a file id '''
    for i, ver in enumerate(tree_vers):
        if ver['file_id'] == file_id:
            return i
    # let's assume it's the next version
    return i+1


@celery.task
def update_row(doc, collection_name):
    collection = celery.data_db[collection_name]
    # from celery.contrib import rdb; rdb.set_trace()
    update_doc(collection, doc)
    ensure_indices(collection)

def update_collection(collection, query, doc):
    if MIGRATE_RELATED != '0':
        doc['related'] = get_bhp_related(doc, collection.name,
                                                max_items=6,
                                                bhp_only=True)

    if MIGRATE_MODE  == 'i':
        doc['Slug'] = create_slug(doc, collection.name)
        return collection.insert(doc)
    else:
        r = collection.update_one(query,
                                  {'$set': doc},
                                  upsert=False)
        # check if update failed and if it did, create a slug
        if r.modified_count == 0:
            doc['Slug'] = create_slug(doc, collection.name)
            try:
                return collection.insert(doc)
            except pymongo.errors.DuplicateKeyError:
                # oops - seems like we need to add the id to the slug
                reslugify(collection, doc)
                collection.insert(doc)


def update_doc(collection, document):
    # update place items with geojson
    if collection.name == 'places':
        document['geometry'] = get_place_geo(document)

    # family trees get special treatment
    if collection.name == 'persons':
        tree_num = document['tree_num']
        id = document['id']
        tree_key = 'tree_vers_'+str(tree_num)
        query = {'tree_num': tree_num, 'id': id}
        tree_vers = current_app.redis.get(tree_key)
        if tree_vers:
            tree_vers = json.loads(tree_vers)
            i = find_version(tree_vers, document['tree_file_id'])
        else:
            tree = current_app.data_db['trees'].find_one({'num':tree_num})
            if tree:
                tree_vers = tree['versions']
                current_app.redis.set(tree_key, json.dumps(tree_vers), 300)
                i = find_version(tree_vers, document['tree_file_id'])
            else:
                current_app.logger.info("didn't find tree number {} using version 0 for {}"
                                         .format(tree_num, id))
                i = 0;

        document['tree_version'] = i
        query['tree_version'] = i

        document['Slug'] = {'En': 'person_{};{}.{}'.format(
                              tree_num,
                              i,
                              id)}
        update_collection(collection, query, document)
        current_app.logger.info('Updated person: {}.{}'
                                .format(tree_num, id))
    else:
        # post parsing: add _id and Slug
        doc_id_field = get_collection_id_field(collection.name)
        try:
            doc_id = document[doc_id_field]
        except KeyError:
            current_app.logger.error('update failed because of id {} {}'
                                     .format(collection.name,
                                             doc_id_field,
                                             ))
        if doc_id:
            document['_id'] = doc_id


        query = {doc_id_field: doc_id}
        result = update_collection(collection, query, document)

        update_es(collection.name, document, doc_id)

        try:
            slug = document['Slug']['En']
        except KeyError:
            slug = 'None'

        current_app.logger.info('Updated {} {}: {}, Slug: {}'.format(
            collection.name,
            doc_id_field,
            doc_id,
            slug))
