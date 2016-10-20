import json
import pymongo
from celery import Celery
from flask import current_app
from bhs_api import create_app

def make_celery():
    app, conf = create_app()
    redis_broker='redis://:{}@{}:{}/0'.format(
        app.config['REDIS_PASSWORD'],
        app.config['REDIS_HOST'],
        app.config['REDIS_PORT'],
    )
    app.logger.info('Broker at {}'.format(redis_broker))
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
    elif collection_name == 'synonyms':
        doc_id = '_id'
    elif collection_name == 'trees':
        doc_id = 'tree_num'
    return doc_id


@celery.task
def update_tree(data, collection=None):
    if not collection:
        collection = celery.data_db['trees']
    tree_num = data['tree_num']
    tree = collection.find_one({'tree_num': tree_num})
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
        collection.update_one({'tree_num': tree_num},
                     {'$set': doc})

    else:
        doc['versions'] = [current_ver]
        collection.insert_one(doc)
    current_app.redis.set('tree_vers_'+str(tree_num),
                          json.dumps(doc['versions']),
                          300)


@celery.task
def update_row(doc, collection_name):
    collection = celery.data_db[collection_name]
    # from celery.contrib import rdb; rdb.set_trace()
    update_doc(collection, doc)


def update_doc(collection, document):
    # family trees get special treatment
    if collection.name == 'persons':
        tree_num = document['tree']['tree_num']
        id = document['id']
        tree_key = 'tree_vers_'+str(tree_num)
        query = {'tree.tree_num': tree_num, 'id': id}
        tree_vers = current_app.redis.get(tree_key)
        if tree_vers:
            tree_vers = json.loads(tree_vers)
        else:
            tree = current_app.data_db['trees'].find_one({'tree_num':tree_num})
            if tree:
                tree_vers = tree['versions']
                current_app.redis.set(tree_key, json.dumps(tree_vers), 300)
            else:
                current_app.logger.error("didn't find tree number {} when trying to update {}"
                                         .format(tree_num, id))
                return

        for i, ver in enumerate(tree_vers):
            if ver['file_id'] == document['tree']['file_id']:
                document['tree']['version'] = i
                query['tree.version'] = i
                break

        r = collection.update_one(query,
                                  {'$set': document},
                                  upsert=True)
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
            collection.update_one(query,
                                  {'$set': document},
                                  upsert=True)
        except pymongo.errors.DuplicateKeyError:
            reslugify(collection, document)
            collection.insert(document)

        try:
            slug = document['Slug']['En']
        except KeyError:
            slug = 'None'
        current_app.logger.info('Updated {} {}: {}, Slug: {}'.format(
            collection.name,
            doc_id_field,
            doc_id,
            slug))

