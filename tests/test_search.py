# -*- coding: utf-8 -*-
from common import *
from mocks import *


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
        assert hit["_type"] == "places"
        assert hit["_source"]["Header"]["En"] == "BOURGES"

def test_general_search(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_search_hit_ids(client, u"q=יהודים&sort=rel", [312757, 187521, 187559, 340727, 240790, 262366], ignore_order=True)
    assert_search_hit_ids(client, u"q=יהודים&sort=abc", [187559, 187521, 240790, 340727, 312757, 262366])
    assert_search_hit_ids(client, u"q=jews&sort=abc", [187521, 312757, 187559, 240790, 340727, 262367])

def test_places_search(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_search_hit_ids(client, u"q=יהודים&collection=places", [187521, 187559], ignore_order=True)
    assert_search_hit_ids(client, u"q=יהודים&collection=places&sort=abc", [187559, 187521])
    assert_search_hit_ids(client, u"q=jews&collection=places&sort=abc", [187521, 187559])

def test_images_search(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_search_hit_ids(client, u"q=Photo&collection=photoUnits&sort=year", [303772, 312757])
    assert_search_hit_ids(client, u"q=Photo&collection=photoUnits&sort=abc", [312757, 303772])
    assert_search_hit_ids(client, u"q=זוננפלד&collection=photoUnits&sort=abc", [303772, 312757])

def test_family_names_search(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_search_hit_ids(client, u"q=משפחה&collection=familyNames&sort=abc", [341018, 340727])

def test_personalities_search(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_search_hit_ids(client, u"q=Leipzig&collection=personalities&sort=abc", [240790, 240792])

def test_movies_search(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_search_hit_ids(client, u"q=jews&collection=movies&sort=abc", [262367])

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
                                                                "photoUnits": ['Boys Praying At The Synagogue Of Mosad Aliyah, Israel 1963'],
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
                                                u'starts_with': [u'Living Moments In Jewish Spain (English)']})

def test_search_result_without_slug(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)

    assert "Slug" not in PHOTO_BRICKS
    results = list(assert_search_results(client.get(u"/v1/search?q=Blocks&collection=photoUnits&sort=abc"), 1))
    # slug is generated on-the-fly if it doesn't exist in source data
    assert results[0]["_source"]["Slug"] == {
      "En": "image_building-blocks-for-housing-projects-israel-1950s",
      "He": u"תמונה_לבנים-למפעל-בנייה-למגורים-ישראל-שנות-1960"
    }

    assert "Slug" not in PLACES_BOURGES
    results = list(assert_search_results(client.get(u"/v1/search?q=bourges&collection=places&sort=abc"), 1))
    # slug is generated on-the-fly if it doesn't exist in source data
    assert results[0]["_source"]["Slug"] == {
      "En": "place_bourges",
      "He": u"מקום_בורג"
    }

def test_search_missing_header_slug(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    # update_es function sets item without header to _
    # so this is how an item with missing hebrew header will look like in ES
    assert PERSONALITY_WITH_MISSING_HE_HEADER_AND_SLUG["Header"] == {'En': 'Davydov, Karl Yulyevich', 'He': '_'}
    # these items will also no have a slug
    assert PERSONALITY_WITH_MISSING_HE_HEADER_AND_SLUG["Slug"] == {'En': 'luminary_davydov-karl-yulyevich'}
    # search for these items
    result = list(assert_search_results(client.get(u"/v1/search?q=karl+yulyevich"), 1))[0]["_source"]
    assert result["Header"] == {'En': 'Davydov, Karl Yulyevich', 'He': '_',
                                "En_lc": 'Davydov, Karl Yulyevich'.lower(), "He_lc": "_"}
    assert result["Slug"] == {'En': 'luminary_davydov-karl-yulyevich'}

def test_search_persons(client, app):
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

def test_advanced_search_persons_death_year(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_persons_no_results(client, "yod=1910")
    assert_einstein_results(client, "yod=1955", "yod=1953&yod_t=pmyears&yod_v=2", "yod=1957&yod_t=pmyears&yod_v=2")
    assert_persons_error_messages(client, {"yod=foobar": "invalid value for yod (death_year): foobar",
                                           "yod=1957&yod_t=invalid": "invalid value for yod_t (death_year): invalid",
                                           "yod=1957&yod_t=pmyears&yod_v=foo": "invalid value for yod_v (death_year): foo"})

def test_advanced_search_persons_birth_year(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_persons_no_results(client, "yob=1910")
    assert_einstein_results(client, "yob=1879", "yob=1877&yob_t=pmyears&yob_v=2", "yob=1881&yob_t=pmyears&yob_v=2")
    assert_persons_error_messages(client, {"yob=foobar": "invalid value for yob (birth_year): foobar",
                                           "yob=1877&yob_t=invalid": "invalid value for yob_t (birth_year): invalid",
                                           "yob=1877&yob_t=pmyears&yob_v=foo": "invalid value for yob_v (birth_year): foo"})

def test_advanced_search_persons_marriage_years(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_persons_no_results(client, "yom=1910")
    assert_einstein_results(client, "yom=1923", "yom=1936&yom_t=pmyears&yom_v=2", "yom=1932&yom_t=pmyears&yom_v=2")
    assert_persons_error_messages(client, {"yom=foobar": "invalid value for yom (marriage_years): foobar",
                                           "yom=1877&yom_t=invalid": "invalid value for yom_t (marriage_years): invalid",
                                           "yom=1877&yom_t=pmyears&yom_v=foo": "invalid value for yom_v (marriage_years): foo"})

def test_advanced_search_persons_multiple_params(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_einstein_result(client, u"/v1/search?collection=persons&yob=1877&yob=1881&yob_t=pmyears&yob_v=2&yod=1955")
    assert_error_message(client, u"/v1/search?collection=persons&yod=123&&yob=1877&yob_t=pmyears&yob_v=foo", "invalid value for yob_v (birth_year): foo")
    assert_no_results(client.get(u"/v1/search?collection=persons&yob=1879&yod=1953"))

def test_advanced_search_persons_text_params(client, app):
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


def test_persons_search_query_should_filter_on_all_text_fields(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    # Values exist
    assert_einstein_result(client, u"/v1/search?q=princeton&last=einstein&collection=persons")
    assert_einstein_result(client, u"/v1/search?q=princeton&last=einstein&with_persons=1")
    assert_einstein_result(client, u"/v1/search?q=princeton&with_persons=1")
    # Values don't exist
    assert_no_results(client.get(u"/v1/search?collection=persons&q=foobarbaz&last=einstein"))
    assert_no_results(client.get(u"/v1/search?q=princeton&last=einstein"))

def test_advanced_search_persons_other_params(client, app):
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

def test_advanced_search_persons_exact_search_should_be_case_insensitive(client, app):
    given_local_elasticsearch_client_with_test_data(app, __file__)
    assert_einstein_results(client, "first=aLbErT&first_t=exact")

def test_should_return_places_before_people(client, app):
    given_local_elasticsearch_client_with_test_data(app, "test_search_test_should_return_places_before_people",
                                                    additional_index_docs={"persons": [PERSON_JAMES_GERMANY_MCDADE],
                                                                           "places": [PLACES_GERMANY]})
    results = assert_search_results(client.get(u"/v1/search?with_persons=1&q=germany"), 6)
    assert next(results)["_source"]["Header"]["En"] == "GERMANY"

