# coding: utf-8
import json
import boto
import elasticsearch
import requests
from migration.tasks import update_doc, update_tree
from migration.files import upload_file
from test_search import given_local_elasticsearch_client_with_test_data
from scripts.ensure_required_metadata import EnsureRequiredMetadataCommand
from copy import deepcopy
from mocks import PLACE_BIELSK_NOT_FOR_VIEWING


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

    def _handle_process_item_results(self, num_actions, errors, results, collection_name):
        if not hasattr(self, "process_item_results"):
            self.process_item_results = []
        code, msg, processed_key = results
        self.process_item_results.append((collection_name,
                                          {False: "ERROR",  1: "UPDATED_METADATA", 2: "ADDED_ITEM", 3: "DELETED_ITEM", 4: "NO_UPDATE_NEEDED"}[code],
                                          processed_key))
        return super(MockEnsureRequiredMetadataCommand, self)._handle_process_item_results(num_actions, errors, results, collection_name)

    def _parse_args(self):
        return type("MockArgs", (object,), {"key": None,
                                            "collection": None,
                                            "debug": True,
                                            "add": True,
                                            "limit": None,
                                            "legacy": False,
                                            "index": None})


def given_ensure_required_metadata_ran(app):
    command = MockEnsureRequiredMetadataCommand(app=app)
    command.main()
    app.es.indices.refresh(app.es_data_db_index_name)
    return getattr(command, "process_item_results", [])


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
        # make sure the document does not exist in mongo
        assert not collection.find_one({'UnitId':1000})
        # this will create the document in mongo
        update_doc(collection, deepcopy(THE_TESTER))
        doc =  collection.find_one({'UnitId':1000})
        assert doc['UnitText1']['En'] == 'The Tester'
        assert doc["UnitId"] == 1000
        # check in elasticsearch
        expected_elasticsearch_body = dict(deepcopy(THE_TESTER),
                                           Header={"En": "Nik Nikos", "He": "_"},
                                           Slug={"En": "luminary_nik-nikos"},
                                           related=["place_some"])
        elasticsearch.Elasticsearch.index.assert_called_once_with(body=expected_elasticsearch_body,
                                                                  doc_type='personalities',
                                                                  id=1000,
                                                                  index='bhdata',)

def test_updated_doc(mocker, app):
    ''' testing a creation and an update, ensuring uniquness '''
    mocker.patch('elasticsearch.Elasticsearch.index')
    mocker.patch('elasticsearch.Elasticsearch.update')
    collection = app.data_db['personalities']
    with app.app_context():
        the_tester = deepcopy(THE_TESTER)
        update_doc(collection, the_tester)
        assert collection.find_one({'UnitId':1000})['Slug']['En'] == "luminary_nik-nikos"
        elasticsearch.Elasticsearch.index.assert_called_once_with(
            index="bhdata", doc_type="personalities", id=1000,
            body = dict(deepcopy(THE_TESTER),
                        Header={"En": "Nik Nikos", "He": "_"},
                        Slug={"En": "luminary_nik-nikos"},
                        related=["place_some"])
        )
        updated_tester = deepcopy(the_tester)
        updated_tester['Header']['En'] = 'Nikos Nikolveich'
        updated_tester['UnitText1']['En'] = 'The Great Tester'
        update_doc(collection, updated_tester)
        elasticsearch.Elasticsearch.update.assert_called_once_with(
            index = 'bhdata', doc_type = 'personalities', id = 1000,
            body = dict(deepcopy(THE_TESTER),
                        Header={"En": "Nikos Nikolveich", "He": "_"},
                        Slug={"En": "luminary_nik-nikos"},
                        related=["place_some"],
                        UnitText1={"En": "The Great Tester"})
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
    assert es_search(app, "persons", "person_id:I2") == []  # living person (in mongo)
    assert es_search(app, "persons", "person_id:I3") == []  # dead person (in mongo)
    assert [h["person_id"] for h in es_search(app, "persons", "person_id:I687")] == ["I687"]  # living person in ES
    assert set(given_ensure_required_metadata_ran(app)) == {('places', 'ADDED_ITEM', 3),
                                                            ('places', 'DELETED_ITEM', 71255),
                                                            ('places', 'DELETED_ITEM', 71236),
                                                            # item is not allowed for viewing, and is already not in ES so no update needed
                                                            ('places', 'NO_UPDATE_NEEDED', PLACE_BIELSK_NOT_FOR_VIEWING["UnitId"]),
                                                            ('familyNames', 'DELETED_ITEM', 77321),
                                                            ('familyNames', 'DELETED_ITEM', 77323),
                                                            ('photoUnits', 'DELETED_ITEM', 140068),
                                                            ('photoUnits', 'DELETED_ITEM', 137523),
                                                            ('personalities', 'ADDED_ITEM', 1),
                                                            ('personalities', 'NO_UPDATE_NEEDED', 2),
                                                            ('personalities', 'DELETED_ITEM', 93967),
                                                            ('personalities', 'DELETED_ITEM', 93968),
                                                            ('movies', 'DELETED_ITEM', 111554),
                                                            ('movies', 'DELETED_ITEM', 111553),
                                                            ('persons', 'NO_UPDATE_NEEDED', (1, 0, 'I2')),
                                                            ('persons', 'ADDED_ITEM', (1, 0, 'I3')),
                                                            ('persons', 'DELETED_ITEM', (1933, 0, 'I687')),
                                                            ('persons', 'DELETED_ITEM', (1196, 0, 'I686')),
                                                            ('persons', 'DELETED_ITEM', (6654, 0, 'I7787')),
                                                            ('persons', 'DELETED_ITEM', (6654, 0, 'I7788')),}
    # running again - to make sure it searches items properly in ES
    # items deleted in previous results - don't appear now
    # items added / no update needed in previous results - all have no_update_needed now
    assert set(given_ensure_required_metadata_ran(app)) == {('places', 'NO_UPDATE_NEEDED', 3),
                                                            ('places', 'NO_UPDATE_NEEDED', PLACE_BIELSK_NOT_FOR_VIEWING["UnitId"]),
                                                            ('personalities', 'NO_UPDATE_NEEDED', 1),
                                                            ('personalities', 'NO_UPDATE_NEEDED', 2),
                                                            ('persons', 'NO_UPDATE_NEEDED', (1, 0, 'I2')),
                                                            ('persons', 'NO_UPDATE_NEEDED', (1, 0, 'I3'))}
    # new item in mongo - added to ES (because add parameter is enabled in these tests)
    assert es_search(app, "personalities", "UnitId:1") == [{u'DisplayStatusDesc': u'free',
                                                            u'RightsDesc': u'Full',
                                                            u'Slug': {u'En': u'personality_tester',
                                                                      u'He': u'\u05d0\u05d9\u05e9\u05d9\u05d5\u05ea_\u05d1\u05d5\u05d3\u05e7'},
                                                            u'StatusDesc': u'Completed',
                                                            u'UnitId': 1,
                                                            u'UnitText1': {u'En': u'tester',
                                                                           u'He': u'\u05d1\u05d5\u05d3\u05e7'}}]
    # modifying slug in mongo - should update slug in ES
    assert [h["Slug"]["En"] for h in es_search(app, "personalities", "UnitId:1")] == ["personality_tester"]
    mock_db["personalities"].update_one({"UnitId": 1}, {"$set": {"Slug.En": "personality_tester-modified"}})
    given_ensure_required_metadata_ran(app)
    assert [h["Slug"]["En"] for h in es_search(app, "personalities", "UnitId:1")] == ["personality_tester-modified"]
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
    # dead person - added to ES
    assert [h["person_id"] for h in es_search(app, "persons", "person_id:I3")] == ["I3"]
    # living person in mongo - not synced to ES
    assert [h["person_id"] for h in es_search(app, "persons", "person_id:I2")] == []
    # living person in ES - deleted
    assert [h["person_id"] for h in es_search(app, "persons", "person_id:I687")] == []
    assert [h["person_id"] for h in es_search(app, "persons", "person_id:I686")] == []
    # person has first_name / last_name fields (added during migration process for elasticsearch indexing)
    assert [h["first_name_lc"] for h in es_search(app, "persons", "person_id:I3")] == ["deady"]
    assert [h["last_name_lc"] for h in es_search(app, "persons", "person_id:I3")] == ["deadead"]
