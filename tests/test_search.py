# -*- coding: utf-8 -*-
from common import *
from mocks import *

def assert_doc(app, doc_id, **assert_attrs):
    res = app.es.get(index=app.es_data_db_index_name, id=doc_id)
    doc = res["_source"]
    for k,v in assert_attrs.items():
        assert doc.get(k) == v, "expected={}, actual={}".format(assert_attrs, {k:v for k,v in doc.items() if k in assert_attrs})

def test_search_without_parameters_should_return_error(client):
    assert_error_response(client.get('/v1/search'), 400, "You must specify a search query")

def test_search_without_elasticsearch_should_return_error(client, app):
    given_invalid_elasticsearch_client(app)
    assert_error_response(client.get('/v1/search?q=test'), 500, "Error connecting to Elasticsearch")

def test_searching_for_nonexistant_term_should_return_no_results(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_no_results(client.get('/v1/search?q=testfoobarbazbaxINVALID'))

def test_general_search_single_result(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    # test data contains exactly 1 match for "BOURGES"
    res = client.get("/v1/search?q=BOURGES")
    for hit in assert_search_results(res, 1):
        assert hit["collection"] == "places"
        assert hit["title_en"] == "BOURGES"

def test_general_search_multiple_results(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    # for reference - to know how the results should be sorted
    assert_doc(app, u'clearmash_154126', **{"title_en": "BOZZOLO", "title_he": u"בוצולו"})
    assert_doc(app, u'clearmash_244123', **{"title_en": "BOURGES", "title_he": u"בורג'"})
    assert_doc(app, u'clearmash_222830', **{"title_en": "EDREHY", "title_he": u"אדרהי"})
    assert_doc(app, u'clearmash_175821', **{"title_en": "Boys (jews) praying at the synagogue of Mosad Aliyah, Israel 1963",
                                            "title_he": u"נערים יהודים מתפללים בבית הכנסת במוסד עליה, ישראל 1960-1950"})
    assert_doc(app, u'clearmash_222829', **{"title_en": "DER'I", "title_he": u"דרעי"})
    assert_doc(app, u'clearmash_130323', **{"title_en": "Living Moments in Jewish Spain (English jews)",
                                            "title_he": u"רגעים עם יהודי ספרד (אנגלית)"})
    # relevancy search
    assert_search_hit_ids(client, u"q=יהודים&sort=rel", [u'clearmash_154126', u'clearmash_244123', u'clearmash_222830', u'clearmash_175821', u'clearmash_222829'], ignore_order=True)
    # sort abc with hebrew query - will sort based on the hebrew titles
    assert_search_hit_ids(client, u"q=יהודים&sort=abc", [u'clearmash_222830', u'clearmash_154126', u'clearmash_244123', u'clearmash_222829', u'clearmash_175821'])
    # sort abc with english query - will sort based on the english titles
    assert_search_hit_ids(client, u"q=jews&sort=abc", [u'clearmash_244123', u'clearmash_175821', u'clearmash_154126', u'clearmash_224646', u'clearmash_130323'])

def test_places_search(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    # for reference - to know how the results should be sorted
    assert_doc(app, u'clearmash_154126', **{"title_en": "BOZZOLO", "title_he": u"בוצולו"})
    assert_doc(app, u'clearmash_244123', **{"title_en": "BOURGES", "title_he": u"בורג'"})
    assert_search_hit_ids(client, u"q=יהודים&collection=places", [u'clearmash_154126', u'clearmash_244123'], ignore_order=True)
    assert_search_hit_ids(client, u"q=יהודים&collection=places&sort=abc", [u'clearmash_154126', u'clearmash_244123'])
    assert_search_hit_ids(client, u"q=jews&collection=places&sort=abc", [u'clearmash_244123', u'clearmash_154126'])

def test_images_search(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_doc(app, u'clearmash_189948', **{"title_en": "Building Blocks for Housing Projects, Israel 1950s",
                                            "title_he": u"לבנים למפעל בנייה למגורים, ישראל שנות 1960",
                                            "period_startdate": "1960-01-01T00:00:00Z"})
    assert_doc(app, u'clearmash_175821', **{"title_en": "Boys (jews) praying at the synagogue of Mosad Aliyah, Israel 1963",
                                            "title_he": u"נערים יהודים מתפללים בבית הכנסת במוסד עליה, ישראל 1960-1950",
                                            "period_startdate": "1950-01-01T00:00:00Z"})
    assert_search_hit_ids(client, u"q=Photo&collection=photoUnits&sort=year", [u'clearmash_175821', u'clearmash_189948'])
    assert_search_hit_ids(client, u"q=Photo&collection=photoUnits&sort=abc", [u'clearmash_175821', u'clearmash_189948'])
    assert_search_hit_ids(client, u"q=זוננפלד&collection=photoUnits&sort=abc", [u'clearmash_189948', u'clearmash_175821'])

def test_family_names_search(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_doc(app, u'clearmash_222829', **{"title_en": "DER'I", "title_he": u"דרעי"})
    assert_doc(app, u'clearmash_222830', **{"title_en": "EDREHY", "title_he": u"אדרהי"})
    assert_search_hit_ids(client, u"q=משפחה&collection=familyNames&sort=abc", [u'clearmash_222830', u'clearmash_222829'])
    assert_search_hit_ids(client, u"q=EDREHY+DER'I&collection=familyNames&sort=abc", [u'clearmash_222829', u'clearmash_222830'])

def test_personalities_search(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_doc(app, u'clearmash_202014', **{'title_en': "Davydov, Karl Yulyevich"})
    assert_doc(app, u'clearmash_202015', **{'title_en': "David, Ferdinand", "title_he": u"דוד, פרדיננד"})
    assert_search_hit_ids(client, u"q=Leipzig&collection=personalities&sort=abc", [u'clearmash_202015', u'clearmash_202014'])
    assert_search_hit_ids(client, u"q=לייפציג&collection=personalities&sort=abc", [u'clearmash_202014', u'clearmash_202015'])

def test_movies_search(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_doc(app, u'clearmash_224646', **{"title_en": "Jewish Communities in the Middle Ages: Babylonia; Spain; Ashkenaz (Hebrew)",
                                            "title_he": u"קהילות יהודיות בימי הביניים:  בבל; ספרד; אשכנז (עברית)"})
    assert_doc(app, u'clearmash_130323', **{"title_en": "Living Moments in Jewish Spain (English jews)",
                                            "title_he": u"רגעים עם יהודי ספרד (אנגלית)"})
    assert_search_hit_ids(client, u"q=jews&collection=movies&sort=abc", [u'clearmash_224646', u'clearmash_130323'])

def test_invalid_suggest(client, app):
    given_invalid_elasticsearch_client(app)
    assert_suggest_response(client, u"places", u"mos",
                            500, expected_error_message="unexpected exception getting completion data: ConnectionError")

def test_general_suggest(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_suggest_response(client, u"*", u"bo",
                            200, expected_json={"phonetic": {"places": [], "photoUnits": [], "familyNames": [], "personalities": [], "movies": [], "persons": []},
                                                "contains": {},
                                                "starts_with": {"places": [u'Bourges', u'Bozzolo'],
                                                                               # notice that suggest captilizes all letters
                                                                "photoUnits": ['Boys (Jews) Praying At The Synagogue Of Mosad Aliyah, Israel 1963'],
                                                                "familyNames": [], "personalities": [], "movies": [], "persons": []}})

def test_places_suggest(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_suggest_response(client, u"places", u"bo",
                            200, expected_json={"phonetic": [], "contains": [], "starts_with": ["Bourges", "Bozzolo"]})

def test_images_suggest(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_suggest_response(client, u"photoUnits", u"נער",
                            200, expected_json={u'phonetic': [], u'contains': [],
                                                u'starts_with': [u'נערים יהודים מתפללים בבית הכנסת במוסד עליה, ישראל 1960-1950']})

def test_family_names_suggest(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_suggest_response(client, u"familyNames", u"דר",
                            200, expected_json={u'phonetic': [], u'contains': [],
                                                u'starts_with': [u'דרעי']})

def test_personalities_suggest(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_suggest_response(client, u"personalities", u"dav",
                            200, expected_json={u'phonetic': [], u'contains': [],
                                                u'starts_with': [u'David, Ferdinand', u'Davydov, Karl Yulyevich']})

def test_movies_suggest(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_suggest_response(client, u"movies", u"liv",
                            200, expected_json={u'phonetic': [], u'contains': [],
                                                u'starts_with': [u'Living Moments In Jewish Spain (English Jews)']})

def test_search_result_without_slug(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert "slug_en" not in PHOTO_BRICKS
    assert "slug_he" not in PHOTO_BRICKS
    results = list(assert_search_results(client.get(u"/v1/search?q=Blocks&collection=photoUnits&sort=abc"), 1))
    # slug is generated on-the-fly if it doesn't exist in source data
    assert results[0]["slug_en"] == "image_building-blocks-for-housing-projects-israel-1950s"
    assert results[0]["slug_he"] == u"תמונה_לבנים-למפעל-בנייה-למגורים-ישראל-שנות-1960"
    assert "slug_en" not in PLACES_BOURGES
    assert "slug_he" not in PLACES_BOURGES
    results = list(assert_search_results(client.get(u"/v1/search?q=bourges&collection=places&sort=abc"), 1))
    # slug is generated on-the-fly if it doesn't exist in source data
    assert results[0]["slug_en"] == "place_bourges"
    assert results[0]["slug_he"] == u"מקום_בורג"

def test_search_missing_header_slug(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert PERSONALITY_WITH_MISSING_HE_HEADER_AND_SLUG["title_en"] == "Davydov, Karl Yulyevich"
    assert PERSONALITY_WITH_MISSING_HE_HEADER_AND_SLUG.get("title_he", "") == ""
    assert PERSONALITY_WITH_MISSING_HE_HEADER_AND_SLUG.get("slug_en") == 'luminary_davydov-karl-yulyevich'
    result = list(assert_search_results(client.get(u"/v1/search?q=karl+yulyevich"), 1))[0]
    assert result["title_en"] == 'Davydov, Karl Yulyevich'
    assert result["title_en_lc"] == 'davydov, karl yulyevich'
    assert result.get("title_he", "") == ""
    assert result.get("title_he_lc", "") == ""
    assert result["slug_en"] == "luminary_davydov-karl-yulyevich"

# TODO: re-enable once persons are in the new ES
def skip_test_search_persons(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert PERSON_EINSTEIN["name_lc"] == ["albert", "einstein"]
    # searching without persons support - doesn't return persons
    assert_no_results(client.get(u"/v1/search?q=einstein"))
    # search with persons support - return persons as part of general search
    result = list(assert_search_results(client.get(u"/v1/search?q=einstein&with_persons=1"), 1))[0]["_source"]
    assert result["name_lc"] == ["albert", "einstein"]
    # searching for collection persons - returns only persons results
    result = list(assert_search_results(client.get(u"/v1/search?q=einstein&collection=persons"), 1))[0]["_source"]
    assert result["name_lc"] == ["albert", "einstein"]
    assert result["person_id"] == "I686"

def assert_persons_no_results(client, qs):
    assert_no_results(client.get(u"/v1/search?collection=persons&{}".format(qs)))

def assert_error_message(client, url, expected_error_message):
    assert_error_response(client.get(url), 500, expected_error_message)

def assert_persons_error_messages(client, qses):
    for qs, expected_error_message in qses.items():
        assert_error_message(client, u"/v1/search?collection=persons&{}".format(qs), expected_error_message)

def assert_einstein_result(client, url):
    assert list(assert_search_results(client.get(url), 1))[0]["_source"]["name_lc"] == ["albert", "einstein"]

def assert_einstein_results(client, *args):
    for qs in args:
        assert_einstein_result(client, u"/v1/search?collection=persons&{}".format(qs))

# TODO: re-enable once persons are in the new ES
def skip_advanced_search_persons_death_year(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_persons_no_results(client, "yod=1910")
    assert_einstein_results(client, "yod=1955", "yod=1953&yod_t=pmyears&yod_v=2", "yod=1957&yod_t=pmyears&yod_v=2")
    assert_persons_error_messages(client, {"yod=foobar": "invalid value for yod (death_year): foobar",
                                           "yod=1957&yod_t=invalid": "invalid value for yod_t (death_year): invalid",
                                           "yod=1957&yod_t=pmyears&yod_v=foo": "invalid value for yod_v (death_year): foo"})

# TODO: re-enable once persons are in the new ES
def skip_advanced_search_persons_birth_year(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_persons_no_results(client, "yob=1910")
    assert_einstein_results(client, "yob=1879", "yob=1877&yob_t=pmyears&yob_v=2", "yob=1881&yob_t=pmyears&yob_v=2")
    assert_persons_error_messages(client, {"yob=foobar": "invalid value for yob (birth_year): foobar",
                                           "yob=1877&yob_t=invalid": "invalid value for yob_t (birth_year): invalid",
                                           "yob=1877&yob_t=pmyears&yob_v=foo": "invalid value for yob_v (birth_year): foo"})

# TODO: re-enable once persons are in the new ES
def skip_advanced_search_persons_marriage_years(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_persons_no_results(client, "yom=1910")
    assert_einstein_results(client, "yom=1923", "yom=1936&yom_t=pmyears&yom_v=2", "yom=1932&yom_t=pmyears&yom_v=2")
    assert_persons_error_messages(client, {"yom=foobar": "invalid value for yom (marriage_years): foobar",
                                           "yom=1877&yom_t=invalid": "invalid value for yom_t (marriage_years): invalid",
                                           "yom=1877&yom_t=pmyears&yom_v=foo": "invalid value for yom_v (marriage_years): foo"})

# TODO: re-enable once persons are in the new ES
def skip_advanced_search_persons_multiple_params(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_einstein_result(client, u"/v1/search?collection=persons&yob=1877&yob=1881&yob_t=pmyears&yob_v=2&yod=1955")
    assert_error_message(client, u"/v1/search?collection=persons&yod=123&&yob=1877&yob_t=pmyears&yob_v=foo", "invalid value for yob_v (birth_year): foo")
    assert_no_results(client.get(u"/v1/search?collection=persons&yob=1879&yod=1953"))

# TODO: re-enable once persons are in the new ES
def skip_advanced_search_persons_text_params(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    for param, attr, val, exact, starts, like in (("first", "first_name_lc", "albert", "albert", "alber", "alebrt"),
                                                  ("last", "last_name_lc", "einstein", "einstein", "einste", "einstien"),
                                                  ("pob", "BIRT_PLAC_lc", "ulm a.d., germany", "germany", "germ", "uml"),
                                                  ("pod", "DEAT_PLAC_lc", "princeton, u.s.a.", "princeton", "prince", "prniceton"),
                                                  ("pom", "MARR_PLAC_lc", ["uklaulaulaska", "agrogorog"], "uklaulaulaska", "agro", "agroogrog")):
        assert PERSON_EINSTEIN[attr] == val
        format_kwargs = {"param": param, "exact": exact, "starts": starts, "like": like}
        assert_no_results(client.get(u"/v1/search?collection=persons&{param}=foobarbaz".format(**format_kwargs)))
        assert_einstein_result(client, u"/v1/search?collection=persons&{param}={exact}".format(**format_kwargs))
        assert_no_results(client.get(u"/v1/search?collection=persons&{param}=foobarbaz&{param}_t=exact".format(**format_kwargs)))
        assert_einstein_result(client, u"/v1/search?collection=persons&{param}={exact}&{param}_t=exact".format(**format_kwargs))
        assert_no_results(client.get(u"/v1/search?collection=persons&{param}=foobarbaz&{param}_t=starts".format(**format_kwargs)))
        assert_einstein_result(client, u"/v1/search?collection=persons&{param}={starts}&{param}_t=starts".format(**format_kwargs))
        assert_no_results(client.get(u"/v1/search?collection=persons&{param}=foobarbaz&{param}_t=like".format(**format_kwargs)))
        assert_einstein_result(client, u"/v1/search?collection=persons&{param}={like}&{param}_t=like".format(**format_kwargs))
    # the place param does a search over multiple fields
    # TODO: integrate it into the above for loop - to test all the place_type options
    assert_search_hit_ids(client, u"q=moshe&with_persons=1&place=yaffo&place_type=exact", [None])


# TODO: re-enable once persons are in the new ES
def skip_persons_search_query_should_filter_on_all_text_fields(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    # Values exist
    assert_einstein_result(client, u"/v1/search?q=princeton&last=einstein&collection=persons")
    assert_einstein_result(client, u"/v1/search?q=princeton&last=einstein&with_persons=1")
    assert_einstein_result(client, u"/v1/search?q=princeton&with_persons=1")
    # Values don't exist
    assert_no_results(client.get(u"/v1/search?collection=persons&q=foobarbaz&last=einstein"))
    assert_no_results(client.get(u"/v1/search?q=princeton&last=einstein"))

# TODO: re-enable once persons are in the new ES
def skip_advanced_search_persons_other_params(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    for param, attr, val, invalid_val, no_results_val in (("sex", "gender", "M", "FOO", "F"),
                                                          ("treenum", "tree_num", "1196", "FOO", "1002"),
                                                          ("sex", "gender", "m", "FOO", "f"),):
        assert str(PERSON_EINSTEIN[attr]).lower() == val.lower()
        format_kwargs = {"param": param, "attr": attr, "val": val, "invalid_val": invalid_val, "no_results_val": no_results_val}
        assert_no_results(client.get(u"/v1/search?collection=persons&{param}={no_results_val}".format(**format_kwargs)))
        assert_error_message(client, u"/v1/search?collection=persons&{param}={invalid_val}".format(**format_kwargs),
                             "invalid value for {param} ({attr}): {invalid_val}".format(**format_kwargs))
        assert_einstein_result(client, u"/v1/search?collection=persons&{param}={val}".format(**format_kwargs))

# TODO: re-enable once persons are in the new ES
def skip_advanced_search_persons_exact_search_should_be_case_insensitive(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_einstein_results(client, "first=aLbErT&first_t=exact")

# TODO: re-enable once persons are in the new ES
def skip_test_should_return_places_before_people(client, app):
    given_local_elasticsearch_client_with_test_data(app, "test_search_test_should_return_places_before_people",
                                                    additional_index_docs={"persons": [PERSON_JAMES_GERMANY_MCDADE],
                                                                           "places": [PLACES_GERMANY]})
    results = assert_search_results(client.get(u"/v1/search?with_persons=1&q=germany"), 6)
    assert next(results)["title_en"] == "GERMANY"
