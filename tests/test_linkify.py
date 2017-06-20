# -*- coding: utf-8 -*-
from common import *
from mocks import *

def test_linkify_single(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    res = client.get(u"/v1/linkify?html={0}".format(PLACES_BOURGES["Header"]["En"]))
    assert res.status_code == 200, "invalid status, json response: {}".format(res.data)
    assert res.json == {"linkified_html": "<a href=\"http://test.dbs.bh.org.il/place/bourges\">BOURGES</a>"}

def test_linkify(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    res = client.get(u"/v1/linkify?html={0}+{1}+{2}+{3}".format(PLACES_BOURGES["Header"]["En"],
                                                                PLACES_BOZZOLO["Header"]["En"],
                                                                PERSONALITIES_DAVIDOV["Header"]["En"],
                                                                FAMILY_NAMES_DERI["Header"]["En"]))
    assert res.status_code == 200, "invalid status, json response: {}".format(res.data)
    assert res.json == {"linkified_html": "<a href=\"http://test.dbs.bh.org.il/place/bourges\">BOURGES</a> <a href=\"http://test.dbs.bh.org.il/place/bozzolo\">BOZZOLO</a> <a href=\"http://test.dbs.bh.org.il/luminary/davydov-karl-yulyevich\">Davydov, Karl Yulyevich</a> <a href=\"http://test.dbs.bh.org.il/familyname/deri\">DER'I</a>"}

def test_linkify_hebrew(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    res = client.get(u"/v1/linkify?html={0}".format(u"בוצולו"))
    assert res.status_code == 200, "invalid status, json response: {}".format(res.data)
    assert res.json == {u"linkified_html": u"<a href=\"http://test.dbs.bh.org.il/he/מקום/בוצולו\">בוצולו</a>"}

def test_linkify_title_in_title(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    res = client.get(u"/v1/linkify?html={0}".format(u"בוצולו"))
    assert res.status_code == 200, "invalid status, json response: {}".format(res.data)
    assert res.json == {u"linkified_html": u"<a href=\"http://test.dbs.bh.org.il/he/מקום/בוצולו\">בוצולו</a>"}
