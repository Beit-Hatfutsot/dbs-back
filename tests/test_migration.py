import boto
from migration.tasks import update_doc, update_tree
from migration.files import upload_file

def test_update_doc(mock_db, app):
    collection = mock_db['personalities']
    with app.app_context():
        update_doc(collection, {
            'UnitId': '1',
            'UnitText1.En': 'The Tester'
        })
    doc =  collection.find_one({'UnitId':'1'})
    assert doc['UnitText1']['En'] == 'The Tester'

def test_update_photo(mocker):
    mocker.patch('boto.storage_uri')
    mocker.patch('boto.storage_uri')
    upload_file('from', 'to_bucket', 'to_key')
    boto.storage_uri.assert_called_once_with('to_bucket/to_key', 'gs')

def test_update_tree(mock_db, app):
    with app.app_context():
        update_tree(dict(num=1,
                        file_id='1',
                        persons=8,
                        date='now'),
                    mock_db['trees'])
    tree = mock_db['trees'].find_one({'num': 1})
    assert tree['versions'][0]['file_id'] == '1'
    assert tree['versions'][0]['persons'] == 8
    # adding the same tree again shouldn't do anythong
    with app.app_context():
        update_tree(dict(num=1,
                        file_id='1',
                        persons=8,
                        date='now'),
                    mock_db['trees'])
    tree = mock_db['trees'].find_one({'num': 1})
    assert len(tree['versions']) == 1
    # adding new version
    with app.app_context():
        update_tree(dict(num=1,
                        file_id='5',
                        persons=16,
                        date='right now'),
                    mock_db['trees'])
    tree = mock_db['trees'].find_one({'num': 1})
    assert len(tree['versions']) == 2


def test_update_person(mock_db, app):
    collection = mock_db['persons']
    app.data_db = mock_db
    with app.app_context():
        # first, create a tree
        update_tree(dict(num=1,
                        file_id='1',
                        persons=8,
                        date='now'),
                    mock_db['trees'])
        # and now the tree
        update_doc(collection, {
            'id': 'I1',
            'tree_num': 1,
            'tree_file_id': '1'
            })
    doc =  collection.find_one({'id':'I1'})
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
        update_doc(collection, {
            'id': 'I1',
            'tree_num': 1,
            'tree_file_id': '2'
            })
    assert collection.count({'id':'I1'}) == 2
