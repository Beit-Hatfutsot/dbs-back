import boto
import elasticsearch
from migration.tasks import update_doc, update_tree
from migration.files import upload_file

first_tree = dict(num=100,
                    file_id='1',
                    persons=8,
                    date='now')
second_tree = dict(num=100,
                    file_id='5',
                    persons=16,
                    date='right now')

the_tester = {
    'UnitId': '1000',
    'UnitText1': {'En': 'The Tester'},
    'Header': {'En': 'Nik Nikos'},
    'UnitPlaces': [{'PlaceIds': 3}],
            'StatusDesc': 'Completed',
            'RightsDesc': 'Full',
            'DisplayStatusDesc':  'free',
}

def test_update_doc(mocker, app):
    mocker.patch('elasticsearch.Elasticsearch.index')
    collection = app.data_db['personalities']
    with app.app_context():
        r=update_doc(collection, the_tester)
    doc =  collection.find_one({'UnitId':'1000'})
    assert doc['UnitText1']['En'] == 'The Tester'
    elasticsearch.Elasticsearch.index.assert_called_once_with(
        body = the_tester,
        doc_type = 'personalities',
        id=doc["_id"],
        index = 'db',
       )
    assert doc['related'] == ['place_some']
    collection.remove({'UnitId':'1000'})

def test_updated_doc(mocker, app):
    mocker.patch('elasticsearch.Elasticsearch.index')
    collection = app.data_db['personalities']
    with app.app_context():
        update_doc(collection, the_tester)
        updated_tester = the_tester.copy()
        updated_tester['UnitText1']['En'] = 'The Great Tester'
        update_doc(collection, updated_tester)

    assert collection.count({'UnitId':'1000'}) == 1
    collection.remove({'UnitId':'1000'})

def test_update_photo(mocker):
    mocker.patch('boto.storage_uri')
    mocker.patch('boto.storage_uri')
    upload_file('from', 'to_bucket', 'to_key')
    boto.storage_uri.assert_called_once_with('to_bucket/to_key', 'gs')

def test_update_tree(app):

    with app.app_context():
        update_tree(first_tree, app.data_db)
    tree = app.data_db['trees'].find_one({'num': 100})
    assert tree['versions'][0]['file_id'] == '1'
    assert tree['versions'][0]['persons'] == 8
    # adding the same tree again shouldn't do anythong
    with app.app_context():
        update_tree(first_tree, app.data_db)
    tree = app.data_db['trees'].find_one({'num': 100})
    assert len(tree['versions']) == 1
    # adding new version
    with app.app_context():
        update_tree(second_tree, app.data_db)
    tree = app.data_db['trees'].find_one({'num': 100})
    assert len(tree['versions']) == 2


def test_update_person(app):
    persons = app.data_db['persons']
    with app.app_context():
        # first, create a tree
        update_tree(first_tree, app.data_db)
        # and now the tree
        update_doc(persons, {
            'id': 'I1',
            'tree_num': 1,
            'tree_file_id': 'initial'
            }
        )
        doc =  persons.find_one({'id':'I1'})
    assert doc['tree_version'] == 0
    # ensure we keep the old version
    with app.app_context():
        update_tree(dict(num=1,
                        file_id='2',
                        persons=16,
                        date='right now'),
                    app.data_db)
        # reset the cache
        app.redis.delete('tree_vers_1')
        update_doc(persons, {
            'id': 'I1',
            'tree_num': 1,
            'tree_file_id': '2'
            })
    assert persons.count({'id':'I1'}) == 2
    # eensure the old I1 is archived
    doc = persons.find_one({'id':'I1', 'tree_version': 0})
    assert doc['archived'] == True
    doc = persons.find_one({'id':'I1', 'tree_version': 1})
    assert 'archived' not in doc
