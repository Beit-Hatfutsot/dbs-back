import json
import boto
import elasticsearch
import requests
from migration.tasks import update_doc, update_tree
from migration.files import upload_file
from test_search import given_local_elasticsearch_client_with_test_data
from scripts.ensure_required_metadata import EnsureRequiredMetadataCommand
from copy import deepcopy


first_tree = dict(num=100,
                    file_id='1',
                    persons=8,
                    date='now')
second_tree = dict(num=100,
                    file_id='5',
                    persons=16,
                    date='right now')

THE_TESTER = {
    'UnitId': 1000,
    'UnitText1': {'En': 'The Tester'},
    'Header': {'En': 'Nik Nikos'},
    'UnitPlaces': [{'PlaceIds': 3}],
    'StatusDesc': 'Completed',
    'RightsDesc': 'Full',
    'DisplayStatusDesc':  'free',
}


class MockEnsureRequiredMetadataCommand(EnsureRequiredMetadataCommand):
    def _parse_args(self):
        return type("MockArgs", (object,), {"key": None,
                                            "collection": None,
                                            "debug": True,
                                            "add_to_es": True})


def given_ensure_required_metadata_ran(app):
    MockEnsureRequiredMetadataCommand(app=app).main()
    app.es.indices.refresh(app.es_data_db_index_name)


def es_search(app, collection_name, query):
    return [h["_source"] for h in app.es.search(index=app.es_data_db_index_name,
                                                doc_type=collection_name, q=query)["hits"]["hits"]]



def test_update_doc(mocker, app):
    ''' This function tests the simplest case for
        migration.tasks.update_doc function
    '''
    mocker.patch('elasticsearch.Elasticsearch.index')
    collection = app.data_db['personalities']
    with app.app_context():
        # make sure the collection is clean
        doc =  collection.find_one({'UnitId':1000})
        assert not doc
        r=update_doc(collection, THE_TESTER)
        doc =  collection.find_one({'UnitId':1000})
        assert doc['UnitText1']['En'] == 'The Tester'
        assert doc['_id'] == 1000
        expected_body = deepcopy(THE_TESTER)
        del expected_body["_id"]
        expected_body["Header"]["He"] = "_"
        elasticsearch.Elasticsearch.index.assert_called_once_with(
            body = expected_body,
            doc_type = 'personalities',
            id=doc['_id'],
            index = 'bhdata',
        )
        assert doc['related'] == ['place_some']

def test_updated_doc(mocker, app):
    ''' testing a creation and an update, ensuring uniquness '''
    mocker.patch('elasticsearch.Elasticsearch.index')
    collection = app.data_db['personalities']
    with app.app_context():
        update_doc(collection, deepcopy(THE_TESTER))
        slug = collection.find_one({'UnitId':1000})['Slug']['En']
        assert slug ==  collection.find_one({'UnitId':1000})['Slug']['En']
        id = THE_TESTER['_id']
        expected_body = deepcopy(THE_TESTER)
        del expected_body["_id"]
        expected_body["Header"]["He"] = "_"
        # no hebrew slug
        expected_body["Slug"] = {"En": expected_body["Slug"]["En"]}
        elasticsearch.Elasticsearch.index.assert_called_once_with(
            body = expected_body,
            doc_type = "personalities",
            id=id,
            index = "bhdata",
        )
        elasticsearch.Elasticsearch.index.reset_mock()
        updated_tester = deepcopy(THE_TESTER)
        updated_tester['Header']['En'] = 'Nikos Nikolveich'
        updated_tester['UnitText1']['En'] = 'The Great Tester'
        update_doc(collection, updated_tester)
        assert collection.count({'UnitId':1000}) == 1
        expected_body = deepcopy(updated_tester)
        del expected_body['_id']
        expected_body["Header"] = {"En": "Nikos Nikolveich"}
        elasticsearch.Elasticsearch.index.assert_called_once_with(
            body = expected_body,
            doc_type = 'personalities',
            id=id,
            index = 'bhdata',
        )

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


def test_update_place(mocker, app):
    mocker.patch('elasticsearch.Elasticsearch.index')
    mocker.patch('requests.get')
    resp = requests.Response()
    resp.status_code = 200
    resp._content = json.dumps({'features': [{'geometry': 'geo'}]})
    requests.get.return_value = resp
    collection = app.data_db['places']
    with app.app_context():
        update_doc(collection, {
            'UnitId': 2000,
            'UnitText1': {'En': "Oh la la!"},
            'Header': {'En': 'Paris'},
        })

    doc =  collection.find_one({'UnitId':2000})
    assert doc['geometry'] == 'geo'


def test_ensure_metadata(app, mock_db):
    app.data_db = mock_db
    given_local_elasticsearch_client_with_test_data(app)
    assert es_search(app, "personalities", "UnitId:1") == []
    assert es_search(app, "personalities", "UnitId:2") == []
    assert es_search(app, "places", "UnitId:3") == []
    assert es_search(app, "persons", "PID:I2") == []
    given_ensure_required_metadata_ran(app)
    # new item in mongo - added to ES (because add_to_es parameter is enabled in these tests)
    assert es_search(app, "personalities", "UnitId:1") == [{u'DisplayStatusDesc': u'free',
                                                            u'RightsDesc': u'Full',
                                                            u'Slug': {u'En': u'personality_tester',
                                                                      u'He': u'\u05d0\u05d9\u05e9\u05d9\u05d5\u05ea_\u05d1\u05d5\u05d3\u05e7'},
                                                            u'StatusDesc': u'Completed',
                                                            u'UnitId': 1,
                                                            u'UnitText1': {u'En': u'tester',
                                                                           u'He': u'\u05d1\u05d5\u05d3\u05e7'}}]
    # modifying slug in mongo - should update slug in ES
    assert [h["Slug"]["En"] for h in es_search(app, "personalities", "UnitId:2")] == ["personality_another-tester"]
    mock_db["personalities"].update_one({"UnitId": 2}, {"$set": {"Slug.En": "personality_another-tester-modified"}})
    given_ensure_required_metadata_ran(app)
    assert [h["Slug"]["En"] for h in es_search(app, "personalities", "UnitId:2")] == ["personality_another-tester-modified"]
    # changing item rights in ES - will fix them when updating from mongo
    app.es.update(index=app.es_data_db_index_name, doc_type="places", id=3, body={"doc": {"StatusDesc": "PARTIAL"}})
    app.es.indices.refresh()
    assert [h["StatusDesc"] for h in es_search(app, "places", "UnitId:3")] == ["PARTIAL"]
    given_ensure_required_metadata_ran(app)
    assert [h["StatusDesc"] for h in es_search(app, "places", "UnitId:3")] == ["Completed"]
    # setting item rights to private - should delete item in ES
    assert len(es_search(app, "places", "UnitId:3")) == 1
    mock_db["places"].update_one({"UnitId": 3}, {"$set": {"StatusDesc": "PRIVATE"}})
    given_ensure_required_metadata_ran(app)
    assert len(es_search(app, "places", "UnitId:3")) == 0
    # persons - added to ES
    assert [h["PID"] for h in es_search(app, "persons", "PID:I2")] == ["I2"]


