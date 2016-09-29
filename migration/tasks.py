import pymongo
import logging
from celery import Celery
from bhs_api.utils import get_conf

app = Celery('migration.tasks', broker='redis://guest@localhost//')

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
    return doc_id


@app.task
def update_row(document, collection_name):
    conf = get_conf(set(['data_db_host',
                         'data_db_port',
                         'data_db_name',
                        ]))
    target_db = pymongo.MongoClient(host=conf.data_db_host,
                                    port=conf.data_db_port)[conf.data_db_name]
    update_doc(collection, document)

def update_doc(collection, document):
    doc_id_field = get_collection_id_field(collection.name)
    doc_id = document[doc_id_field]
    logging.info('updating {} in {}'.format(doc_id, collection.name))
    # family trees get special treatment
    if collection.name == 'genTreeIndividuals':
        tree_num = document['GTN']
        logging.debug('updating {}.{}'.format(tree_num, document['II']))
        collection.update_one({'GTN': tree_num, 'II': document['II']},
                              {'$set': document},
                              upsert=True)
    else:
        # Set up collection specific document ids
        # Search updated collections for collection specific index field
        # and update it.  Save the _id of updated/inserted doc to
        # the 'migration_log' collection
        query = {doc_id_field: doc_id}
        try:
            r = collection.update_one(query,
                                      {'$set': document},
                                      upsert=True)
        except pymongo.errors.DuplicateKeyError:
            reslugify(collection, document)
            collection.insert(document)