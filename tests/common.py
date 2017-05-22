from elasticsearch import Elasticsearch
from scripts.elasticsearch_create_index import ElasticsearchCreateIndexCommand
from copy import deepcopy
import os
from bhs_api.item import get_doc_id
from mocks import *


def given_invalid_elasticsearch_client(app):
    app.es = Elasticsearch("192.0.2.0", timeout=0.000000001)

def index_doc(app, collection, doc):
    doc = deepcopy(doc)
    doc.get("Header", {}).setdefault("He_lc", doc.get("Header", {}).get("He", "").lower())
    doc.get("Header", {}).setdefault("En_lc", doc.get("Header", {}).get("En", "").lower())
    if collection == "persons":
        doc_id = "{}_{}_{}".format(doc["tree_num"], doc["tree_version"], doc["person_id"])
    else:
        doc_id = get_doc_id(collection, doc)
    app.es.index(index=app.es_data_db_index_name, doc_type=collection, body=doc, id=doc_id)

def index_docs(app, collections, reuse_db=False):
    if not reuse_db or not app.es.indices.exists(app.es_data_db_index_name):
        ElasticsearchCreateIndexCommand().create_es_index(es=app.es, es_index_name=app.es_data_db_index_name, delete_existing=True)
        for collection, docs in collections.items():
            for doc in docs:
                index_doc(app, collection, doc)
        app.es.indices.refresh(app.es_data_db_index_name)

def given_local_elasticsearch_client_with_test_data(app, session_id=None):
    """
    setup elasticsearch on localhost:9200 for testing on a testing index
    if given session_id param and it is the same as previous session_id param - will not reindex the docs
    """
    app.es = Elasticsearch("localhost")
    app.es_data_db_index_name = "bh_dbs_back_pytest"
    if not session_id or session_id != getattr(given_local_elasticsearch_client_with_test_data, "_session_id", None):
        given_local_elasticsearch_client_with_test_data._session_id = session_id
        reuse_db = os.environ.get("REUSE_DB", "") == "1"
        index_docs(app, {
            "places": [PLACES_BOURGES, PLACES_BOZZOLO],
            "photoUnits": [PHOTO_BRICKS, PHOTOS_BOYS_PRAYING],
            "familyNames": [FAMILY_NAMES_DERI, FAMILY_NAMES_EDREHY],
            "personalities": [PERSONALITIES_FERDINAND, PERSONALITIES_DAVIDOV],
            "movies": [MOVIES_MIDAGES, MOVIES_SPAIN],
            "persons": [PERSON_EINSTEIN, PERSON_LIVING],
        }, reuse_db)


def assert_error_response(res, expected_status_code, expected_error_startswith):
    assert res.status_code == expected_status_code
    assert res.json["error"].startswith(expected_error_startswith)

def assert_common_elasticsearch_search_results(res):
    assert res.status_code == 200, "invalid status, json response: {}".format(res.json)
    hits = res.json["hits"]
    shards = res.json["_shards"]
    assert shards["successful"] > 0
    assert shards["failed"] < 1
    assert shards["total"] == shards["successful"]
    assert res.json["took"] > 0
    assert isinstance(res.json["timed_out"], bool)
    return hits


def assert_no_results(res):
    hits = assert_common_elasticsearch_search_results(res)
    assert hits["hits"] == [] and hits["total"] == 0 and hits["max_score"] == None

def assert_search_results(res, num_expected):
    hits = assert_common_elasticsearch_search_results(res)
    assert len(hits["hits"]) == num_expected and hits["total"] == num_expected
    for hit in hits["hits"]:
        assert hit["_index"] == "bh_dbs_back_pytest"
        yield hit

def assert_search_hit_ids(client, search_params, expected_ids, ignore_order=False):
    hit_ids = [hit["_source"].get("Id", hit["_source"].get("id"))
               for hit
               in assert_search_results(client.get(u"/v1/search?{}".format(search_params)),
                                        len(expected_ids))]
    if not ignore_order:
        assert hit_ids == expected_ids
    else:
        assert {id:id for id in hit_ids} == {id:id for id in expected_ids}

def assert_suggest_response(client, collection, string,
                            expected_http_status_code=200, expected_error_message=None, expected_json=None):
    res = client.get(u"/v1/suggest/{}/{}".format(collection, string))
    assert res.status_code == expected_http_status_code
    if expected_error_message is not None:
        assert expected_error_message in res.data
    if expected_json is not None:
        print(res.json)
        assert expected_json == res.json

def dump_res(res):
    print(res.status_code, res.data)
