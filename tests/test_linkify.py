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
    res = client.get(u"/v1/linkify?html={0}+{1}+{2}+{3}".format(PLACES_BOURGES["Header"]["En"],
                                                                PLACES_BOZZOLO["Header"]["En"],
                                                                PERSONALITIES_DAVIDOV["Header"]["En"],
                                                                FAMILY_NAMES_DERI["Header"]["En"]))
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
