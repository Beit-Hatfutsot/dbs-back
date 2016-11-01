import os
import json
import elasticsearch
import pymongo
from celery import Celery
from flask import current_app
from bhs_api import create_app
from bhs_api.utils import uuids_to_str

MIGRATE_MODE = os.environ.get('MIGRATE_MODE')

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
    app.logger.info('Broker at {}'.format(app.config['REDIS_PORT']))
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


def update_es(collection, doc, id):
    index_name = current_app.data_db.name
    try:
        current_app.es.index(index=index_name,
                             doc_type=collection,
                             id=id,
                             body=doc)
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
                                     .format(collection, _id, e))


def reslugify(collection, document):
    ''' append the document id to the slug to ensure uniquness '''
    for lang, val in document['Slug'].items():
        if val:
            doc_id = get_collection_id_field(collection.name)
            document['Slug'][lang] += '-' + str(document[doc_id])


def get_collection_id_field(collection_name):
    doc_id = 'UnitId'
    if collection_name == 'photos':
        doc_id = 'PictureId'
    elif collection_name == 'genTreeIndividuals':
        doc_id = 'ID'
    elif collection_name == 'persons':
        doc_id = 'id'
    elif collection_name == 'synonyms':
        doc_id = '_id'
    elif collection_name == 'trees':
        doc_id = 'num'
    return doc_id


@celery.task
def update_tree(data, collection=None):
    # from celery.contrib import rdb; rdb.set_trace()
    if not collection:
        collection = celery.data_db['trees']
    num = data['num']
    tree = collection.find_one({'num': num})
    doc = data.copy()
    file_id = doc.pop('file_id')
    date = doc.pop('date')
    persons = doc.pop('persons')
    current_ver = {'file_id':file_id,
                   'update_date': date,
                   'persons': persons}
    if tree:
        # don't add the same version twice
        for i in tree['versions']:
            if i['file_id'] == file_id:
                return
        doc['versions'] = tree['versions']
        doc['versions'].append(current_ver)
        collection.update_one({'num': num},
                              {'$set': doc},
                              upsert=True)

    else:
        doc['versions'] = [current_ver]
        collection.insert_one(doc)
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

def update_collection(collection, query, doc):
    if MIGRATE_MODE  == 'i':
        return collection.insert(doc)
    else:
        return collection.update_one(query,
                        {'$set': doc},
                        upsert=True)

def update_doc(collection, document):
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
        doc_id_field = get_collection_id_field(collection.name)
        doc_id = document[doc_id_field]
        # Set up collection specific document ids
        # Search updated collections for collection specific index field
        # and update it.  Save the _id of updated/inserted doc to
        # the 'migration_log' collection
        query = {doc_id_field: doc_id}
        try:
            result = update_collection(collection, query, document)
            try:
                id = result.upserted_id
            except AttributeError:
                result = collection.find_one(query)
                id = result['_id']

        except pymongo.errors.DuplicateKeyError:
            reslugify(collection, document)
            result = collection.insert(document)
            id = result.inserted_id

        update_es(collection.name, document, id)

        try:
            slug = document['Slug']['En']
        except KeyError:
            slug = 'None'

        current_app.logger.info('Updated {} {}: {}, Slug: {}'.format(
            collection.name,
            doc_id_field,
            doc_id,
            slug))
