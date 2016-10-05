from migration.tasks import update_doc

def test_update_doc(mock_db):
    collection = mock_db['personalities']
    update_doc(collection, {
        'UnitId': '1',
        'UnitText1.En': 'The Tester'
    })
    doc =  collection.find_one({'UnitId':'1'})
    assert doc['UnitText1']['En'] == 'The Tester'
