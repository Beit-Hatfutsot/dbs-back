import boto
from migration.tasks import update_doc
from migration.files import upload_file

def test_update_doc(mock_db):
    collection = mock_db['personalities']
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
