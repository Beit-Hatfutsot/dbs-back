import boto
import elasticsearch
from migration.tasks import update_doc, update_tree
from migration.files import upload_file

first_tree = dict(num=1,
                    file_id='1',
                    persons=8,
                    date='now')
second_tree = dict(num=1,
                    file_id='5',
                    persons=16,
                    date='right now')


def test_update_doc(mocker, mock_db, app):
    mocker.patch('elasticsearch.Elasticsearch.index')
    collection = mock_db['personalities']
    with app.app_context():
        update_doc(collection, {
            'UnitId': '1',
            'UnitText1.En': 'The Tester',
            '_id': 'some id',
        })
    doc =  collection.find_one({'UnitId':'1'})
    assert doc['UnitText1']['En'] == 'The Tester'
    elasticsearch.Elasticsearch.index.assert_called_once_with(
        body = {'UnitId': '1', 'UnitText1.En': 'The Tester', '_id': 'some id'},
        doc_type = 'personalities',
        id=None,
        index = u'bhdata',
       )

def test_update_photo(mocker):
    mocker.patch('boto.storage_uri')
    mocker.patch('boto.storage_uri')
    upload_file('from', 'to_bucket', 'to_key')
    boto.storage_uri.assert_called_once_with('to_bucket/to_key', 'gs')

def test_update_tree(mock_db, app):

    with app.app_context():
        update_tree(first_tree,
                    mock_db['trees'])
    tree = mock_db['trees'].find_one({'num': 1})
    assert tree['versions'][0]['file_id'] == '1'
    assert tree['versions'][0]['persons'] == 8
    # adding the same tree again shouldn't do anythong
    with app.app_context():
        update_tree(first_tree,
                    mock_db['trees'])
    tree = mock_db['trees'].find_one({'num': 1})
    assert len(tree['versions']) == 1
    # adding new version
    with app.app_context():
        update_tree(second_tree,
                    mock_db['trees'])
    tree = mock_db['trees'].find_one({'num': 1})
    assert len(tree['versions']) == 2


def test_update_person(mock_db, app):
    persons = mock_db['persons']
    app.data_db = mock_db
    with app.app_context():
        # first, create a tree
        update_tree(first_tree,
                    mock_db['trees'])
        # and now the tree
        update_doc(persons, {
            'id': 'I1',
            'tree_num': 1,
            'tree_file_id': '1'
            })
        doc =  persons.find_one({'id':'I1'})
    assert doc['tree_version'] == 0
    # 
    with app.app_context():
        update_tree(dict(num=1,
                        file_id='2',
                        persons=16,
                        date='right now'),
                    mock_db['trees'])
        # reset the cache
        app.redis.delete('tree_vers_1')
        update_doc(persons, {
            'id': 'I1',
            'tree_num': 1,
            'tree_file_id': '2'
            })
    assert persons.count({'id':'I1'}) == 2
    # eensure the old I1 is archived
