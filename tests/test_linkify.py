# -*- coding: utf-8 -*-
from common import *
from mocks import *


def test_linkify_single(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    res = client.post("/v1/linkify", data={"html": "hello from BOURGES!!!"})
    assert res.status_code == 200, "invalid status, json response: {}".format(res.data)
    assert res.json == {"familyNames": [], "personalities": [],
                        "places": [{"url": "http://dbs.bh.org.il/place/bourges", "title": "BOURGES"}]}


def test_linkify_all_types(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    res = client.get(u"/v1/linkify?html={0}+{1}+{2}+{3}".format(PLACES_BOURGES["title_en"],
                                                                PLACES_BOZZOLO["title_en"],
                                                                PERSONALITIES_DAVIDOV["title_en"],
                                                                FAMILY_NAMES_DERI["title_en"]))
    assert res.status_code == 200, "invalid status, json response: {}".format(res.data)
    assert res.json == {"familyNames": [{"url": "http://dbs.bh.org.il/familyname/deri", "title": "DER'I"}],
                        "personalities": [{"url": "http://dbs.bh.org.il/luminary/davydov-karl-yulyevich", "title": "Davydov, Karl Yulyevich"},],
                        "places": [{"url": "http://dbs.bh.org.il/place/bourges", "title": "BOURGES"},
                                   {"url": "http://dbs.bh.org.il/place/bozzolo", "title": "BOZZOLO"}]}


def test_linkify_hebrew(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    res = client.get(u"/v1/linkify?html={0}".format(u"בוצולו"))
    assert res.status_code == 200, "invalid status, json response: {}".format(res.data)
    assert res.json == {"familyNames": [], "personalities": [],
                        "places": [{"url": u"http://dbs.bh.org.il/he/מקום/בוצולו", "title": u"בוצולו"}]}

def test_linkify_case_insensitive(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    res = client.get(u"/v1/linkify?html={}".format("boZZolo"))
    assert res.status_code == 200, "invalid status, json response: {}".format(res.data)
    assert res.json == {"familyNames": [], "personalities": [],
                        "places": [{"url": "http://dbs.bh.org.il/place/bozzolo", "title": "BOZZOLO"}]}

def test_linkify_missing_title(client, app):
    place_ixt = {"source": "clearmash", "source_id": "2441266", "collection": "places",
                 "title_en": "IXT", "slug_en": "place_ixt"}
    personality_fxt = {"source": "clearmash", "source_id": "2441267", "collection": "personalities",
                       "title_he": "פחט", "slug_he": "מקום_פחט"}
    given_local_elasticsearch_client_with_test_data(app,
                                                    "test_linkify::test_linkify_missing_title",
                                                    additional_index_docs={"places": [place_ixt],
                                                                           "personalities": [personality_fxt]})
    res = client.get(u"/v1/linkify?html=hello from IXT!")
    assert res.json == {"familyNames": [],
                        "personalities": [],
                        "places": [{u'title': u'IXT', u'url': u'http://dbs.bh.org.il/place/ixt'}]}
    res = client.get(u"/v1/linkify?html=בדיקה פחט!")
    assert res.json == {"familyNames": [],
                        "personalities": [{u'title': u'פחט', u'url': u'http://dbs.bh.org.il/he/\u05d0\u05d9\u05e9\u05d9\u05d5\u05ea/\u05e4\u05d7\u05d8'}],
                        "places": []}
