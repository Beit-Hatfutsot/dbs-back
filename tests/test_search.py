# -*- coding: utf-8 -*-
from elasticsearch import Elasticsearch
from scripts.elasticsearch_create_index import ElasticsearchCreateIndexCommand
from copy import deepcopy
import os


### environment setup functions


def given_invalid_elasticsearch_client(app):
    app.es = Elasticsearch("192.0.2.0", timeout=0.000000001)

def index_doc(app, collection, doc):
    doc = deepcopy(doc)
    doc.get("Header", {}).setdefault("He_lc", doc.get("Header", {}).get("He", "").lower())
    doc.get("Header", {}).setdefault("En_lc", doc.get("Header", {}).get("En", "").lower())
    app.es.index(app.es_data_db_index_name, collection, doc)

def index_docs(app, collections, reuse_db=False):
    if not reuse_db or not app.es.indices.exists(app.es_data_db_index_name):
        ElasticsearchCreateIndexCommand().create_es_index(es=app.es, es_index_name=app.es_data_db_index_name, delete_existing=True)
        for collection, docs in collections.items():
            for doc in docs:
                index_doc(app, collection, doc)
        app.es.indices.refresh(app.es_data_db_index_name)

def given_local_elasticsearch_client_with_test_data(app):
    app.es = Elasticsearch("localhost")
    app.es_data_db_index_name = "bh_dbs_back_pytest"
    reuse_db = os.environ.get("REUSE_DB", "") == "1"
    index_docs(app, {
        "places": [PLACES_BOURGES, PLACES_BOZZOLO],
        "photoUnits": [PHOTO_BRICKS, PHOTOS_BOYS_PRAYING],
        "familyNames": [FAMILY_NAMES_DERI, FAMILY_NAMES_EDREHY],
        "personalities": [PERSONALITIES_FERDINAND, PERSONALITIES_DAVIDOV],
        "movies": [MOVIES_MIDAGES, MOVIES_SPAIN]
    }, reuse_db)

### custom assertions


def assert_error_response(res, expected_status_code, expected_error):
    assert res.status_code == expected_status_code
    assert res.data == """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<title>{status_code} {status_msg}</title>
<h1>{status_msg}</h1>
<p>{error}</p>
""".format(error=expected_error, status_code=expected_status_code, status_msg="Bad Request" if expected_status_code == 400 else "Internal Server Error")

def assert_common_elasticsearch_search_results(res):
    assert res.status_code == 200
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

### utility functions


def dump_res(res):
    print(res.status_code, res.data)


### tests


def test_search_without_parameters_should_return_error(client):
    assert_error_response(client.get('/v1/search'), 400, "You must specify a search query")

def test_search_without_elasticsearch_should_return_error(client, app):
    given_invalid_elasticsearch_client(app)
    assert_error_response(client.get('/v1/search?q=test'), 500, "Sorry, the search cluster appears to be down")

def test_searching_for_nonexistant_term_should_return_no_results(client, app):
    given_local_elasticsearch_client_with_test_data(app)
    assert_no_results(client.get('/v1/search?q=testfoobarbazbaxINVALID'))

def test_general_search_single_result(client, app):
    given_local_elasticsearch_client_with_test_data(app)
    # test data contains exactly 1 match for "BOURGES"
    res = client.get("/v1/search?q=BOURGES")
    for hit in assert_search_results(res, 1):
        assert hit["_type"] == "places"
        assert hit["_source"]["Header"]["En"] == "BOURGES"

def test_general_search(client, app):
    given_local_elasticsearch_client_with_test_data(app)
    assert_search_hit_ids(client, u"q=יהודים&sort=rel", [312757, 187521, 187559, 340727, 240790, 262366], ignore_order=True)
    # sort=abc - query is in hebrew, ordered on the hebrew headers
    # 187559 = בוצולו
    # 187521 = בורג
    # 240790 = דוד, פרדיננד
    # 340727 = דרעי
    # 312757 = נערים יהודים מתפללים בבית הכנסת במוסד עליה, ישראל 1960-1950s
    # 262366 = רגעים עם יהודי ספרד (אנגלית)
    assert_search_hit_ids(client, u"q=יהודים&sort=abc", [187559, 187521, 240790, 340727, 312757, 262366])
    # sort=abc - query is in english, ordered on the english headers
    # 187521 = BOURGES
    # 312757 = Boys praying at the synagogue of Mosad Aliyah, Israel 1963
    # 187559 = BOZZOLO
    # 240790 = David, Ferdinand
    # 340727 = DEREI
    # 262367 = Jewish Communities in the Middle Ages: Babylonia; Spain; Ashkenaz (Hebrew)
    assert_search_hit_ids(client, u"q=jews&sort=abc", [187521, 312757, 187559, 240790, 340727, 262367])

def test_places_search(client, app):
    given_local_elasticsearch_client_with_test_data(app)
    assert_search_hit_ids(client, u"q=יהודים&collection=places", [187521, 187559], ignore_order=True)
    # sort=abc - query is in hebrew, ordered on the hebrew headers
    # 187559 = בוצולו
    # 187521 = בורג
    assert_search_hit_ids(client, u"q=יהודים&collection=places&sort=abc", [187559, 187521])
    # sort=abc - query is in english, ordered on the english headers
    # 187521 = BOURGES
    # 187559 = BOZZOLO
    assert_search_hit_ids(client, u"q=jews&collection=places&sort=abc", [187521, 187559])

def test_images_search(client, app):
    given_local_elasticsearch_client_with_test_data(app)
    # 303772 = Building Blocks for Housing Projects, Israel 1950s
    # 312757 = Boys praying at the synagogue of Mosad Aliyah, Israel 1963
    assert_search_hit_ids(client, u"q=Photo&collection=photoUnits&sort=year", [303772, 312757])
    # alphabetical english
    # 312757 = Boys praying at the synagogue of Mosad Aliyah, Israel 1963
    # 303772 = Building Blocks for Housing Projects, Israel 1950s
    assert_search_hit_ids(client, u"q=Photo&collection=photoUnits&sort=abc", [312757, 303772])
    # alphabetical hebrew
    # 393772 - לבנים למפעל בנייה למגורים, ישראל שנות 1960
    # 312757 = נערים יהודים מתפללים בבית הכנסת במוסד עליה, ישראל 1960-1950
    assert_search_hit_ids(client, u"q=זוננפלד&collection=photoUnits&sort=abc", [303772, 312757])

def test_family_names_search(client, app):
    given_local_elasticsearch_client_with_test_data(app)
    # 341018 = אדרהי
    # 340727 = דרעי
    assert_search_hit_ids(client, u"q=משפחה&collection=familyNames&sort=abc", [341018, 340727])

def test_personalities_search(client, app):
    given_local_elasticsearch_client_with_test_data(app)
    # 240790 = David, Ferdinand
    # 240792 = Davydov, Karl Yulyevich
    assert_search_hit_ids(client, u"q=Leipzig&collection=personalities&sort=abc", [240790, 240792])

def test_movies_search(client, app):
    given_local_elasticsearch_client_with_test_data(app)
    # 262367 = Jewish Communities in the Middle Ages: Babylonia; Spain; Ashkenaz (Hebrew)
    assert_search_hit_ids(client, u"q=jews&collection=movies&sort=abc", [262367])

def test_invalid_suggest(client, app):
    given_invalid_elasticsearch_client(app)
    assert_suggest_response(client, u"places", u"mos",
                            500, expected_error_message="unexpected exception getting completion data: ConnectionError")

def test_general_suggest(client, app):
    given_local_elasticsearch_client_with_test_data(app)
    assert_suggest_response(client, u"*", u"bo",
                            200, expected_json={"phonetic": {"places": [], "photoUnits": [], "familyNames": [], "personalities": [], "movies": [], "persons": []},
                                                "contains": {},
                                                "starts_with": {"places": [u'Bourges', u'Bozzolo'],
                                                                               # notice that suggest captilizes all letters
                                                                "photoUnits": ['Boys Praying At The Synagogue Of Mosad Aliyah, Israel 1963'],
                                                                "familyNames": [], "personalities": [], "movies": [], "persons": []}})

def test_places_suggest(client, app):
    given_local_elasticsearch_client_with_test_data(app)
    assert_suggest_response(client, u"places", u"bo",
                            200, expected_json={"phonetic": [], "contains": [], "starts_with": ["Bourges", "Bozzolo"]})

def test_images_suggest(client, app):
    given_local_elasticsearch_client_with_test_data(app)
    assert_suggest_response(client, u"photoUnits", u"נער",
                            200, expected_json={u'phonetic': [], u'contains': [],
                                                u'starts_with': [u'נערים יהודים מתפללים בבית הכנסת במוסד עליה, ישראל 1960-1950']})

def test_family_names_suggest(client, app):
    given_local_elasticsearch_client_with_test_data(app)
    assert_suggest_response(client, u"familyNames", u"דר",
                            200, expected_json={u'phonetic': [], u'contains': [],
                                                u'starts_with': [u'דרעי']})

def test_personalities_suggest(client, app):
    given_local_elasticsearch_client_with_test_data(app)
    assert_suggest_response(client, u"personalities", u"dav",
                            200, expected_json={u'phonetic': [], u'contains': [],
                                                u'starts_with': [u'David, Ferdinand', u'Davydov, Karl Yulyevich']})

def test_movies_suggest(client, app):
    given_local_elasticsearch_client_with_test_data(app)
    assert_suggest_response(client, u"movies", u"liv",
                            200, expected_json={u'phonetic': [], u'contains': [],
                                                u'starts_with': [u'Living Moments In Jewish Spain (English)']})

def test_search_result_without_slug(client, app):
    given_local_elasticsearch_client_with_test_data(app)

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
    given_local_elasticsearch_client_with_test_data(app)
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


### constants


PLACES_BOURGES = {
    "LocationInMuseum": None,
    "Pictures": [
      {
        "PictureId": "445411A5-F570-4C39-A9FC-1638A38F0B9D",
        "IsPreview": "1"
      }
    ],
    "PictureUnitsIds": "139836,",
    "related": [
      "image_the-last-supper-fresco-south-austria-15th-century",
      "familyname_albebas",
      "luminary_mendelssohn-abraham",
      "place_havre-le",
      "image_the-judenherberge-in-berlin-engraving-18th-century",
      "familyname_attawil"
    ],
    "UpdateDate": "2015-08-06T09:20:00",
    "OldUnitId": "HB000398.HTM-EB000174.HTM",
    "dm_soundex": [
      "795400"
    ],
    "Id": 187521,
    "UpdateUser": "simona",
    "PrevPictureFileNames": "139836.jpg,",
    "PrevPicturePaths": "Photos\\445411a5-f570-4c39-a9fc-1638a38f0b9d.jpg,",
    "PlaceTypeCode": 2,
    "TS": "00000000003f9726",
    "PlaceTypeDesc": {
      "En": "Town",
      "He": u"עיירה"
    },
    "UnitType": 5,
    "UnitTypeDesc": "Place",
    "EditorRemarks": "hasavot from Places ",
    "DisplayStatusDesc": "Museum only",
    "RightsDesc": "Full",
    "Bibiliography": {
      "En": "ENCYCLOPAEDIA JUDAICA",
      "He": u"אנציקלופדיה יודאיקה"
    },
    "UnitText1": {
      "En": "BOURGES\r\n\r\nCAPITAL OF THE DEPARTMENT OF CHER, CENTRAL FRANCE.\r\n\r\nIN 570 A JEW, SIGERICUS, WAS BAPTIZED IN BOURGES, WHILE AT ABOUT THE SAME TIME A JEW PRACTICING MEDICINE THERE TREATED A CLERIC. SULPICIUS, BISHOP OF BOURGES, 624--647, ATTEMPTED TO CONVERT THE JEWS IN BOURGES TO CHRISTIANITY, AND EXPELLED ANY WHO RESISTED HIS MISSIONARY ACTIVITIES. IN 1020 A JEWISH QUARTER IS MENTIONED TO THE SOUTH OF THE CITY. ABOUT 1200 A BAPTIZED JEW OF BOURGES NAMED GUILLAUME, WHO HAD BECOME A DEACON, COMPOSED AN ANTI-JEWISH TREATISE, BELLUM DOMINI ADVERSUS IUDAEOS. AROUND 1250 THE POPE REQUESTED THE ARCHBISHOP OF BOURGES TO SECURE A LIVELIHOOD FOR THE BAPTIZED JEW, JEAN. BETWEEN THE END OF THE 13TH CENTURY AND 1305 MANY JEWISH NAMES APPEAR ON THE MUNICIPAL TAX ROLLS AND BAILIFF COURT RECORDS. A BUILDING AT 79 RUE DES JUIFS IS BELIEVED TO HAVE BEEN USED AS A SYNAGOGUE IN THE MIDDLE AGES. THE COMMUNITY CEASED TO EXIST AFTER THE JEWS WERE EXPELLED FROM FRANCE IN THE 14TH CENTURY. DURING WORLD WAR II, ESPECIALLY AFTER JUNE 1940, HUNDREDS OF JEWISH REFUGEES WERE\r\nTEMPORARILY SETTLED IN BOURGES.",
      "He": u"בורג'\r\n\r\nעיר במרכז צרפת.\r\n\r\nידיעות ראשונות על יישוב יהודים במקום מקורן במאה ה-6 . בתחילת המאה ה-11 נזכר רובע יהודי בדרום העיר.\r\n\r\nיהודי מומר, בן בורג', פירסם ב- 1200 לערך חיבור על \"מלחמת ישו ביהודים\".\r\n\r\nבתחילת המאה ה-14 מופיעים שמות יהודיים רבים ברשימת משלמי המסים העירוניים.\r\n\r\nהקהילה חדלה להתקיים עם גירוש צרפת (1394).\r\n\r\nבימי מלחמת העולם השנייה, אחרי יוני 1940 , ישבו בבורג', ישיבה זמנית, מאות פליטים יהודים."
    },
    "UnitText2": {
      "En": None,
      "He": None
    },
    "UnitPlaces": [],
    "UnitStatus": 3,
    "UnitDisplayStatus": 2,
    "RightsCode": 1,
    "UnitId": 71236,
    "IsValueUnit": True,
    "StatusDesc": "Completed",
    "PlaceParentTypeCodeDesc": {
      "En": "City"
    },
    "PlaceParentId": 70345,
    "UserLexicon": None,
    "Attachments": [],
    "Header": {
      "En": "BOURGES",
      "He": u"בורג'",
      "En_lc": "bourges",
      "He_lc": u"בורג'"
    },
    "ForPreview": False
}

PLACES_BOZZOLO = {
    "LocationInMuseum": None,
    "Pictures": [],
    "PictureUnitsIds": None,
    "related": [
      "image_-rabbi-loew-and-the-golem-ink-on-paper-prague-1913-1914",
      "familyname_goinzburg",
      "luminary_cherkassky-shura",
      "place_kazimierz-dolny",
      "image_the-synagogue-building-in-dzierzniow-silesia-poland-2010",
      "familyname_emden"
    ],
    "UpdateDate": "2015-07-02T14:44:00",
    "OldUnitId": "HB000419.HTM-EB000175.HTM",
    "dm_soundex": [
      "748000"
    ],
    "Id": 187559,
    "UpdateUser": "archive1",
    "PrevPictureFileNames": None,
    "PrevPicturePaths": None,
    "PlaceTypeCode": 1,
    "TS": "00000000003c85f1",
    "PlaceTypeDesc": {
      "En": "City",
      "He": "עיר"
    },
    "UnitType": 5,
    "UnitTypeDesc": "Place",
    "EditorRemarks": "hasavot from Places ",
    "DisplayStatusDesc": "Museum only",
    "RightsDesc": "Full",
    "Bibiliography": {
      "En": "MILANO, ITALIA, INDEX.\n\nEncyclopedia Judaica (2007)",
      "He": "אנציקלופדיה יודאיקה (2007)"
    },
    "UnitText1": {
      "En": "Bozzolo\n\nTown in Lombardy, northern Italy. \n\nJewish settlement in Bozzolo began in 1522 with the arrival of Jewish loan bankers who had close connections with the Jews in the nearby Duchy of Mantua. During the 17th and the first half of the 18th centuries, a small but prosperous community existed in Bozzolo, mainly occupied in banking, commerce, and farming of the customs dues. By the first half of the 17th century, the influential Finzi family was able to build a rich network of commercial, economic, and cultural activity, such as the production, manufacture and trade silk. They founded a company that set up all the mulberry plantations in multiple cities. \n\nAt the end 18th century, under Austrian rule, the economic and commercial importance of Bozzolo progressively diminished and the Jews began to leave and moved to Milan. In the 1820's 135 Jews lived in Bozzolo and a new cemetery was opened, at the edge of town. There is also evidence of a Jewish cemetery with three tombstones from the 18th century which had been converted into a private vegetable garden.\n\nThere were no Jews left in Bozzolo by the beginning of the 20th century",
      "He": "בוצולו\r\n\r\nעיר בלומבארדיה, צפון איטליה.\r\n\r\nתחילת היישוב היהודי בבוצולו במחצית הראשונה של המאה ה-16. קהילה קטנה ועשירה הייתה שם במאה ה-17 ועד אמצע ה-18. רוב היהודים היו בנקאים, סוחרים ומוכסים. בשנת 1746 עברה העיר לשליטת אוסטריה, וחשיבותה הכלכלית פחתה. היהודים עזבו.\r\n\r\nבתחילת המאה ה-20 לא ישבו יהודים בבוצולו."
    },
    "UnitText2": {
      "En": None,
      "He": None
    },
    "UnitPlaces": [],
    "UnitStatus": 3,
    "UnitDisplayStatus": 2,
    "RightsCode": 1,
    "UnitId": 71255,
    "IsValueUnit": True,
    "StatusDesc": "Completed",
    "PlaceParentTypeCodeDesc": {
      "En": None
    },
    "PlaceParentId": None,
    "UserLexicon": None,
    "Attachments": [],
    "Slug": {
      "En": "place_bozzolo",
      "He": "מקום_בוצולו"
    },
    "Header": {
      "En": "BOZZOLO",
      "He": u"בוצולו",
      "En_lc": "bozzolo",
      "He_lc": u"בוצולו"
    },
    "ForPreview": False
}

PHOTOS_BOYS_PRAYING = {
    "NegativeNumbers": "|||||",
    "IsLandscape": "1|0|0|1|1|",
    "PrevPictureUnitsId": "140068",
    "ExhibitionIsPreview": None,
    "LocationInMuseum": None,
    "Pictures": [
      {
        "IsLandscape": "1",
        "ForDisplay": "1",
        "ToScan": "1",
        "IsPreview": "0",
        "PictureTypeDesc": {
          "En": "Picture",
          "He": "תצלום - ש/ל"
        },
        "PicId": "208845",
        "PictureId": "30E58D58-DF6B-4D79-91EC-057B72B1F962",
        "LocationCode": "SON.31/123"
      },
      {
        "IsLandscape": "0",
        "ForDisplay": "1",
        "ToScan": "1",
        "IsPreview": "0",
        "PictureTypeDesc": {
          "En": "Picture",
          "He": "תצלום - ש/ל"
        },
        "PicId": "211159",
        "PictureId": "85B1F924-DD46-4D7B-BBD4-357D5247AA97",
        "LocationCode": "SON.30/49"
      },
      {
        "IsLandscape": "0",
        "ForDisplay": "1",
        "ToScan": "1",
        "IsPreview": "0",
        "PictureTypeDesc": {
          "En": "Picture",
          "He": "תצלום - ש/ל"
        },
        "PicId": "211158",
        "PictureId": "75A1D6C2-24CA-435F-953D-4818F594BD66",
        "LocationCode": "SON.72/87"
      },
      {
        "IsLandscape": "1",
        "ForDisplay": "1",
        "ToScan": "1",
        "IsPreview": "0",
        "PictureTypeDesc": {
          "En": "Picture",
          "He": "תצלום - ש/ל"
        },
        "PicId": "211160",
        "PictureId": "4A26D392-400B-44E9-8C82-721B376943C8",
        "LocationCode": "SON.30/50"
      },
      {
        "IsLandscape": "1",
        "ForDisplay": "1",
        "ToScan": "1",
        "IsPreview": "1",
        "PictureTypeDesc": {
          "En": "Picture",
          "He": "תצלום - ש/ל"
        },
        "PicId": "208844",
        "PictureId": "ED6D44A9-3C49-41E0-8D75-9A87DDCDF3A7",
        "LocationCode": "SON.31/124"
      }
    ],
    "ToScan": "1|1|1|1|1|",
    "PeriodDateTypeDesc": {
      "En": "Year|",
      "He": "שנים|"
    },
    "related": [
      "image_small-boys-learning-torah-in-a-heder-jerusalem-israel-1950s",
      "image_old-men-during-talmud-class-in-the-synagogue-in-bakka-jerusalm-israel-1953",
      "image_lighting-candles-at-the-grave-of-rabbi-meir-baal-hanes-tiberias-israel-1960s",
      "image_boys-praying-at-the-synagogue-of-mosad-aliyah-israel-1963"
    ],
    "ExhibitionId": None,
    "UpdateDate": "2012-10-29T11:47:00",
    "OldPictureNumbers": "|||||",
    "OldUnitId": None,
    "Id": 312757,
    "UpdateUser": "Zippi",
    "PictureLocations": "Box 31 (30x40)|Box 30 (30x40)|Box 72 (30x40)|Box 30 (30x40)|Box 31 (30x40)|",
    "UnitDisplayStatus": 3,
    "UnitPeriod": [
      {
        "PeriodDateTypeDesc": {
          "En": "Year",
          "He": "שנים"
        },
        "PeriodEndDate": "19639999",
        "PeriodNum": "1",
        "PeriodTypeDesc": {
          "En": "Period",
          "He": "תקופת צילום"
        },
        "PeriodDesc": {
          "En": "1963",
          "He": "1963"
        },
        "PeriodStartDate": "19630000",
        "PeriodTypeCode": "4",
        "PeriodDateTypeCode": "1"
      }
    ],
    "PrevPicturePaths": "Photos\\ed6d44a9-3c49-41e0-8d75-9a87ddcdf3a7.jpg|",
    "TS": "\u0000\u0000\u0000\u0000\u0000\u0002$1",
    "PrevPictureId": "ED6D44A9-3C49-41E0-8D75-9A87DDCDF3A7",
    "PictureSources": "122328|",
    "UnitPersonalities": [
      {
        "OrderBy": "1"
      }
    ],
    "UnitTypeDesc": "Photo",
    "Slug": {
      "En": "image_boys-praying-at-the-synagogue-of-mosad-aliyah-israel-1963",
      "He": "תמונה_נערים-מתפללים-בבית-הכנסת-במוסד-עליה-ישראל-1960-1950"
    },
    "PeriodStartDate": "19630000|",
    "PIctureReceivedIds": "122329|",
    "PeriodDateTypeCode": "1|",
    "RightsDesc": "Full",
    "OrderBy": "1|",
    "Bibiliography": {
      "En": None,
      "He": None
    },
    "UnitText1": {
      "En": "Boys (jews) praying at the synagogue of Mosad Aliyah, \nIsrael 1963.\nPhoto: Leni Sonnenfeld\nBeth Hatefutsoth Photo Archive, Sonnenfeld collection)",
      "He": "נערים מתפללים בבית הכנסת במוסד עליה, \nישראל 1963.\nצילום:לני זוננפלד\n(בית התפוצות, ארכיון התצלומים, אוסף זוננפלד)\t"
    },
    "UnitText2": {
      "En": None,
      "He": None
    },
    "UnitPlaces": [
      {
        "PlaceIds": "113047"
      }
    ],
    "main_image_url": "https://storage.googleapis.com/bhs-flat-pics/ED6D44A9-3C49-41E0-8D75-9A87DDCDF3A7.jpg",
    "UnitStatus": 3,
    "PersonalityIds": "49547|",
    "PeriodNum": "1|",
    "PeriodDesc": {
      "En": "1963|",
      "He": "1963|"
    },
    "PrevPictureFileNames": "31-124.jpg",
    "RightsCode": 1,
    "PeriodTypeCode": "4|",
    "UnitId": 140068,
    "PicId": "208845|211159|211158|211160|208844|",
    "IsValueUnit": True,
    "StatusDesc": "Completed",
    "PreviewPics": [
      {
        "PrevPictureId": "ED6D44A9-3C49-41E0-8D75-9A87DDCDF3A"
      }
    ],
    "PicturePaths": "Photos\\30e58d58-df6b-4d79-91ec-057b72b1f962.jpgPhotos\\85b1f924-dd46-4d7b-bbd4-357d5247aa97.jpgPhotos\\75a1d6c2-24ca-435f-953d-4818f594bd66.jpgPhotos\\4a26d392-400b-44e9-8c82-721b376943c8.jpgPhotos\\ed6d44a9-3c49-41e0-8d75-9a87ddcdf3a7.jpg",
    "Attachments": [],
    "UserLexicon": "49344|49358|49370|49371|56153|57342|",
    "PictureTypeCodes": "1|1|1|1|1|",
    "EditorRemarks": "",
    "PictureFileNames": "31-123.jpg|30-49.jpg|72-87.jpg|30-50.jpg|31-124.jpg|",
    "Exhibitions": [],
    "ForDisplay": "1|1|1|1|1|",
    "DisplayStatusDesc": "Museum and Internet",
    "PeriodEndDate": "19639999|",
    "UnitType": 1,
    "PictureTypeDesc": {
      "En": "Picture|Picture|Picture|Picture|Picture|",
      "He": "תצלום - ש/ל|תצלום - ש/ל|תצלום - ש/ל|תצלום - ש/ל|תצלום - ש/ל|"
    },
    "thumbnail": {
      "path": "Photos/ed6d44a9-3c49-41e0-8d75-9a87ddcdf3a7.jpg",
      "data": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a%0AHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIy%0AMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCADMAQQDASIA%0AAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA%0AAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3%0AODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm%0Ap6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4%2BTl5ufo6erx8vP09fb3%2BPn6/8QAHwEA%0AAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSEx%0ABhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElK%0AU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3%0AuLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3%2BPn6/9oADAMBAAIRAxEAPwDzksRR%0Av4pzLkVERipES7qXdUYpaAHFqRW%2BammkH3qAJw1O3n1qEU6gCQue9Rs9JTG6UAPjc84NWIpOOveq%0AidDU8Q4oYy8knHWoJZPm60gyKik6mkBpeHX3a9bDP8VW2Yt4guwOMK5rP8OE/wDCQWmOTvrQIZ/E%0At9gYwsmR%2BFJ7gVbJv9FPPVjTJD1p1iP9EyT/ABNUcwwM0wGyt8i8UkT8U2biNc0sI%2BWgB08pAAzV%0AXzT5o571NcY4qqo/fr9RQB7JaEjwJqJPUQyf%2BgCvO5WcRDB7V6HGpTwFqWe8Un/oIrzyYjyhz2rO%0APUplESN5nXtVeaVvO61KuPMP0qvLzKfrWhIsjttzmqpkYyDnvViYfuxVVAWnQDuwFAHrCDb8Mb0/%0A3mP/AKEtebTnaxK5H0NenXCGL4bTK3Uvj/x8V5lcj71RDqVIrSSvtyWP50i3cqLxg/WidcRioGHy%0AitCCU6lIDzEv50VUbrRQBabp0qM1M2aiIpAIBzRS4opgNamr96nEU1eGoAkHWnGmA0%2BgAxTHp5pj%0A9KAEj6GrEXtVaM9atwDIoYyVQSDgVBIDk1eRMCoZo%2BScUgE0af7Lq8Mx6KavWUhuNau5ezRuayok%0A/fCtfQ4i99cY7QMf0oYEFqcWpGf4j/Oo5T8vBpsT4jI/2jTJG4oAJGyop0R4qEtnipY87aAEnqtH%0A/wAfKf7w/nVmbkVVBKzqfQ5oA9muDs8A6iT/AM8n/oK82kYGEZ64raPjGN/Cl3pLwP58uVWQEbcE%0Ag/0rnXbKioirFNkK/wCsbmq7nMp9c1KG/eHmoSf3hqyRZc%2BXiq0IJuox/tj%2BdWZTlBzUNrj%2B0IM/%0A89F/nTA9d1MCP4egEfekX/0OvMbvG416b4ikUeAbcrjDSJ/MmvMLlgeRWcCpFW4%2B4PrUTD93Us7b%0AkH1qN8eXWhBVbrRQRzRQBbOTxSBGJwBTy3JIp0ZG7JIAxSGM8pvSkMbehq0Hj/vr%2BdP%2BU9GH50AZ%0A7KfSowPnrTIBHaqcwxKKYiPFOp8a5kUEcZq4YUP8IpAUM0x60Tbx4%2B7TWtI8dMfjTAzo%2BprQtUDD%0ApVREAdh6Gpp2CW6jMgJPVemPrSYy5Ndw2yAE7n/uiqR1IOcNFgexqj/nNKVKn5gRTsI0oAGlVhyp%0A6Gug8NRhr%2B946Wzfyrk7SURTpn7pODXa%2BFYwb2/B7W7VMtho5f7rMP8AaNMkPBq99imkVpETK7jz%0A%2BNVprWdRzEaYFZamXO3INRIpOeMEVMqtt%2B6fyoEMckiq%2BT5lTvn0qAZ8ygZOp%2BarBc7elVhxT9xx%0AjNADS37wmgn5%2BKjJ%2Ben/AMfSgQORtqsDtmB9Dmp3PtVb/lpTA2/7c1C4sI9PmuGa1jbeiHsfr%2BJq%0AlM2agRuaWRqVgEfoKRx8tJnNKxyKYFY9aKD1ooAsHqa7r4ZPaG/v1uBEZDEuzeueMnOP0rh3HJrt%0AfhiwXW7zJHNv3/3qiXwlLc9LNppMn37Wzb/ehX/Com0Tw/McNptgx/64r/hV4MG6EVNGoznAzWFz%0AU4CTwj4fmi1IwwyCS3B%2BYOQqkjIxXBeIbC203W5La1JMSxRty2eSuTXqtjDsn8QxnBU447cpXnHj%0Ae3W38TuiKFBtYmwPpW0XqZtaFbwtp0Gr%2BJLSyud/kyFt2w4JwpPX8K9NPw40Jvutep9LjP8AMV55%0A4DH/ABWunZ/vP/6Aa9zA4qajaY4pNHnmq/DuyghWS21K4hG7DGbDjn8BWJfeBby2uYIo79XEgckt%0AHjG0Zr0XxQjNpO5CQVlQ/wDjwpNSg8%2B6tMsy/LIPlOOq0KTBpHgsYIyx6k81sjRLm%2B8OS38MkZig%0AlAdN3zc4GcfiKytm1PoxH616T4D0eG/8L3zSZLzu8IBPA%2BUYOPqa0k7akJXPORpzomY2Uv6EZqs1%0AlcROqyIwLdM963L%2By1DRNQMF7EY3U/dTBz6HPoavblkhQuqk9RkdDTuFjnLjS2htzIT%2B8UbmTviu%0A18JwoL2/COHU2gYMDkcqDWZcDzkKHB%2BUjmur%2BF62X2K%2BjKr9tSTDg/8APPtj2z1qZPQaWpxsOrWt%0AnEYJd%2B8MScDjk1FLrNk2fmP/AHzXo9ho9kur61C1rE6CVduUBwCueK5XxHotlDqaBbaNVMEjYAxy%0ABxQmrhZnFiQM7svQnIrWs7iKK1US8ZJwSDg1jKpEaH2r2LRI4ovB%2BkrParMrRbtwAIHU805OwLU8%0A8a5snH34zWbeNAZkMW33xXrGq6ZY3fhhrj7JAGKBgFjA715r4itI7bXp44oViAjU7QMdqUXcGrFS%0AzSOSUrIBjHer5srRhwB%2BdQaJbW9280c6bidoUkdOauaz4djskLxSNt9jTEZN/axQFSnc%2BtFrbpcy%0A7CccdRTL62WC/aNC21UBwxzzUMYkkb91IUbIGR7nFMC/JpC9pDWVcWwt7rZuz3rW1XS9S0uISNeb%0AwcdBWIXkkctI2WHGaEBctbNrhGZGAwcc06bTpUUtkHFJp6XkzvHasowNxDUy6u76CVoZtuR1xQBW%0AUZwO9WHtJgPuVWUtuXb97PAq5LeXUPEkIH1piM90ZHIYYNFOlmaZ95GD6UUAWXGMjOa7H4aR7tfu%0ASQCBbk/%2BPCuOf7xFdr8MuNduxn/l26f8CFRL4WVHc9VWNePlFSKgU5wKatSCuc2MC0snj1HWd8RE%0AMoXaT0b5TmvOPiFCsfioBRgGyjP8xXqEMkr6vqVu8jGJI0KL6bgc/wAq84%2BIMOPFEfJObBDz7Eit%0AYbmctjK8Df8AI56Zn/no3/oJr3QdBXhfg5dvjDS%2Bf%2BW39DXuaniipuENjL8RRySaS/l5LBlOAOvz%0ACpLmHzrq0O4jbvzjv8tSatNLb6dJLCQHXBGRnuKkkQtPCQSMZ/lUFHz7Ku1WHYSv/M16t8ND/wAU%0AvJ/18v8AyWvL7lcRHPXzpBn/AIEa9H8BTvaeCLy4X5jFO7BfoFraexnHcf418M32ozS6lbbZgI0T%0AyFUl%2BCckdj1zXE2wDoVwcgkEYx0r13SdSl1LSvthiEeS2FPcDvXnvj3V4V1CCC2tlW7aFGmkXp8w%0AyFx689fepi3sNrqYYffK237kY%2BZqo2eq3OkXEd1ZymK5yz%2BYOQQT0x347VKoex8P7CMzSn5D/dBP%0Af9apWtpLqF3HCqndIwVUXsPp9K0JPWfDEk32QT3kjSXd4gllkbjLY4GPpisrxRGW1BMcEWkx5%2Blb%0AcazgJDBEFiUYQt1wOOlcx4k0mWe5luWupo9sEmVBIHTt7Gs1uU9jgMfuIvpXtOhPJH4N0sGAODbg%0AHB6DB5rxjH%2Bjxf7te56Pug8M6WFj3oLVN2e3y5pz2CIyeMN4VURjrEuAfqK8z8XxsfFd4GUArEnT%0A6V6zOyy6OrIioGCEL2HI4ry7xqMeL9R3f88o8EfSlDccij4U2faZAykksmCPrXQ%2BJIgYDtOQSOPx%0ArF8IqWeUBeTImG9Otb2rWz%2BdEPN3gyoMMP8AaFU9yVscdr0Z/t64Rl2lY14/Cq2lKHlx6yxj/wAe%0ArX8TR58X6krADaoHH0rK0u3kknjKSbf3yLnHQ561XQXU6/xrCI9OBH99RXnYH3z/ALRrvvGdtex2%0Aa%2BZeLKu8DGzFcEikq%2BeuTSjsD3N/wnDvu7gnoI/61Q15AmqzDsNtanhO3nklumhkVMIM5XOeaytc%0AScarOJXVjuUEgYzT6h0KcAzewgD%2BMfzrT8QJhk7ZJqhBGft8CqcNvGKva35yyJ5pU9cbaOoGKi/L%0ARUkRynSimImxkk12fw0OPEFwPW2P/oS1xo%2B8a7D4cceJnHrbP/NaiWxUdz1pelP7U3OFzXFaj8Q0%0A0%2BQI2lyOCSAwmAzj8KwUW9jVuwmqeLtO8PeKb%2BK8edzJDHxGmdpAPH61zvjiSO81qxuoJPMjm05W%0AVh3GTWH4p1dfEmqrem2NttiEe3duzgnnOB61Tvb6a8hsolYRLaW4t129WGScn862jG2pk2aXhIEe%0ALNL7fvx/I17c00UIHmSImRn5mA/nXiHhEs3inSwPmYTjJpnj6Et4x1HJY4dcBs8ZUZAz/SiUeZ2G%0AnZHsPiKURaBdTF9qxqHYgZ4BBqhpPi/R9d1OK0sLl5JgrOQYyvAx6/WqbSpZfDhLe8ljnnSwCPGs%0Ag3Mcfd%2BvQfhXkOl3OoaNq8GoW1s4lhYsqshwRjBB9qmMboblZl29H7px3%2B0Sc/8AAjXongRd3gi%2B%0AQAHMzjB/3VrzmV2lsVkcfOzsxAHQk5r0D4e6lZRaFc2s86JI05KxyfKSCo9fpVy2JjudVpAdfDES%0AxoqHY4wOccmvJ9alL%2BIpJyFYoQCJBlWIUDken%2BFew2s8K6WsiGMQoG37WyFHOea8k1lYz4gvEMyQ%0AKZ8b2yQvGckDnvUw3Y5bEfiGa3l1aOxtEUQ2sCCUg8SS45P/AOr3roPh9pkb3F1qMgz5QESL23Hk%0A/pgfjXGQIFWZt4bLEk57Y7jrXrPhawOn%2BHYN4IklzMwPq3QfgMVUnZCWrNmHG5s9TwaxPEsAlspl%0AA%2BZoXAPpxWzBxEW65NUdUTdBKSuQI27%2BxrJblvY8U3K1vFtOcLzivYl1mDRvBemzXlxHEJLZUBbq%0ATs4wO9eLWkTJbPKY5CoOM8YBrQ1TxRd6zpFrptzHDHBZgeWUBySBjk/StpK5Cdj2aC/g1Dw1b3Fp%0AOskbCMb19QRkfWvOvGbAeKtULsPuR8n/AHay/DXi/wDsixj0p7ZBbS3KyST7juUZGeOnarHjQRT%2B%0AI9TbeXBMezaevyj9KlRsxt3Rd8EZeV3ikDIJVBXHfBre1%2BXySsyjJSRWx9DmvLbO/u7CRms3eEsM%0AHaaRb%2B9hdiLiRi/XcxOapx1uTcv6lr0l5rl5eSxACZiNo7Y4FRWerLbW7SIp85ZkdRjjiooWiuJx%0AFMiruyBJ7%2B9RSwS28MqGMkb9u4dKoR1ms%2BJV1vwyLsw%2BVLHcBGTOQeOorlbdxJA5wQd1U0WWVhAo%0AY5OQvvV6W1kt9JjmXPzt83bHtSSsM0dF8QrockxaFpRIoGAcVDqN0l/dyXUYISSRSAeo4rEDHOTz%0A9a0ljzFFMoIRmwFz6UWAmhlSDUoZJjhFYE1Nrd9b3jq8Eg4ByDVS4TduPUjk1Rjh81iM44zTETQk%0AGIcj86Ku2Onq1sGdeSTRRcCJiFJbtXT%2BALqGHxOhklRA0EgyzADoD3%2BlcuwzkVoeGdKg1rX4LC4d%0A0icMWKdeATxmpexS3PbLy9RdLnmhlR/3eVKMD14HSvO72zgmcJcRh9g4B7Vr2fg218M3ZvlvZJon%0AAj8t0AIGQeo69PSql7Lb6h4s0%2BBWZ7dnHnBAeBz1I%2BlZx02KfmV7WytpUEbR5VR8vzHirEvh6wkU%0AHEi/Qg/zFdymjaYVBjto146xnFQ3Ph6KUYinljPuAwpc4cp522m2ul3CTR3IhBcIXkgVwue5HpUd%0A3qyyTzQI1lc4yBKLUpu46g5/mK6XV/BOoXVuUguoJDu3APlP8a5GTwzrOjzGbULZUgCkLIjhgWPb%0Ag%2BmatNMTTRgzgG6cgDg46U0J/OnYJfJPJOacB0%2BtWQRhcCnAZHan44poGScUAXdEmuxrCWyzzLav%0AFLmJXIVm2E8jp2H5UatO0mp30vOGlLDqOOg6Vs%2BF7eOOU30q4Cv5YZhxypz%2BX9a5171Hnu5GiSUS%0AJhSwIK5PDDB64Hf1pdRk2kWrX9zZ2b4LXEyo2ecZbn36Zr2m8cRRpGuAWbag9%2B1eVeB4ftHiO2fo%0AtujSAE5wSNo/mfyruRNJf%2BJIBCPNitXJlcD5V%2BUgDJPXJ7VM9yo7HRRhUCpjkD8hWLrt%2BkVnOkZ5%0ARGLt%2BB4%2Bta7A7Gwfmxya5rxIEh0S8Kg7Vibj3PBP5VC3KZ40FJUF3PAHfrXQaP4at9btwIbxI5ij%0AOdzdwOmKxLiBVuPLi%2B7nAHrVtl/s7aqrmVhls9h6VszMp/ZADhywK/eBFXXa6fFxgFSNmT2AGOfw%0AqwLSWa/EbEAAAvj%2BVWdcVraEIgwjDHFAGGl5EkjN5R39jnIH4V1el%2BHNJ1Xwrfa1c30kDxvswiAh%0ATxgY685FcYbc54bI9a0rIXn9lzWsLt9nkkWRlzwxHGcUMEUI22SL8uSG6etb18Z5oIIoYv3Sp5js%0AR1NUo7SO0kaZznaM4I71Wknkk3OznntnpQIWxRlnW4YYVe5q9f6lbXdo9sq7WTBVj0JFQvd2kmnr%0AAHYPgDgVQkiTG1Dz6mmAxwOM4wRnirEE4%2BzGOQnYPugdc0x4ybdQBuYY6VGeFAHGBQBcshH829jy%0Aec%2BlXRd2NvYeTHbAyHq7HmsVG5wehp5YY5osBP8AaJQAA%2BBRVRnOeDRQBcTJA%2BldN8P7KSfxA91G%0A4X7Km/kZDbvlwf1rmSNh2itPw94km8PSzFIEmjlK7wSVPGeh/Gpa00Gtz0fXn1e5tjCqWzAHcpRi%0AvbGDurD8N2%2BqaTdebcLLAGLF3wGU%2BnIyKli8b6TfqRMZbV24xIMr%2BYq0QUImt5mG5QyvGxGQeh4r%0APVKxXmb6eImxjEU/%2B7x/KtCLW7dxl0dPfGa4SfU50fM0ME%2BOjOmG/wC%2BlwafF4jtgNskc8X%2B6RKv%0A5HB/U0co%2BY9Djv7SX7s6Z9CcfzrlPiBeImnxQhhlgz8H8B/M1m/2rDMpFvcWsrHojP5Tfk%2BB%2Btc3%0Arcr7dkkbRucZRh06/hiiMdQcjEAyad0ODUakiReDipwa1MxhWljGH5pxPy8ChFO6gDTMrpo%2BEdgq%0AszMMcCuXiZpDIEUluAoAye%2BOlaQFxdXr2iylYAvzLnr64/Sp7iOKC1lKsEZVJBXqDQM6DwfZ3Nvp%0AtxK8bx3EzquXH3Ix3P4k131la/ZbZY4/kUcnHUnuT6msTQr0ajo8FypChVCybBzvA5wPX3PrxW2t%0AyoiMQ%2BVQAB7VlLVlom86KNGXzCSe5BrltfuVutPv4AMxiIj6n/IrXmnkjidgp44Cismezc6JqEzn%0A5/Kd/oQpoQM4WG2tZp4ZYlETIgDAndub19qbf6Rcxy/b5ZYmt/MUHHUCs4Xk8NpHPGwDE4PHFXF1%0A2S9sjbXYiEQIYkDDHFa6kGnpYilu3fIyW8wnPfsPwFV/FE5EEIADZYk4rIjlgUr5cjo/PJOAaddX%0Ai391bxM3yKQGPbFFtQJVsIxo0k0oxPkbeema1bS2EMMUeOwJqhc3Cz3nkRkBAwOPWt6Ip5YkBBJ4%0AGDxQwMLXrd1IkGdjYDD%2BVYabd4DE46V1eu7WsZckDaoPPc1ykZ3DGOlCBgUj3fKSAOuadJ5YwUdm%0APoRSs2BioVyxH1piJEZhINuQfUU%2BVGCbz3PWm79jHgGleZni2bRjOaAIxTSrAnripFjY8ikfIOKA%0AIsH1oqXHtRQBbb7xOKiCZPPNSsrKxwMimFXPY0hiFAeO9amrapJqGrfbLPzLdY4o4kAbBARQO3vm%0AsxVfripdxIbPHHpQItp4hvkGyfZOBxlxhvzFTLqttISJUeFv9oZH5isZwfn/AN4UsufMNFgN4bJB%0AujdXU91Oar3C5lwpPAxjNZTOFSPYxEg647Gl%2B2XOf9YST/e5osM0ArZHJzQGcHBYH6iqAvZ1Jyqn%0A8KBqBH3o8/Q0xF/zGLBdqnJxThL5TcoePQ1Tj1KEPl43wOBjHFOOoQOxOWX0yKQBOnm3AmR3TvwO%0ARxjrTlhRZFdyWxzhicH6ipIbmE4VXUn0p0kiE4yvHvQBsaBq7aReySIB9lmA8yBemR0YehrsrPXb%0ADVrkQ2rSfaApYxuhGR356V5iu084GfarlrcTWc3nW00kMmMbkbBxScblJnqJ8z7h%2BaM8r/eU%2BnvS%0AXH7nS7qWdPKgETbsg8Lg5rL8J3N5qVjcT3ly0pWQKhYDIAGT0q5rd6bfRNTedmkIt3CA9ORj%2BtZ9%0ASjyZlUadHxxnjNVSwUcY/Kr84H2CFPQCshiwfa3TNbGZPBcLGWQ26S7jxu7U9plkfAtUjnHAKcfp%0AUcrImNop8gUKJGJYnk5oAn%2Bx31sBK1v8z9G6inw3c9m4%2B0ws4HT5sAGrmlarAtlJaXSsUY7kK9VN%0AUL6Xz5CI1IQc8nqfWkBDe6hNesQ/CA5CioYjjoKBBlD/AHs9c9qJUSNhsbIP6UwHOgc53hfqKaEK%0ANtyGB9KljiLEDdj3p0sPlKCHDHOMYoAqyZ3kVIrALzTpMooYgHNEbFmyFHFAAspHQUjDc2404EPI%0ATgfQU%2BQggYGDmgCHb70Up6nFFAGy0AJ4oW1Y9s1bIG6r1mg3jgVNyjH%2BzhDnafem3CiRVAGMV2Ut%0AlFLGQ6nd1BUcGuevLN4ZOF4oTCxzsq4aQejCrZhZScgHNV7kETTD/aFaDMB2pklJoRnPGRVRlCuB%0AwTnmrVyzv9wdDg1SCMrgt3NMCS6GHlI4w/QVVBO0sQCBU95nzX9NxqpkjI7UAP3ITyMVJHErsoz9%0A4gZqBAS1WIOZo1HUMOKAN6x0UQ3aOXL5A2gj14rEutv9pSNHyolIBPfBrvZI0iQEDBIVRgZJyK4n%0AUrFrGTaxUndxtP8AOkmNnYyJbC0UusBcsvBxnqBXWx%2BHNFngTfYRBigJZCVOfwNebNEs1tbXAyTK%0A4wPTA6V2Wj%2BIpUsz9uZpdsjoGRMHAzgfXioafQaOrstOs9OshbWqFYwxcZYk5Pua5GfWLa6tXttY%0AYQwOCrTJ/h6/StC48UKJYrWGB90g5dyBs/D15rzXWpt7wQByxViSCenaiMe42yfUjp0MrC2uZpIA%0AflZkwTWRLLZyA/JJu7EcVrayqJaQgDk%2BgrAZO4zWiIJAd8QPcdakVg8OD2qO1BLlccEUsX3nX0oA%0AhP3jj1qTbmAn3qMgliamU5j20AMRio4oJ3HJqQR07yeKAJ0O223/AMWaZvaRhuxjNKiMF2npnNGz%0AnNAED/M5PvQo4ODg1Ns70beeKAGRgxtyKe7kkcdKUYNPEfGRQBXIPaipttFAHW3OnSqzPEhKD%2BEn%0AJpLN1DjPGDWrJP5ZyY256DuaebJbsBigjkI69/xrO5ZesL228vy2RSexzWfqccck52cAnvTZIhZt%0AtkhJHZ8/KajmkEjKQg9hmgDjtRj8vULtM/dfFWZE5qDVc/2pe8Y/eVoyRYA47VZJmPHg5qrMMFeO%0A9arxggis%2B8XZs/3qBFaRC5kz2NVXTB4rQjXJl9MioZIvamBSGVPpTrY/6VH/AL1OZMnFLHApYHdg%0AigDtr3UYIVtFMnlu6Da30PU/571zOtSGa93h98ZA%2BYdCe9WYQJQgk/ebB8u7nFO%2BzRkMvlbQwxgd%0ABSWgy7ayo%2BjQMEw0bFuvQ4K/1qxo1yk9goDYClwzE4w3XP4561lWcrNo15ADtlgjMiEdchgf8ara%0AdcrHAqZ4cv5g9iMUWA37aXfqcQYEKrhjjtzjn86w9Wt2kvZMHDKxwavwzyAx4YsAQSPXFb1l4Wvd%0AU09r6DyiryPhW6nBpXsG5x11JJOsQcn5V7GqpjG4EgkelbV9YS2s7RTJsYdRiqDwe9O4ioxbG1Pl%0AB9KI4imSe9T%2BWQOophUimBXdMMcdKFU1Yx6809Yy38J/KgCBQanjVqnjt3fotWo7MnqyigCoE45F%0AL5ftWmlineTP0qUWkKgH09TSuOxjeWPSlEBPRSfwrYcxKPljVj/s0z5CO4%2BtFwMv7HIecAClFuw4%0AJ474rSIAUkmkWBgc7SaLgUhaLjqaK0dso4Crj3opAdBGAH3tkv8A3jV2J%2BRziskBxz5hjH%2B9n%2BdT%0ApIv/AD1kkP8AsipsUbiSJtKsobcOQe9Z91YlGMkHTsPSmxysekb/APAnx/Km3Uc0gDNcPGuPuxk/%0AqTSA4bVMnVrzPXzOa2GGQO4xWPqS41S75J%2BfqeSeK3bmB7cKSNyED5h9O9WSVHUEdBWTqIwI/wDe%0ANarvjvWXqZyIj/tGmgYy2Xf5uP7w/rT3gyOlNs%2BGm%2Bo/rVrIPXIoAzZLfHOBUYQA9KuzDJ4FVSCO%0AwpiL1qVwM1eUKOefwFZEbFe5rRjmVlG5sj2pDKhKw6jMMfK46fWs%2BIeXcOnoxFXblQb3K5A2gg1S%0AOReSBupwaYjatSQyn0BP6V654PQL4WsMD7ysx%2BpY145bNtbae9es%2BBrgzeGYkP8AyylkjH0zn%2BtZ%0A1Ni47ljxD4eg1WFnI2ygcMB3ryy70ya2naOUbGXjBFe3t0yTXL%2BJtKt722adcLNGOo/iHpUxkOSP%0AL/s6jq2fwpphjzxz%2BNXZNpJAJyPSqrLtJK7ueua1IIPLx91B%2BNTIT024P1pjmXqAp/Go/NnzgICf%0AYUAXcEYIU59RVmNWYfdH4GqEa3jD%2BID0q1bW8%2BfMWUA9weaALBRQMuoX3NNlhLRkLgg/7VWo1VQD%0AOfm/SiVUbsv5UrjKC8gZU5JxgVLsJHQ/jUyQKoOBjPXFBRs/K36UXAryQAqSFII5Bp0byOAV3HPt%0AxQ8rSuYFKkY%2BZh2qwECqAvAHTBoAjKTHngfjRUpDZ4yaKQE8dxFEQskflt6tyD%2BNWRdxDnzEx9at%0Ay6PBMWRpJduO23/Coz4ds1XIeYHOM5H%2BFIBiX8XO0lv91ajudREYKtG4DDgnirUOkRDI8%2BcgHuR/%0AhUN3pUTqEMs2D7j/AAoGcReyebd3D5By3Y10gufMgXM2QVHQ%2B1DeHrQ8mSbn3X/CrMWjwQoAkkuB%0A2JH%2BFNiMS4ZEPysW/Cs3UM7I/wDeNddc6TAyZLyfmP8ACsrUNJgaCP8AeS8Oe49PpTTBmJZna8vv%0AirJkHsatQaVCGb95L09R/hUjaZCP45PzH%2BFAjNLZHSoZABzWqdPiC/fk/Mf4VE2nxf35PzH%2BFFwM%0ArzMGpIpAG5PFWW0%2BLdjfJ%2BY/woGnx4%2B/J%2BY/wpgV7s/IjBvmzxVaddkkcp6MMGtWSwjMcfzycN6j%0A/Cob6zjFsnzPw49P8KAJLQq4yB2r0X4eTn7Hf2%2BeEmDgf7w/%2BtXn1hEoQ8mur8Eu0er3iqxAMKkj%0A6H/69RPYcdzv7zzvKJjfacema4u7vpY5mSe4YhuxOBXVNK85KOx2n0rg9eiWO9IBJ9zyaiJUinqV%0ArAxM1u4JzztzWUzsjfMd1XFZlzhjj0qjck7jzWqJDfGx54PvT1AHas52OetSRyug4Y/SmI1o2Iqw%0AFA/eLjcB0PQiqVuxdAT1q4ihgVPQipGWoh56BmCxqRnCjJ/Oke3iRcKABVWxUmNv3j8OQOat85IJ%0Azx3oAhMXHDkfjVKV3ZtiSEx9yOM%2B1TXUrGMjgZ7jrVcjaoApoCVXiUAFQuParKCNhkFMVRQ5696e%0A4GPxoA0DEP7o/Cishk5%2B%2B/8A31RRYD//2Q%3D%3D%0A"
    },
    "Header": {
      "En": "Boys praying at the synagogue of Mosad Aliyah, Israel 1963",
      "He": u"נערים יהודים מתפללים בבית הכנסת במוסד עליה, ישראל 1960-1950",
      "En_lc": "boys praying at the synagogue of mosad aliyah, israel 1963",
      "He_lc": u"נערים יהודים מתפללים בבית הכנסת במוסד עליה, ישראל 1960-1950"
    },
    "PeriodTypeDesc": {
      "En": "Period|",
      "He": "תקופת צילום|"
    },
    "ForPreview": False,
    "Resolutions": "100|100|100|100|100|",
    "LocationCode": "SON.31/123|SON.30/49|SON.72/87|SON.30/50|SON.31/124|"
  }

PHOTO_BRICKS = {
    "NegativeNumbers": "|||",
    "IsLandscape": "1|1|1|",
    "PrevPictureUnitsId": "137523",
    "ExhibitionIsPreview": None,
    "LocationInMuseum": None,
    "Pictures": [
      {
        "IsLandscape": "1",
        "ForDisplay": "1",
        "ToScan": "1",
        "IsPreview": "0",
        "PictureTypeDesc": {
          "En": "Picture",
          "He": "תצלום - ש/ל"
        },
        "PicId": "204200",
        "PictureId": "DA493EE1-0A0E-4518-8253-178A724A5F78",
        "LocationCode": "SON.14/276"
      },
      {
        "IsLandscape": "1",
        "ForDisplay": "1",
        "ToScan": "1",
        "IsPreview": "0",
        "PictureTypeDesc": {
          "En": "Picture",
          "He": "תצלום - ש/ל"
        },
        "PicId": "204415",
        "PictureId": "5349A73B-8199-4A5A-AE46-4B9C2B066092",
        "LocationCode": "SON.14/328"
      },
      {
        "IsLandscape": "1",
        "ForDisplay": "1",
        "ToScan": "1",
        "IsPreview": "1",
        "PictureTypeDesc": {
          "En": "Picture",
          "He": "תצלום - ש/ל"
        },
        "PicId": "204199",
        "PictureId": "21F612C4-503B-4941-AA47-D935A5FE9952",
        "LocationCode": "SON.14/274"
      }
    ],
    "ToScan": "1|1|1|",
    "PeriodDateTypeDesc": {
      "En": "Decade|",
      "He": "עשור|"
    },
    "related": [
      "image_new-immigrants-families-in-the-maabara-israel-early-1950s",
      "image_view-of-a-maabara-israel-1950s",
      "image_view-of-a-maabara-israel-1950s",
      "image_building-blocks-for-housing-projects-israel-1950s"
    ],
    "ExhibitionId": None,
    "UpdateDate": "2013-04-10T11:31:00",
    "OldPictureNumbers": "|||",
    "OldUnitId": None,
    "Id": 303772,
    "UpdateUser": "Zippi",
    "PictureLocations": "Box 14|Box 14|Box 14|",
    "UnitDisplayStatus": 3,
    "UnitPeriod": [
      {
        "PeriodDateTypeDesc": {
          "En": "Decade",
          "He": "עשור"
        },
        "PeriodEndDate": "19699999",
        "PeriodNum": "0",
        "PeriodTypeDesc": {
          "En": "Period",
          "He": "תקופת צילום"
        },
        "PeriodDesc": {
          "En": "1960s",
          "He": "שנות ה-1960"
        },
        "PeriodStartDate": "19600000",
        "PeriodTypeCode": "4",
        "PeriodDateTypeCode": "4"
      }
    ],
    "PrevPicturePaths": "Photos\\21f612c4-503b-4941-aa47-d935a5fe9952.jpg|",
    "TS": "0000000000024ac9",
    "PrevPictureId": "21F612C4-503B-4941-AA47-D935A5FE9952",
    "PictureSources": "122328|",
    "UnitPersonalities": [
      {
        "OrderBy": "1"
      }
    ],
    "UnitTypeDesc": "Photo",
    "PeriodStartDate": "19600000|",
    "PIctureReceivedIds": "122329|",
    "PeriodDateTypeCode": "4|",
    "RightsDesc": "Full",
    "OrderBy": "1|",
    "Bibiliography": {
      "En": None,
      "He": None
    },
    "UnitText1": {
      "En": "Building Blocks for Housing Projects, Israel 1950s\nPhoto: Leni Sonnenfeld.\n(Beth Hatefutsoth Photo Archive, Sonnenfeld collection)",
      "He": "לבנים למפעל בנייה למגורים, ישראל שנות 1960\nצילום: לני זוננפלד\n(בית התפוצות, ארכיון התצלומים, אוסף זוננפלד)"
    },
    "UnitText2": {
      "En": None,
      "He": None
    },
    "UnitPlaces": [
      {
        "PlaceIds": "113047"
      }
    ],
    "main_image_url": "https://storage.googleapis.com/bhs-flat-pics/21F612C4-503B-4941-AA47-D935A5FE9952.jpg",
    "UnitStatus": 3,
    "PersonalityIds": "49547|",
    "PeriodNum": "0|",
    "PeriodDesc": {
      "En": "1960s|",
      "He": "שנות ה-1960|"
    },
    "PrevPictureFileNames": "14-274.jpg",
    "RightsCode": 1,
    "PeriodTypeCode": "4|",
    "UnitId": 137523,
    "PicId": "204200|204415|204199|",
    "IsValueUnit": True,
    "StatusDesc": "Completed",
    "PreviewPics": [
      {
        "PrevPictureId": "21F612C4-503B-4941-AA47-D935A5FE995"
      }
    ],
    "PicturePaths": "Photos\\da493ee1-0a0e-4518-8253-178a724a5f78.jpgPhotos\\5349a73b-8199-4a5a-ae46-4b9c2b066092.jpgPhotos\\21f612c4-503b-4941-aa47-d935a5fe9952.jpg",
    "Attachments": [],
    "UserLexicon": "93513|",
    "PictureTypeCodes": "1|1|1|",
    "EditorRemarks": "",
    "PictureFileNames": "14-276.jpg|14-328.jpg|14-274.jpg|",
    "Exhibitions": [],
    "ForDisplay": "1|1|1|",
    "DisplayStatusDesc": "Museum and Internet",
    "PeriodEndDate": "19699999|",
    "UnitType": 1,
    "PictureTypeDesc": {
      "En": "Picture|Picture|Picture|",
      "He": "תצלום - ש/ל|תצלום - ש/ל|תצלום - ש/ל|"
    },
    "thumbnail": {
      "path": "Photos/21f612c4-503b-4941-aa47-d935a5fe9952.jpg",
      "data": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a%0AHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCADnAQQBAREA/8QAHwAAAQUBAQEB%0AAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1Fh%0AByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZ%0AWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXG%0Ax8jJytLT1NXW19jZ2uHi4%2BTl5ufo6erx8vP09fb3%2BPn6/9oACAEBAAA/APf6KKKKKKKKKKKKKKKK%0AKKKKKKKKKKKKKKKKKKKKKKKKTNGaXNJkUEik3U0tRml3il3ZFLmilBz2xRRRRRRRRRRRRRRRRRRR%0ATCeaCRSZo3YpN1BOKaW5NJnmnLzTguW6cU7bS4paKKKKKKKKKKKKKKKKKKKKj6Gk70dqQmnBSQMG%0Ah1wpwahz1pASTipkO0c04PT80gOelGaOtLRRRRRRRRRRRRRRSFsU0uO1AkFG8Uwnk0hPvSZzjmlO%0A0HqT7UeaaY8hbqajDkGlDNnI70vmE04E5qYYxnOaM%2Bho3GnA0tGaM0A5paQkDqRS0UUUUUgNFN5p%0ACKYaPLYjPFIrbTzzTmII6ioTnOKAxppcY5oDKVwfzphyTx0ppyD1pwfHekEnOf6U4yHrnipElp3m%0Ac808Nk08MKUOM9aCymkyO1Cn3pJpkgheV2AVBkmvMJfEfiF5Hnm0ucF2JWNJ1zjPAA613PhvV59V%0Ast1xayW8igYEmMtW3RRRSE800GjPekz15oJGOaYaQSbeKazDHApgbHaguSfT6U3dwaTA70hI6U0t%0AxTGJPrTeO9G49OaUNTwwHSpA9O3e9PDZp4IpSQDSbsUZ5qG7hW8tJbdmKiRSAwH3T2P4HmvnDWr/%0AAMV6L4uudIsbhNV%2BzviOZYCxcEAnO04zk8jtXtfgC21htHiv9ajFtcygj7KsZXaM9Tkk8%2BnauxzV%0AXUrR7/Tbi1juJbd5UKrNE2GQ9iD9ayfCutTahYyWeoYTVLF/Iukz1I6OPYjmug3Coy4zSBqXNJmk%0AJpDz1qCeaOFcufoO5rJfWZQzBbZGGeMSHJ/So31x48F7dBnj/WHr6DjmtK2lluot0flKwOGVi3y%2B%0Ax461N5V2QBiDrz87dPyrPe6vIblVkgie3O5mliLfKox2PXrz046Zq4HDKGUggjIIPBoLVGWqOSQR%0AoWY8AZNV47%2BOXO0ScED7vrSzX8UATcJCZDhVVCWPbOPT3qw8wjiaRs7VODjnn0p0VwkwJQng85GK%0Ae0qohd2CqoyWJwAKIb%2B2mUtFcRSKDglXBFTrcxFQ3mLg991PSeOQnY6tjrg04txVW/vksLN7iX7q%0A8D3Pas618Sw3TEwqhjB2s5PfuBViW8AXMDhQOdqgbf5Uy313zYjmVNyHDgVmaT49s9Q1D7M2QG4D%0AEcqeRg/lXYqcivOdd0HVl8bXOowzYgliWSNlbDFgNoj9QByfTn1FdvpNxJc6NaTy/fkiDHnNTk81%0Ayv8AaGrywM4uHGOchFVf5VdbWbgDiSIn2AqE63edQygf7gpG1y8HG9T/AMAFRvrt9jIK8Hn5RzWX%0Aem%2BS0uL19TmZkDSJgAL06N6iuO0fxFrOp/E%2B902a9eOztbTcsUShQ7BgNx475NdtBLcwyTGKedXy%0ABu3DpjoOOPwrjPGvjHxJoVm01nqdwjHURbKXAZduPcdfxr0Cz%2B1NexGfUbx4gfmRpeGA7EVveXDO%0Ao8tpUTHUOTiua8%2B60qee2tE3xGTcFfJCEgZ2%2Bgzzj1JpieI7qSNXEMJBz0ORwfUGoh4rdriS3C2x%0AmjAZ08wgqD0zUN7rc93CIvkh%2BbO%2BKTPboR3HNcG154xj%2BISxx3monw8CFLbxsxsyeev3v8K626lv%0AVWe4h1C%2BNxg7W80nHHAHYVS0y%2B1e5juUvb29S3il/wBH2y7QRk4OMfSuyuNUh0j7Mk6SGSVCo%2BdQ%0ASRz0YjP4V574/wDirqnhmdLfS0i33QJRriJWEIGAeh%2BYk%2BuQKn8BeJ9d1q2efVLr5Jx/orQRRopY%0AAl8hRwQCvWujvz4gbX9OWzuWGmKB9ryyBjyfbPT0roXvEhsreOSRg127xI23JJBHHp69aytIuPEK%0Am/j1RbRIhNi0MSKWMfPLeh6VwvxD1DWo9LuWvpYrWxW8Qae6j5pQqFvmwT/EM9B0rk9L8VXsmn2s%0AEZCJgNuB5Pc5/HNdtbeNULRwnO0rtLMeAazW1aSz1likzDzSCh7ZNZ%2BiWev2N1LrGjTQXTTxPLLZ%0AsDmMBmAx6ngenUV3vg34nw3wFpqUixzj5VDthie/UVvvqX9o6vBZqjNLdN8zDPyRLyfpxnn1NM8N%0A6jDo99c6BLdK9om6awmZuDFk7kJPdTkV0ovLZhlbiFh6hwazo7OHStMEM7TxiFWLSrF5gx1Jycgd%0Ae/pWRa6zDe2qqdUju/tDFIyYVj2Dn5nYZx046frVfeNxYpNJg8bRgH9aUtKy4js7h/T5qhLXRlbF%0AkDxjDOSRS3klu0DQyFGicbZoiScggZHWqcWn6ba60LuK0tbeZo2R5lxuI4wCep6Voi5tw026SNQp%0AUnLgcEdaiuNFstX2yvZw3MG/f80e9GYH73pkVtwFLO5hll%2BRcnBfIB4qe88RabapvnuoeoJRPmYn%0APZR1rkdb1WO71CaayhhuIztCkoQ2cc8fWseKbETWqWVuCoI%2BSMhlz6EHg81FNZvHqEtzHYlZZIvK%0ALGLcDwBnBPXipsXkeSsSJwBlIFU/Tr3qOWHUZcjdIEY5K7Qffj05qFrXVGuHka52lgMocfKPp%2BFW%0Aorp9HiSTU7tniOB%2B78sSMfUbsLxmtO8vE1eeCYQmb7MN0PnKPNdSBnBA4B6nFcR8RDB4xRINO08R%0A3VmyrC6YUOp9jyDkkde2TXS%2BE/DlhoOhxW6zSSrJmYSGTDZYA4wD6f1roC8Lphrh8Y6%2Bcf8AGnM8%0ABRVYiURZKq67jz1xn6U2RYVA2xM/PISMf1rgPinGUs9OLho43kcqrYAO1eTj8RXA2Mf2KKO3kdS/%0AlpJ8vYOodR%2BRFascwMYA709p2yCWyw6E9jXsHgmc6poEF0iLAELQOY%2BGG0Dnp3z6%2BtL4k%2BHGmeIo%0ADMM2N2nK3SKDuH%2B0M8/Xg1DoJ0fwYktpd%2BJLe4vMlJZJSdyKP4AMnA7%2B9aGvT6Tq1j59peWg1GA%2B%0AfbyYwXIHKnjkMDj8RVzSV0rV9Mgvbe1gRZF%2BeNmKlGHUcVy9/wCK9QvbixW6lZ7czoHREA3L1OVz%0Agn8aba3On2uoTNZWE1ksku%2BR3UXRnPqAWwmPbFdQrW%2BoQR3UUieXINyyBFUn29vcVFLHKFMfn4xz%0AkDj8hwKo%2BUI7maARXW%2BEB2K27lcN3DYwacti09rBdgo1tMm6OTyg24H/ACaqm0t4smOGec5P7uG0%0Adzx3O0dOg9a5a81eXQb2OXWtHd7edtiC7tntvLkB5O8ZBXnuO3FSR/GXUGSaF9N0%2BaDJUjTJzHIF%0AOeQWPX3A/KqkHiDV/FE9xLZaytlFa7FjknvHBiXptZQoQliDzg9MZrp0tW0yUWuqw2z3bkbLmE71%0AnPcg4G1varbypEMQ2Y4OCSm3B%2BnXvTxOXYq8G3ByNnX2%2BtRtHPPOoayYRfMG3SY3enT0NP8AsTE5%0AYrgkDa8m7PvjtSvYyMQpWDbj%2BEH/ABqnJpiECLz0VmGOByOPTn1pb3w9b6jDHFJKVEZyGQjOce4r%0AL8RXl14esrGLTpdryl41ZkUqxVSQrAjv3xiuE0zU7maeHUZxHG00qN%2B7OFjxknr269a9dtLeC3sb%0AcSQhnWGMEKpbJ2jNWdiqN/klQOuentUypdMpAhYHud2QKsmC5yu8SAr02gf414x8Z5bka/plqtyz%0AeVauzgtnAdjn89tYPiiwXSr3RZ0kR5rnSbd5YkBGwqgXLcdwP0NQ285IwYCO%2BY%2Bf0NWYVea5TyCJ%0AiT9xc5Ptg963PC95LH4ntA8j%2BTanzIF3/e9VYenH6V9A6bfRX9r51o%2B5doOxuqEkjBHtg187%2BLYp%0AR4u1g5yftkgLA9Tmun0uTfHaqyzEm0ViQMA8KOvrwa6J/DWqzrHdaRqf2OGdBJLETn950Y/jgfjm%0AopfCT6m1ltjEoRfMSWGRljTJxwVGC/t/KoXsbTTL24e5029mQphAd0LkjqduDuHTBNbOm3trLaG0%0A07SbmJBhyGn3AHHTBAGe3XFX7izu3jH2LbFMcHMyhgB3wAfy5/Cn6Jp1xYTeZqut305hY%2BSiu4BH%0Afcq8En06Vlarp97FcXA0fUIYw7AlZ2CtG7cllU/IB7Y57k1k3SapqsEFn5F/cKBi4uoZ/LJIPYDA%0AAPXIx71raPotvY2otjamed5FL3GrT/aJGA5OF3bV74GQM9c0q6HY/wBrpqV14ZF3chdqS77bbCd3%0AUIMAHB/2vrmr16tvZWssl5q9%2BsUUhaKf93EYlbOUBVenI5IPT3zXNrc6fJa3ME3iLSmtXlEsE0ca%0ARTIQOWYrwWPrj8KsXl%2Btj4dOoQ6vb3YZAkVwI/NEjZxnahw3Hbj3OKZZXkujWb3PiLUrPCuQrkeW%0AxzjChRkA84xnd7dK4u%2B8Q67pfiCbVbeCa6t9uZLaGP8AdOOgOC24MAOSF6j616LpXjLS9QhhRP8A%0ARXmXK/a4vLMnHOGPBIzg4rTbBPNwh2nGOp%2BnSmGGKNd4LllGSAP6U0EScpFPu9CCMe/NcV8UBc23%0Ahm0uhGVMOoQPk9ep/wD1V5Zry2lrqVpbRf6THNcJOyA7kCMfuZHJPUH6D1r6GvLW4uLG5SymhiuH%0AjIgYjiNyODiuYi8M%2BNXWXz/ES5UBohGMZb0PA4pE8O%2BMY0M974hhiCHcP9ogHjI6%2Bvviuo06Ke2t%0A44ri5lu7s5lllkHXPBwvQAZryr4nWUl148srcK2Z7aGJcnrl2HX8ayvFMovPG%2BqyAK8UUgt4ieip%0AGAoAxxgYNUvNkQhGSNMd9pP9aRg9yVUTurKwKsvylSDwRXp3hrwjqus6Xb63e6xFOLi2dyi24QpP%0AkjeccHBGT0J9BmrWn6L4l015JpfEESwqpYFRjL4%2BUnA6fX8jXGz%2BEvEl1cXMz2014TKztcDIMuT9%0A7Bwea2tMs7yKHTYjbu0kX7mQBwyqAeckEiu0sRf21mkLPPHtzhEZQAM57mti8tLOyt0S5vI4bUDa%0Aoe4Kr9MZxVbztBgt/Le7hkRekalpTg9cCmJreiRIfLEvGAg8pl69B/8ArqnL400uDEfkFpCuSoOD%0AjPXjNVp/HdmkoRdL1BlII8xUUKPqWYVLY%2BONOuZGjntrm2CgESSBDk%2BgCkkmpbfxjos1urXN20Ep%0ALKY3QjkEjAJ%2BlEnjLQosA6hHg4AyeP8APanReKtDeKSWK9hVI2AdmkwBu6ZJ9T0rC8XvHrWlwx6L%0AqNobiKUEJHcr8ykYPO7jHBrg7vTdS03QIr%2B7naG9kvjAYUmDqE2kq2VY5JxXbeFPDt74k%2BH1pfWu%0ApLZXdxtnjiRMwoVc5PHJJGMjpkdK5dvBviD/AIT64s01dvtMJM0moyxZVlYgs4DKQTkgEA8E4zir%0AN14UubAGSwvPtuttcYOo3LCOOEA87FUHLds9u1WdS8Fazr%2BiKlzqEWo3qK0kN1K7rLC3GVQl8Mpx%0A3/ECp/CsPifQdT8jW4L/AFK1vFijtiqx5iIHLNhuMAY65PXtVjxfqOr6PrGyK%2BlW1kAkjWNivlpn%0Abj3wec1tyeF9TVV%2B1avOQCNuS4yfXG8VxnjfSn3C3v8AUpWsIlS5mYk5KgngDJ5yMD657V5dHdSa%0ArrUdzKoRmuYzHGnAjUOAFGPQGvpVNQ%2Bx3Bt7h0kVm/d3HG7J/hkx0PYHo3seK0JbwoisskYJz8hy%0ASf8ACq4muJ3G0qQD1cngY9h707c6uF24BHPHP1rzD4h3ttpPxB8OXkrNILVoGlTuR5pIA/DmuAv5%0AZLTUb22ukcTRzSo%2B4ZDNuOeff%2BtVrK/N4nU/ITGwPX2P9PwrctLoNaGAQ2q5Od/kgOcdt3UV2fwn%0A1G/tvFmoaYpdtNu4DdhD0imUqCR6ZB/Hj0r12fTLS9lhluIcyQsrr85C7gcgkDg8461e33UqSKhL%0AnaR8pA/AHsayItJt7S3UW9m1qrksVwAc9yeetUZVhZyWcZ/3jXn8Gq6be%2BczSXcibyjB1A5H0xxW%0AZq%2BtQ6ZHEkKSNE%2BUXc7gg8Hk7jmtJL1FUk2kQdiCQM4b6jvW74ihn0vw1DewaleQTSyIiBbhgig5%0AJAXp0FchBretx3lqJL3V2tXlXzJRkIVyAw3nvj0rY8WeFdbu9V02PS/tE%2ByQGR3mONvII3H6g4qg%0AfhvrWoxvFLJFGIJwWyxc7gQ20dB0PXPQ1qW3wsnLkXN3sQchkK/y5NQeJ/Cdt4a8OXaC6eRL%2BWGA%0AtKABGAxJbjsBS%2BG7O3tba%2Bn0XztRtHfbA42xvLtGMgHjBPT8KxNbsb7WZbLU4dF1G3vbK4Nu9tPC%0AS5QjeG%2BUdMqRnpzXc6Freq6dYwz6nZW9tPMy40%2BORIpIwerYdhnvwPTHO4Eauv8AjBLVDDPGIzJx%0ACVyxI6EspA2gcdzntXM29zdT3ZwyyrGCDIkYReT/AA5JyP15re0YCC1Aw2MnHQ8ZNZXiHwVba1Ml%0A5p97cWV4snmAtLI0W7GN2wMNrDsVx9K5aa3LakdH8R%2BKLZrm3QoreQ/mSKxyCd2FBzjoTmp4oNbt%0A9Rnay8Q292zKW8y22SStyeCpOR%2BeKqa5Fr97ZMSG1CFYpPMmuoti4xkEdMgc4wTgg%2Btea%2BGtPnvt%0Ad0yyj/1s06jJHIAIP9M59q%2BmF064v/MjEcZibKsmwFXX3/wJNU1J0k7LiSRrIMAHPLxegc91z/F1%0AHf1q6JMXKL5rquOEByD%2BH9av4QpgttBHIz96uH8W%2BCW1bUTf2tqbhJ7b7HdRoVMluxIKzIGwGxgc%0AAg4ziuA8b20B8Y6mIT8vmgsBkYcqC361yJh%2BwXp2oWjnGSB2I7/kavRXSk7VB3HtXY/DDVvsXjZZ%0Arh5FtfIkRlCljIcfKgA6knGAOa910%2BW%2Bf7Xe6vY22nWyJuhHn7nRAOTJxtB74BIHrV3R2RtPRluG%0AuEkHmLI67WZW749PSsvxb4kt/D0NmLq3la3uJCjzR4Pk4HBx35IGP/1ViXOoJ9ocRGJoxjaSMZBG%0Ac8/WuLttM0GyinjRb%2BTe5fzEkjZAT3LA9PyotF8GasVhMGoXE0LEtvjyoIODjdwfwNdZFJ4RWya4%0A8krKuVCSW2GVucZ4I56jmmrrWkwxW2mi7ES28aKqyxLI7YXAwp5HQ8in6jdm/wDD9/Hb6pA3mxyR%0Aj/R40y5XoMnrgj9Ku6X4gstqyXWoR2%2B6NR5bsQpbqSGxjI%2BtTadqWmXGsXsdtqkLNPKkkeGGHPlh%0AWA9fuc1buNU0qzyJdZsg27BDTLlTnoQDmuJ8bz6fqx0y1F6stm1x%2B/e3Hm4XqflGSeBj8awJ5F0u%0AOE6Df3qyS3Ajt4YrbMXlqw3tIuDs4b0zmu8XVWgvbLyI7u6tZtyzT%2BWYzCQB/CwG4HJ6elP1HU4L%0Ah0Xy42wfk8xASD7ZHH4VzskdxNdyPJdhoXb91GIxk49Tjp6Vo2loscLblCB%2BSB3FXFVQABwOwHap%0AhL5TY3/L7/n1pt1p2majJDNf6fbXUkORG00YYqD1APpSjSdKiRbbS9PtrISjFzLDEqlYh2BHr0/W%0ArF9No1/bGwe4TYUKBIHyAAMYOMgDpXmHhDQk0/xZ4eS4szvSCbzNpBw%2BX25wf7uK9PvNVCWc7mcx%0A21uhZivzvgDJ/EVzmqeJfsc8tvHAZxGFB%2B8zNuG5egxyM8VhL4y0S0hEEl4tmMny7aTdmHHTBwPl%0APoM46DiugsPFkP7v7VHMkM0QdpSh%2BVe5K4yBnp1PNa3/AAmGk7/s9rcR3F2QGS3YlCw9eRkDqc4r%0AxvxjdqviGS5Mcccl2xmdEk3gHoMHHcDtVnTvDdhrugT3IuETU45Qtv5kpVEXALEqFJbIyOwFc14t%0As/8AhGV01oZorlruJ2kCkEIQQMDBPY55x1r0T4XT6bYWVlqclvdtfXMzxQmMM4ztxyqg4xluT2x7%0A12msah4l1XU7NIBAul222Wbahc3EgY/KVBBIXAO0H6%2BlZ%2BrXFr4g1GPRNb1e%2BS4ZhILa3jNuSAp2%0A7mUtnuQAQAeueKdF4O02zjVJZZ7uRCdk18RNIqn%2BFTxgY9Oe%2Bauq0KDb5jcEj5wc/pXOXFlcPa7I%0ArgWoHzCSOFfkx3GSf5VBcaNFeWiCQR3cUuULBDvkI69MYOTnj1qrZqbV/sradaRKmQsNpKqkgcbn%0A3NnNZus67Z%2BHL%2BKW7WeUTofJVAhSJhjPIwT19T161X8QXUVvZT31rYwXF6hXDSBm3AkDGwNz14rU%0AsNI8S6zo0b32lx28pRuJIAoUdsLycdO1WNP8I%2BILS2ZtW161adwDG0EeRjGNo2gH8cVXj8OS2l5u%0Alj1TU4yC37m4jWFMnsGTII7cn61JPovh2G/e4bRrmO4I2GZppJP0jB/wrqdEkstI037PBM8ULSGT%0Aadynkdcnk9O5FQaj4q0y2lhW%2BhvS1w3lwlIS/msewIzz9akaZLiP7QbWWJQPlEjBDjvnI4/EDPai%0A51a3iRYp4Yo5k%2B5E0qbmHoR1Ge3BrGj8WXH2YTx6NdoPMYMkVvI6uQcffYKcdztU4xTbDx9ZJN/x%0ANI4owQRH5bSozPnp86gYwO2a04PHmiySn7Npd5cAIA7xLuVfTcxx%2BddDD4l0NXAaaJyF3%2BZHAxQj%0Ap1Ge9eZeKrm61C9trKy8Uu1qw8wf2fYyyTK3IKuU68HgEj3FSWOkR29jOl1qviGeQvtCNARn2A5x%0A15GT2rMK3UNzAkfjyOytlf8Aex3TxLKCCD9xTkHr1INdLNrNvDDcT2urQy288k1xLELcSoVbnGcj%0Aj73596rWvjPSZLeO4GpJcIRw0qlBFuAGCu5sYHGAwHtVC5SLUJ7TUrPXZFlRHETR26ShVJ427%2BFH%0AHbmquiaqLdFfVNXlufNRiPIspI1Qc85EeXJPU8D3NbP9qQwWST6fLcqxhaVA0agM4BPLFcuv%2Byc4%0A9a4HxBqF5qt3phvZ45Zlsk%2BZFIX5iW4yBnr9PSu00Ga90bwwtwtzAFlYSrA9qWyA4X7%2B4Y49Aa5n%0A4nRIL7SrdYLWCTy2neOG2EW3cRtB4BJwM966zwr9ntfCEH2i1tbmMXKAJKhyN7KhIYHjr6flWjqM%0Aaab8QNIhs0FvCbOZmjiJCtgkZIz6Vtr4dFz4xi8QfbLcxpboqIrbjuwQen1%2BldDcPaPIXFwojUjE%0AgxxtI68Efn61nNeizYxeUZFyWUvjoTwBjt6Z5rm5pYBayCKIqXiI3ElzgjqB61UtWuDZ26fPIylj%0AGTa%2BW4BxkDuP/r1m2/hprXxPd6ldaZe%2BbI4aJhMsQZCgDDDKSxz37Yrpry6s7e3Fy/gSS7eAZKym%0AO4KDuwP0HNJb%2BIm1%2B2kC%2BE7qODAIFzbIEkyeAN5yT7CuevtR0zw5N9rvPB91BB5pzIjv8hPYchQO%0AcYzVuC6t7sfaLax16wRUJKzzzwI2fcvj8vWtSWOW/sjIYYTZjhiLglgcdDtxg/7xrg7xrnStULWX%0AiGOTT0XJsF1NhJnnhdwb6cVr2euySwCQeGr1Aw3oS/mCQ98oVy31xViPxJo00iRS6lZ2JYfNDLbP%0AGBjPBMgIP4DvVO4vfB8V354nIvioQxxsSjHkZAj2qOvU1bGn3sNpJJpE17phLBnLSLPFt9SFDfq4%0A%2BlaSw6ottsfxJFK7Rnb5duis/wDsiJjnHv7d6oXenazcXVpA9npWpFTvxfGWLYQP7rsQPqBUd/aW%0AwdDPbaCjgjfHab/M98Ecce9MtNH0%2B5uZbeaw1IxugdZJZiIlAH8Klgcf8BPNTQ6Zdxyx2unXWqWV%0Av1gWdhKgPPIQq3XnglaZ/Z2ouUS61%2BRpo2bzUmXymkA5yEVg5%2BgPao7ewlhuAv2LTX%2B0nErx2aly%0AMnu75ycdWOane1iuC1riO0kbJaGWziwUHUBMcD8QKhkm1Swjt3/tGOS0aTeB5SwLjp98FlHbhevp%0AVeDxFbS3K/ab6wTy5flQXCNkd/l5OffC1rLq0asFtNViWENukkOZGZT/AAkbtpPTAJ4qvNreki6i%0AN3ePPKTiLzgzmXnlQgAVVx7n6GuO8YOZfHF7PIxOSn3iTt%2BUcc9h2H5V3ejRz3mgWUq3LxG0h3Lc%0ASLEY4UUk4VGOXY49AOcmvPvFlssmq2t5Ffm%2Bhuo/MR2YFgNxHzbSVB9gePavSvB2lvdeHoBIm6Jm%0ADlm6KQcrj1OQDiuxnj0pLpXnTzLkDyQ7RZY5%2BYrnHyjv%2BFLbzPdSSH/RxZKvySLOC28%2BoAGcDJxk%0A06FtN06dI2kM0sgJCs3L5BJ74PqDQ89tIQ7Wt2%2B4ZUwwBxg9BnFc3DodvNAgt5L/ADsCpP8AZ/lI%0AA4PzBQemartpvilLlN3iK0msFwpea0QP7jaMADHvVTUZmt4SYvEUEeGy0TI6Jx3cxsOMe4qaxudY%0AE8mLCwe0Ub/P0ydpCV7H2%2BjPmrtzrci2bvPeOi7fmS%2BfymbPYN/Fx6HFcXq0VhrtpNBB/aU4ZQvm%0ARy740bIOdzqFUcdBn61n6PofjvTI/P8A7Q8uIdIZJDcKyn%2B8q5XFQ3eg%2BIJ7iS51R4dYih628F2y%0AO4/2Rtz%2BQrT0uEW674NBvNIlYjYDs3H2JyHP1JAqO91fVrUXVxc%2BF5p4YgfNvIJEJAHUsUXaR/nn%0ArVC08cadeAFLWVpYEG0XMcbqvI%2B4c5X/ADxUkvjXTZ5St9KlmF%2BZIhC0%2B76scgf98mrGla14cs7m%0AS8sHtpJ8hi0MciSR/wC6WwPyVafN4z0hpliaaGz8s7gbmNriV8/7RBX/AL6Jptlf%2BEft0%2BoRyLNd%0AvznzmYxg9dqmML%2BABx605vFHh5NRMyPFayxHAjbdG7ZHDFhxn/gX4VPa%2BIrJfOIvPtMk0m5wLtLk%0AKCSejAc5P8Kn61V1O9F5MS2nXlxIR%2B6WGZopRjuFDlu3TCiqEPiGHT1mufsHiQwbv3v2xvtESexB%0AIBP%2B9n6VuaR4gudWgGoQafLDAq%2BXEZF8pF91Knn/AICBVW61LVFgQu32iAy7vszyywbsHIIUDcwP%0AQ5ByKo6j4xuNFul%2B26Xb/v0KoLe6R/LHXBIUN3HG4U%2BW8S9kiit9Nt3kA%2BUNCJCc/wCyR/PNZPnR%0A6Brd9JqGkXflSFCq28YSMHbzkgevYU9PiQIJo5IbKBHiJEaRl4o1X/b6s%2BfqOlU5r9NXuFvUi2K/%0AytgAAt7ADjgiu50oKdBCZ5ETAH2INeeW10JLLR7XYzPHGQPQlnOB7V728lpouj2OnyuY44o1zc%2BW%0AxBnPBC9wQBgHocnBq2moxEFdLtlkVl2C4lONwONx7tx%2BRP41haxqTW1tFb6dAJpPMBkS3hUomRnJ%0AYjbjoePfpTr%2B3F/pzXOoXkxNugDqkYjaQAfMTjqh6/LjjrmqNh4c0W5ga4N7qkJlcvs%2B0SRAfRSc%0A49M9qe%2Bh6NJN5tr4jumhwB5EGsDPfJBJJx7HFWpb7QJTBarcxblGFW7kUjIx96Un5votUb3S7K/0%0Au4jGnPPGw2NNBL5YGf7vLZ/75NUbXwn4at2KWSMk6t/q50dp3HcgqSwHvtWmTaFaXNy7Khsr1j%2B5%0AeW4wEb/aRvMZh9QPwq0mg%2BJ4Y/PutZt5t3Wb%2Bz4pI1HQ4wc4PqMVz%2BtvqVpaT3FlrNjLKn7z7JGp%0AIfH%2ByoKtx0BNZ1jq3i69H%2Bk%2BF4GhOBl4mtlHuqlgv5LWrcXnixcwixvHtVOWhtpFLBf99t20fTFU%0ArHV4NQuJl/4RjVrhoCVmZys4XHUMX%2BX19K3bvVruztAIvDMdvD1R1tSq4/2VX5SfzrnL3xR4T1BV%0AsL/SbmGRSN6vaRhs9f4Sj/me9dPap4d02xSWPw5cxxSRhgDbGAy%2Bm8nPy%2B1ZEuo%2BDL5pZr2LRbWf%0A7rW5tyZB/wAC2hF/AE1Lpll4PihkTT2s8y8PJaSvM4HZMyISSfRQo96y9bt7O3uJZl8N7nVOl1a7%0Aeg4yqjOcdyT9K5m28Y2dhujg0AWYb/WfZLponbvy5BYD2BArodM8S/2urCxsLh3wIxDM4lTOOTgK%0AGY9eWY1XupfEaTO1nYxagIeJozGk0cXHGVU4U/hVG617xHawrqt5ocfB2pftHJmPttRyxC%2BnHNad%0Avf3d9BHBF5pe4IcxozOzsR3JJY/yqjqtuNMuoP7Z8PXl3EgYhNzRhTx1wDn6ZFT2/jfTd3z3N9Am%0Af%2BPMQJHbkf7WzLN/P3roY7q0TTisUKbn5Isd9pC3HBKqSzn3JFcn44v3u9LtRLDEpjlCpsjUYGDx%0An7x%2BpJrL0szjR4jbqHX7R8%2BR0O31rv8Aw94j8PWtgo1O6uTKkhUW0CLvYDBySTgDnHrxU8vhkXd6%0ANWtdNe20Z9hgUODPHGBndjnA64/Diuqvtcd1i0%2B0sZZL%2BUK8VwqSBdhBwzgjBHGcj61ens7iUxD%2B%0A0Lu3cIN0iMAnHLHDA59AG469%2Baksre3k82FLi5mDosZkZ88dioU4X8ADUsNra3LMFQttGS4f1bHA%0ABOACvANXhJaR5Dzx5PP8K/oa86tvARF41zZ6l5vl5Aikgy5yPWMso/HFUL7wXrF%2BsbMILcAkYmc9%0A/XAIH4ms%2BHwNr9tdB4WtQqHJkjvFVSPYnGelWNO0/wAaWpmjsEvbO2dv3jl/JjY9MnP3vwBrYtU8%0AXwOIJdchNuEOYyCnmE9AuYxuOfSsrWIdWsU/tC/%2Bz3Oz/ljcT7%2BPdMggfgKsaZ4t1q5id7XwzBLb%0Aovz/AGVZIkHvuBx%2Btbl/4q1mw05ZYtPuLeLylJVI2cAY5ClgQO/OK5z/AITvQ2ZHudM1ETA5YyzJ%0AIc%2Bo8xcL%2BC1rr47t5bb7ZGs08KsVSCcJgnj%2BI7mx7LtFY7ePrOK6aXUrW5Vpzlf7OcRH/gTHLenR%0Alq7pnj3QFZpreRbe6d/uS2aIG93m/eSMe3UfUU/UPGllp9tcXFrA0tyw3TXNuXtkb0B%2BYu4%2BrL9K%0Aw18X6F4nsRb6s9lZpHyIXtyXnOerTYO39a2dO1aO1tPJ0270Q2rjCafp04ifdjAaSdmUg/QE8dqr%0AS65Z6fp7Wtvw8hLzWtjcsId3q0pHmSH1wce9cvqevWOoNajxHFdT2ULYigs2WILjsSQSR75yfWrt%0An470C0XybWPUrK1U5S1tYo0jc%2BshyWcfU5963LXWbXUdLEoWK5ilO6NHtkhjiwTn5F%2B8fdjWZfT6%0AFqMb6fq%2Bri3C7XECpsyOoCtjYmfpWppeoWkAVbK70ZbHGwWNtMDcS8Yw0rMCBx1GfpV63jtrfTHj%0AQS6PcSvzb6bdBy/vJKRkHngZbHtXP%2BO7vz/CBhFrEiRFAsjDzJm%2Bbq0rfM354pdNRXNskjFUUKrE%0A9MACpvEPhg60tobezvBYLKXuJ4I94UbT90fxHPYZ/CofCXhC8R/9Ltp7fS1yzGZGRzkcNjuenTrk%0A9MV6VZnw7YSwzfZkgldAFDRKd3GcBu%2BeDjvito3TmJhaSxIZFDGWWH5evTAA7A9enp3qK%2BiuUWIQ%0AzxeYpJiR4QUz0BDD7uCeTzwcVHZQM0fzWhjYSFCrxjLEEnrzx0IH06VIbSaWVnmEhaQM6Kf4fUqc%0AcHnHqeaikhsoSolKxjcIw%2B0ktnhQSSee3v6U%2BKxikTzYLCymVyWLyTZYn9axTdao67ZfCt9FLEN6%0AyiQyKp7diV/DFYmp694ght5C0VzFGuWZfLcZ78u2WA/GskeO5IWC/wBkxKT1aKd1L/Vjlj%2BBFW9P%0A8WQXCzTWum/Zp0KqzrdOWYdeWGHIz2LYqtd%2BLzJclNVvr2K2bjFjGqsfryOPqTT7XW/CexhbXsVv%0Agbg1xZNPKT/wL5B%2BX51py%2BKrCW2R7k29/HtBVhEWkP8AwIhY1/BDVG11ZL6Y3C6jZaaEbCpLcmW4%0AHoUU4UD6AVc/svR7m%2Bj1O806HU5idonnvPtM8mM4YRLlAPTcafPq9rZCVpZyJyNqwXaR3QQeixoR%0AFHj35rIuFtdTsJ/N0jTLSGQMBfX1vGHHB%2B4qqPrwDz3qlp3gjwpaaUs0kq30jPg3t/M9lEpxn92m%0AMvj1yR9Ku6t4Z8PyWscczX1rBLtLO06ZkHX92gVmI%2Bprz7W/CkbeIYtO8Mw394ske8eft3DkjJIw%0Aqj6n8a6Pw94V8PaTqMCaobjXNUJBW1sU3W8R45kbILgd8ELx1NdxDd6ffatexLe6Zqk0UbZt2slh%0At7dQepO3kDoMEfjWJdLpRtpbb7Bp11K4Y/aGs0URnHSMAZx7tz7CuG0P4canqlsuoXk0en6W33bl%0A1Mhk/wBxF5P44HvXo%2BgaXpej26Rw2N1FaRKSNU1TbsB5OVi4DHPQDdVv/hH7LU9NlvJUs79JSB9s%0A1W08jaPSJVUM3/fRH0rA8ReEvDFr4YvZrfTQ13FC7JdbmiGQuRiMMRj3P5VHpxDWMAZcho0wT24F%0AWdbsrfXNM/s9jcJnZuktrczuMEfwAjIrY0vRLuS4ji0nSGRW%2B9qWsoBsHqkA/TOa7iKO7tIWFnHG%0AZzkRyTkgO2ByR2yc8Cm/bb2GOR70JEzjasMcoJB7njt39ecfTBWC81C9luBZRwwsyrBeCfzGYdn2%0AZIJ5xk4I5rbsobY6dHf22orcO8hjVBIHbfk7hwRk8ZPHA9qp3Osz6dNINXtYLC2DqkF15m9ZZGz8%0Aqjr68kdKbLqTWerIxKma4BijjRMyMMZ2kk4HXOMYqbVtYlsDZvBdW6vIxVY7lTh0Uc7cDOR7Y/So%0ALOWxt70WtrBebncBAkTSrGW5IkfdjPPc8VsiyMyhvttzB22QqoH6g/pxWZfa/Z2Ba10xZbglQvlI%0Anlxg5zkBRvb8TVG9g1i/06S21G%2Bj061dCotyecEdol%2BY/wDAqyNP8KeGrWLzLxrndkbJdUjKRyH/%0AAGIkO9vx4rVu7S001S93dWEibcRwSWqKFXttiRQ4P%2B8wHtXMtbaXq7Pb2fh%2BO8k5PnBGTYO%2BEVjg%0Ae7NWDY/Du5uZyk9/aLIAS1taSrcXGPXYCAB7k1tN4bsolWyube/s0iTaqhhczuev%2BrRMDP8AvDHv%0AXK6h4Os3nnnl1l7U5Gy2lt0kkc%2B4RyF/4Fg1kaX4D8QalEl%2B9uLLTkO77ZcAqpXOMqBlj7YFdf8A%0A2LDfTtDp82pQRrwdRubdI4EPYg7gfyyaoW1v4tu7ub7D4vtrw2qlmuJg/lqB/wBNJI9v05rMsPFG%0Avah4jNndG1vbg5USpbI7kgcFDt/pXXnQr2MtcasZoWbnCoZpmP0B4/Eis680vVYj9psNcl0klApt%0A7mMq04yedqls9cYIFQTL4wsNIkaXU9KWCWM7oZLQRySAc52eWCR7niodA1PUda0pEWFWLOcxWsIU%0AOR/EQo5Puav3MC2DA315FBK3AtwGkf8AEKDiuVv/AA/r2j3TSWV8sVrM%2B6FvtiwOyZ4LIWBUnjgi%0ArN7d%2BOvD0UUmq3t3FGcGNpbkS5z0IGSe1eoQvPeWsU00rTyHHzs2c/n2qr4ptRJ4d1OKFS8n2WTA%0AHJ%2B6eAKpaVoUiaMt3q1yun2EUSu7Sff4Uc47fz9q1rbUtK1G2/snRmvrWebbungtTI2Dg7WyPvYP%0AIyMV1Ok%2BGxpKXKNqE8yumxUkRVXAPG1RjAGVAHsfXi20F3u8q4dFkkBfIByE6Y44DeprMvYf3Pkx%0AuRsQNGku3nnAyXHJyDkn2qldW8lxGrWl7d2kpAUR2YQAH1HGD155PTr3rM0me1urK2sQ9k95ZqwE%0AskIR9hBGM9ckjJ9cHrV2ytdYkhiOsKszrcieEDJwqjGCMZbk9Rxg1r2sZtsxmLy4X%2BS3jjLlo028%0AgnJ2Hg8g4981NG8cyRT29qGiXjdKrHJHUgnB3Y79%2Bc5qVNKtJZJbmWzt47pvlHkTt86ejcAZ9ODi%0Ao5IbqMJsudTi3LkixXzIyfXJB59a4%2B70fxdZXrTaPHN9pHEhtJ0c47ZAPA%2BtZmneIPG8msG1t4y9%0A0HxL51on7o9y74yuAckk5xWzDFrtzeXNrDqmjPqBJLNY7o3dQOvmFf5GsRNL1qC/cwaXbanOPma3%0A%2B0JKD/tMquDVG/8AiCEuGs9V0B7eOJh5lnBdGCMNgdU29/c96SLxVoV9bSxWOnzQAjd5MU4ijI6b%0AXYAO5/HFVbnXbx7QWxneGwjBP2eAlVx1Pck/jmtKx8UeDba0j%2BwNcafdrnNxfW32sjOPuFThT/wG%0ArtvNpbXyXtj4jh1LUcA%2BZqF48EcLdv3fVufU49qraj4gQQyQanLaeIL45CEW2y3tx3wRhpOvoB9a%0A5G71zzriFdUkd9PhPFrbssKKPRVxgfXFakPi3wzB%2B60%2BC/02GUDzntxG8r%2Bu6UtuP04HtWhY6t4e%0AErW2iX19pzzgK05gD3Mp6kb9%2B1Rn0A/GkvdeuIIvs1pPMq9XuJWDzyEjnLgDA9hisWw1XRbWaSPW%0AzekSDH7jBz1zkk5/KrsOsaLPbiztvEUekWiYIhs7SWM/UnqT7sTW1p16kqRW9jrdqLaIHc7Kbq8k%0AyeuWChPbnj3qV7yNbp/7OsYbaXPzTkbpmPqWPT8MVzXjGI3GnxpI53GcEsxzk4PWu1tWeKKG3hQy%0ASBOAoyScelbjaG0emyy6vevYQNG2DCf35yDllAz0pdK8O6fb3cWoXd5LeTxjELXjlvKQggNtwAGI%0AJznJPati7mvJ5C9nIls6owhdpz5bP23Kv3gfzBPbFSw2eoG0ZrrUx5zNkG0h%2B5nkhTJnjryR%2BdMv%0AJbnTrNGtZUCqD5q3E5GDxySO59ff61jQfYr25ur25ZZrhS8W8o2xQCAR8wCk9Oue9OWKLUVhuxKr%0AEsR5vkgRyL0OMg9PUEDnrVPUfDMuo%2BJk1OfWngeGEH7PDEoIwerPyAD%2BeO/WtOF3Ei7LK5mBb55m%0AUbIh65x0%2B7xyfeqNnq%2BojUpFjHm2bttknmk8vyJMkFVXGWzx378HtW1b28c2IztZ/N3YQsyiQL1J%0A7dD146Ux1tZ40uYriI28h2eerhkJ4%2BVm6de1W4NMu449rM6ehM3LDsfv1nz3FzIjC0Sa9ixggqLS%0A2x74wcfUiiC%2Bs9QRLKawlmcH94mmq32WP0Z2YqCfU81iatc6RZCW3%2B0i4Qcm2sE8mJj/ALbjJb9a%0AxLVtU1CKVNMs4rS0PEjQII0x/tytyfxP4Vmf8IJoF9rbvqWs3F3cSlVFnp0DkAgAZZ8Z2%2B4GPeuv%0AttBsrM/YLGPSjGvS10%2BKOSZ8dSzyZPtk569Kbd2GmSSNHqOk6Hp/zEfZ44jPMR6naygEj1IxXN%2BK%0A/AljqenpJ4Z0RNNbzVVrie6ZI9mDuJ3HHp0BNZ%2BleAdFspI/tc99rl2DkxWC%2BXCD6F2G4j3wtdxb%0Az6PZmOxtHnsp5wN1npaCWRvZpVBJ/A8UauLG1iW3u7yNtoyIYYllmz/tSuDg%2B3b0rmtU1WGbSLi1%0AgsrWK3Mb/wDLJWkZipGS5HJ9xiuJ8G%2BAdfurq31G4thZ2QO4SXOVZxj%2BBPvN1%2Bldxe6NaCNLez0a%0A6upAQZLu6nMC/gBwo%2BuTWXqHgrQ9TuYxZwavcXKxgOtvInlIepw7qOOTycVl%2BIPA2k6d4dnvrTWb%0AmW6gi3PA0aMoORwXXrx6A81l%2BAv%2BPi8O4NhQcMePvdq7mF1ind%2BvJOOlUrmbSbdVn1yO6ltkywW2%0AZQxbBzndwRtJ9PrxXbQ38DacT4XtlkMka4nlI3k4BOT0GM9%2BvYVeis5rowSPlbokO0pyJFIX1J4J%0AJ6DpWjY2V9DbPHcvHchQRBNKVZvu9G49sZ569sVoQkwh/kzIykIzR8I2MkbiBxz7ZxUJb7GouL2R%0APM/1eyLLM2T6D/PNV31y3lchFCrKfRmIx3PQjjtjn0rOuoNPNy91dwllX90rNNlQOAfl9s9TzycU%0AQalc6hqVxb2Nvam3ijw115hA8wgj5QQdwGCCpxggDkVNqdjrEcK31jcxw%2BXCROrAfNjo6ZIXPs3H%0AuKzLGyma7%2B3PqGov5ynfCLlGjZzj5sKOCOThcgZrRYXxilW0FlbrHiIrMPNiVsAn5s5yOvQdRx3q%0ASy04xSxvc3UWpTrukS6jiCsCTwoZTjAXjnk9zWg0X%2BiIkCMEONsctudueOT%2BBwSOaoW3h%2B0aLBiE%0AYX5VEF5cOu3HHVgR9MVwUPxL1GeSKLVLOz1CIOMLInl7c8cbePzrT13UtSnRYZ0a2tgMLCiGOM/h%0A0NcourtpV2LhLe2uD2S4Teo98etWrv4jNeshu9ItpNmAE8yRFH0UHA/KrUXjzT7qOO1n02eKJ8qy%0A2U4hU88ZAGW9Mk%2B9QXGtyxpJb6bBFp1u3DLbDazj/ac8n88e1Z4lYMSpJZQWY45%2BprHHjPXolwuq%0AXJAHCs28AduDxU6fEPX0Ro5blJom6xywKV9OQAM1raX4qv7qwfDRQAttb7PCsRcY7kckVFJqFrDI%0Ak2oSSx224K7RKGYfQEgVu22veGkii/sfUrWB2GGn1BGMuf8AZABUfXrTrzRtCv8AbfXWs2%2BtXDEF%0Aka7EUQ92J%2BZh7DFaIS6t5he61rfmoeYtNsdhjIHTc%2BDgewyfeqV54gvL%2BJ4HfyrZgAIIvlTGf1rn%0A9acvoN/GDtQwtwO/%2BcVy/gdv9MvA/wAq7FGcdt1elaP4f1HW33W0QS3J%2BaaThePT1/CuzstG0vSI%0ApYraKK%2BunXY812uUAOOFXnNLb2jQoiCCNCBkxRRqCBjr6D0xV5C1qWWVWcBi2CgPy%2BgP%2BcUya9tl%0ASOK1/clvnPlEkB%2Boz659DxxzVa%2B1OKJ1N3PLFIZgBEEKo5PYEHrxk9ufeo/tjXuop/xLprZIssHk%0AIUOQMEoOr4GMkDHPXiq8t5NpliZpNQhdi52ySERDaSSo2854BHqe1Q%2BbcX0dysjwGIruWPySfnyC%0ASScZAC8e9TxWl2bTzjqcR81QZXWLKkd9iZJXAB5z1%2BtVLWxuJszy6trklmwP%2BiXW1ECnGOxY8Z6/%0AjV95pI4IRDEz7VUKBuO3AwDkncfqTTZPtKRFI4ILaIkAAIrjJIyzdsHJB4984qzHHHaQC0t9MSAR%0AtwtrJHEGIPJGSOvJx3FXLWea4%2BZoGA3fIJI2GMkjGTwG47fXGDWuiSRs6KVChuMlj1AP90%2BtcbD4%0APg8Pj7RpunQRSr01C/nWRh/tKPur%2BAJosGubeW6livdQ1a7KnKyMwtRnjJDHsO/ArGubnThcM%2BtQ%0A6Vfkf8ulnZqArepmGPyGfrXE6vo8%2Bs6og0HQWUOpzFaozIvP8TMcD8xVuy8CW9lOkuv%2BIbCwZSGM%0AEWZnHpkj5R%2Btds/hqXT43nsbK1i2jcLm8czNj%2B8FC4HHOMZqpZJfu8yqt7rk8ind9qiCWy5I7sNw%0AA9yB7Csp9J0WGR5NatNGKnI%2BzabG/mKfUyK20D25rKl%2BHT65cR3mlWw0nSXDeZcX0xZQM8bc8sev%0AA4961IY/D%2BiImiaTocuuXkxAaeXcGkbp8ip90e/5mreseFvCzaNENXe70%2B9xumtLK5W48th2LMOD%0A%2BNczD8KY9VsF1PQ9aEdnkqTqdu0DEgZ%2BXGQ46civPbppdP1G5s5XDS20rRtjJGQcEj8q9G01ydFs%0A8tkCIcjvUinYQTnAPQDk/jUkcNvJF5d1C80DttkjjbazqeoB7H3rc8OaZ4Rivrn%2Bz9C1QXgXm2mc%0ASRhv4Qeeuema6HTfEF5q12IfK%2BxMm5YI5G2qcAfNtxkqPy9K1JdCiY2xknnmMe4sYJBGhPZScZHU%0A8jBqaS/GnxlbidlikY7RGPnZcdM55x7Y/GprWW21DT0niMht54zIpHy4DDrz9ao6gkVxb/2ZPDNN%0Aay4Oza2zcDkZYdDkcc%2BlZDzWSXaSmCNbiQbYp72IkueoXIzn7pPYjApLjU79yzWJEkvTfcBl5JwR%0AnBPqeM8DkVc0iOQWLSX%2B8XMUm4CAmRkPzKQ7DhiepzxSQLJDciM2sMc0rGQTTNhmRT8pxjJPt296%0Au25/tCGSSOaKYfeRophsJ6FQV4HI9/zqO1uIbSOS4ntxY5ch47mUgIR/Fnkc9vX2qY3EInkfz5i3%0ABYK/KgjGQPT2NSRPILlQ9rEsBx5c6zFSf9lk%2BnuRx2pt3BDcmHfNBL%2B9BEMwEqpjg/KOuenU4z0q%0AIaIkVzHJ57mOAMiwxwFFUNzyc7sZySfcDtmtC1tbnM58/VArSEqoukwowOAOw9uaw5Nck0qZ5LjV%0AJ9WuMbfKyBbIenplj9ABXM6xr2oamCJ5ysWflhjG1B%2BA6/jW7pB8HQktdRSy3YXO%2B4G9A3sowD9D%0AmtGBNJ1eYLceJf8ARBwLOKHyEA%2BnTFRyaFLbszaNFpFnGuVN9LP58wHqOPlJ9AKpxfYdEvnn/tG9%0A1W9X5jcXE7CEHH8Man5vxqtJ/bnikO/%2BrsEJzI58qAAd2Pf9aomfQvD6%2BYsa6vqA%2B67qRbxn/ZX%2B%0AL6n9K17LVNXvoTeeMoLG00brHBPARM7YwNig5x65HsK0LCfTdcS4tPCU8FoI1zckW7RscnHLY/TN%0AZEmjaHpTFpUh1e9LZ5XECt6lf4z9eKW7vbm7bfcTFiowBjCqPQAcAV8/eKY2j8WaqjZH%2BlOQR9c5%0A/WvQNE3PoNg3UmFSe/atG2sbi6uEgtkeSV%2BiKM9O9dYulW/hdLa81APdahJMsNrbQqWQTEErvPfG%0ACew46mtTU9EuNYgiSO5RUt8zxkjhpVBxu5yBnPQHjjiryWTrAI1ZXcgFiqgHPGeenX8qpTHVTdNa%0AWgg%2BzKV86a4BcejKFX1GOvfPpUsi3E0jpbPFJcRSAmJ0HIyeQR93Iz14qOfTNXkhuF1We3FrdAIb%0APYzbVwQVLKRxkj7v6VDpUt3Zj92skn2Z22xzR7N%2BDgKDyCu3Bzy358WtKsrCGBo7GBGtZQS4JJ37%0AuSAW6jmpI5fP1Ge3ubKW2W3kVUnKZSXg528dBnr74PpVq0ikgndvPlktyPmRtmCOx4A5/oeelQ3l%0AjZayVS8tIZzEWeJ2BDIOnf1H4e1ZWo%2BGzqDxC1ubnT0g2uklltUN6jHHPPXB6/hWrY2V1FZLbS3C%0AyQgbd1y2%2BaT/AK6cY9cYxjFH9hor7keZ9rEj96XxkY6Hp/8AXPY8TRafGbRUVrWOd1P7yEdGPGRn%0A7w%2BvpinxWqpgzpC7IqqJEXa7kdTgDjkdKlnt0W4nEzbY2XG%2BORkJBwcseMHPHfg9s1pWkkEcbRmF%0AgyNhsFSM4HQk%2BmK8ouBg4IOcZI75rLnHZRke9RMrebyxAI4OOtSpPKkg27OmMsK1NLeWeG4DqE3A%0AAnGMDuKJrj%2ByQLmSGO4AcfupeVbPcitO%2B%2BIWga1ZW1rq9pfRbOT9kcBQf93oR/KtPR9W8GrZyNo9%0A3Ha3hwEn1GIsUbt14HfpUcugW0%2B6/wBZ15NRD52x28uDJ7bj0H0FMnvStolnZxpY2Kfdt4eB9WPV%0Aj7msjziJMbfYfSrG9RGoZsM3IGCa8z8ReCdXutd1G/tbK9uIbqR9pgtllGOPR8g9O2RXbeF/Cd6/%0Ah%2BzfUg2nW0cQ8xpl2vkcEBT0%2BpwPrV%2B11rS7i0uoNO1k6Haplo5/su%2BWdFHzSNux8uTwPbOK7Czt%0AYhpNrG2sfaVZAouVKqZjjO7OT1HNXFiMc6sZAyD%2BADj3Pr61HfWKrYSrcXMlpjAWeAhCuDnqR7Y5%0A4qGSKSJtsExMkgCiLbjI6ZLdfU1ZtkkcKkVgLe2nYMQxG88dWB57H/CkWK3WaKTE9wynbhxsjz0b%0Ap17%2B3FNK28rh1BEnzBVwowenAPQf1qODRVjmlne486dlCRymNUKJ1KhVGPellsYY76GUWyu8abDK%0ASQVXk9e4Pf6VV2SWW5lnSUmXYi52oAx4UAHBbPH1PbpUjW11fXRjjubi3JTDBV4VTnpwV3Z79qtx%0AxRW6bS8kxyFUMwDY4BJzj60W1vuQySW4kkxnekeB82c4H5d6jngZ4v3bxjDkq5zuQjAznI5HPT1F%0APRWtUEMEqxwomfKVeV5/h54Az6Vjalbz6ioWCacQTpIgmikTaHHRjjDE9hisfSbPWLe7t3udfuLq%0A7SNsxJEPLljz8rHtjPGe/HpXZaatyLXbJDb7lbGPspTHAOMAnPXr3riLiHkqD7n3qobAFfMJG0nC%0AjqSaqzRB8DOPmJOefxqtGm7lh07Vs6fCTZSMn8TcA98CsvxEsj6Wr7ySXwf1rjyjMBuwWA6DgGmx%0AK6kYwQcnNdx4VQvp6AtgNIc/pXRzQhlKrg1QltOuTj5gDjr%2BdOTNxN9mj9lDH/PrUPiv4U6rqF//%0AAGnFr0VtEtqNsHknMbBRnkHkE8k9enXFTaXIU0uKXVdSbUpxaqgTayqF%2B7gZ7nH3jknHatSTwXpu%0AqWsJvJL1IiAy2qyqqjjBJwpz34zVrTPDcOgQ3Y8%2Be6iMpn/eldsO7IIQAcDHWtltRtYtPaV2f90m%0A9xt4xj8%2B3asmbUbe8G%2BSaRYJFRmK5IdSAOVI9MVrPaXqMYrRtjE4HzDBAzz0/wA9qoXgkltugZVY%0ArIr8HbnJcMOQQBgY5P48TWcU4AdYgry/MsYbqc8nP45qGa2ea8aBUhVoMCZ5I9xIPUg54J45xVwa%0AZK6W8yTKJIlwHcksQegJ645//XVlFcwyQT4aRAC%2Bw4C5BPB4Pb0qvHFK100EYg%2ByR9eWVlJbpwBx%0A1PXOalDpdIDFIcrl4t%2BdpbJHI6gc9M1G9i9whVZYt6zAsGi%2BQANk4HODjHrzzV%2BK5UyBY185TllZ%0Ahg4HU89/yqvrp8gxzeShhHJZgCOnp6/SsWPX9HkmSZFDoJfvhGUxsQcZ7kdu/Xp3qW%2Bu7SfUIhaW%0Asc8hdTMu5ozt%2B6TkdcZHBPel0/XodcnlstDh82SzP%2BlR3Pyq3zFSoPPOfYjiunt4ZFRjcL%2B8Y52q%0AwIXgcA4Ge/Nf/9k%3D%0A"
    },
    "Header": {
      "En": "Building Blocks for Housing Projects, Israel 1950s",
      "He": u"לבנים למפעל בנייה למגורים, ישראל שנות 1960",
      "En_lc": "building blocks for housing projects, israel 1950s",
      "He_lc": u"לבנים למפעל בנייה למגורים, ישראל שנות 1960"
    },
    "PeriodTypeDesc": {
      "En": "Period|",
      "He": "תקופת צילום|"
    },
    "ForPreview": False,
    "Resolutions": "100|100|100|",
    "LocationCode": "SON.14/276|SON.14/328|SON.14/274|"
  }

FAMILY_NAMES_DERI = {
          "LocationInMuseum" : None,
          "Pictures" : [ ],
          "PictureUnitsIds" : None,
          "UpdateDate" : "2012-11-30T10:21:00",
          "OldUnitId" : "FM016294.HTM",
          "dm_soundex" : [
            "390000"
          ],
          "UpdateUser" : "Haim - Family Names (2012)",
          "UnitDisplayStatus" : 2,
          "PrevPicturePaths" : None,
          "TS" : "000000000001897e",
          "UnitType" : 6,
          "UnitTypeDesc" : "Family Name",
          "EditorRemarks" : "hasavot from Family Names",
          "UnitStatus" : 3,
          "RightsDesc" : "Full",
          "Bibiliography" : {
            "En" : None,
            "He" : None
          },
          "UnitText1" : {
            "En" : "DARI, DERI, DER'I, DEREHA, EDRY, EDERY, EDREHY\r\n\r\nSurnames derive from one of many different origins. Sometimes there may be more than one explanation for the same name. This family name is a toponymic (derived from a geographic name of a town, city, region or country). Surnames that are based on place names do not always testify to direct origin from that place, but may indicate an indirect relation between the name-bearer or his ancestors and the place, such as birth place, temporary residence, trade, or family-relatives.  The family name Deri is associated with the town of Der'a (Draa) in the province of Draa, southern Morocco.  This entire area is one of the oldest sites of Jewish settlement in North Africa, dating from well before the Arab invasions.  The name (and variants) is recorded as a Jewish family name in the following examples:  in the 9th century, Mosheh Ha-Rofe Ben Abraham Edery, who was born in Draa, was a renowned Karaite poet; in the 13th century, Isaac Daray, and his son Jacob, of Barcelona, Spain, are mentioned in a legal document issued by Don Pedro III King of Aragon, dated October 14, 1285; in the 17th century, Mosheh Ben Khoulief Edery was a rabbi in Debdou, Morocco (1607); in the 18th century, Abraham Bar Messod Edery (born 1771?) was a rabbi in Baizza, a village near Marrakech, Morocco; Rabbi Mosheh de Isaac Edrehi from Mogador, Morocco, was a prolific author, kabbalist and professor of languages at Etz Hayyim school in London, England (1792) and in the high school of the Sephardi community of Amsterdam, Holland; Reuben Edery was a rabbi and 'dayan' (\"religious judge\") in Tetouan, Morocco, in 19th century; Rabbi David Edery from Morocco was member of the rabbinical tribunal of Safed, Eretz Israel. His name is mentioned in the introduction to 'Vayomer Yitshak' by Rabbi Isaac Benghalid (1872); David Edery (died 1963 in Tangiers, Morocco) was head of the graduates association of the Alliance Israelite.  In the 20th century, Dari is documented with the Israeli Knesset member Rafael Edry, born 1937 in Casablanca, Morocco; and with Arye Machluf Dari, Knesset member during the 1990s and head of the Shas movement. jews",
            "He" : "DARI, DERI, DER'I, DEREHA, EDRY, EDERY, EDREHY\r\n\r\nשמות משפחה נובעים מכמה מקורות שונים. לעיתים לאותו שם קיים יותר מהסבר אחד. שם משפחה זה הוא מסוג השמות הטופונימיים (שם הנגזר משם של מקום כגון עיירה, עיר, מחוז או ארץ). שמות אלו, אשר נובעים משמות של מקומות, לא בהכרח מעידים על קשר היסטורי ישיר לאותו מקום, אבל יכולים להצביע על קשר בלתי ישיר בין נושא השם או אבותיו לבין מקום לידה, מגורים ארעיים, אזור מסחר או קרובי משפחה.\r\n\r\nשם המשפחה דרעי קשור בשמה של העיירה דרע אשר בעמק הדרע, דרום מרוקו.  איזור זה הוא אחד המקומות העתיקים להתיישבות יהודית בצפון אפריקה, זמן רב לפני הכיבוש הערבי.  שם משפחה זה וצורותיו מתועדים כשמות משפחה יהודיים בדוגמאות הבאות:  במאה ה-9, M משה הרופא בן אברהם אדרעי, אשר נולד בדרע, היה פייטן קראי מפורסם; במאה ה-13, יצחק דראי ובנו יעקוב מברצלוניה, ספרד, מוזכרים במסמך משפטי של דון פדרו ה-3, מלך ארגון, מ-14 באוקטובר 1285; במאה ה-17, משה בן חוליאף אדרי שימש כרב בדבדו, מרוקו (1607); במאה ה-18, אברהם בר מסעוד אדרעי (נולד ב-1771?) שימש כרב בכפר באיזה ליד מרקש, מרוקו;  הרב משה דה יצחק אדרהי ממוגדור, מרוקו, היה מקובל, סופר פורה ומורה לשפות בבית הספר \"עץ חיים\" בלונדון, אנגליה (1792) ובבית הספר של הקהילה הספרדית באמסטרדם, הולנד; הרב ראובן אדרעי היה דיין בטטואן, מרוקו, במאה ה-19; הרב דויד אדרעי ממרוקו היה דיין בבית הדין של צפת, ארץ ישראל: שמו מוזכר במבוא לספר \"ויאמר יצחק\" מאת הרב יצחק בנגליד (1872); דויד אדרעי (נפטר בטנג'יר, מרוקו, בשנת 1963)  שימש כיו\"ר של אגודת בוגרי בתי הספר של \"כל ישראל חברים\" (\"כי\"ח\").\r\n\r\nבמאה ה-20,דרעי מתועד  עם ח\"כ רפאל אדרעי (נולד בקסבלנקה, מרוקו, בשנת 1937); ועם ח\"כ אריה מחלוף דרעי, יו\"ר תנועת ש\"ס בשנות ה-1990. יהודים"
          },
          "UnitText2" : {
            "En" : None,
            "He" : None
          },
          "UnitPlaces" : [ ],
          "DisplayStatusDesc" : "Museum only",
          "PrevPictureFileNames" : None,
          "RightsCode" : 1,
          "UnitId" : 77321,
          "IsValueUnit" : True,
          "StatusDesc" : "Completed",
          "UserLexicon" : None,
          "Attachments" : [ ],
          "Slug" : {
            "En" : "familyname_deri",
            "He" : "שםמשפחה_דרעי"
          },
          "Header" : {
            "En" : "DER'I",
            "He" : "דרעי",

              "En_lc": "der'i",
              "He_lc": "דרעי"
          },
          "ForPreview" : False,
          "Id" : 340727
        }

FAMILY_NAMES_EDREHY = {
          "LocationInMuseum" : None,
          "Pictures" : [ ],
          "PictureUnitsIds" : None,
          "UpdateDate" : "2012-11-30T10:21:00",
          "OldUnitId" : "FM016296.HTM",
          "dm_soundex" : [
            "039500"
          ],
          "UpdateUser" : "Haim - Family Names (2012)",
          "UnitDisplayStatus" : 2,
          "PrevPicturePaths" : None,
          "TS" : "0000000000018980",
          "UnitType" : 6,
          "UnitTypeDesc" : "Family Name",
          "EditorRemarks" : "hasavot from Family Names",
          "UnitStatus" : 3,
          "RightsDesc" : "Full",
          "Bibiliography" : {
            "En" : None,
            "He" : None
          },
          "UnitText1" : {
            "En" : "DARI, DERI, DEREHA, EDRY, EDERY, EDREHY\r\n\r\nSurnames derive from one of many different origins. Sometimes there may be more than one explanation for the same name. This family name is a toponymic (derived from a geographic name of a town, city, region or country). Surnames that are based on place names do not always testify to direct origin from that place, but may indicate an indirect relation between the name-bearer or his ancestors and the place, such as birth place, temporary residence, trade, or family-relatives.  The family name Edrehy is associated with the town of Der'a (Draa) in the province of Draa, south Morocco.  This entire area is one of the oldest sites of Jewish settlement in North Africa, dating from well before the Arab invasions.  The name (and variants) is recorded as a Jewish family name in the following examples:  in the 9th century, Mosheh Ha-Rofe Ben Abraham Edery, who was born in Draa, was a renowned Karaite poet; in the 13th century, Isaac Daray, and his son Jacob, of Barcelona, Spain, are mentioned in a legal document issued by Don Pedro III King of Aragon, dated October 14, 1285; in the 17th century, Mosheh Ben Khoulief Edery was a rabbi in Debdou, Morocco (1607); in the 18th century, Abraham Bar Messod Edery (born 1771?) was a rabbi in Baizza, a village near Marrakech, Morocco; Rabbi Mosheh de Isaac Edrehi from Mogador, Morocco, was a prolific author, kabbalist and professor of languages at Etz Hayyim school in London, England (1792) and in the high school of the Sephardi community of Amsterdam, Holland; Reuben Edery was a rabbi and 'dayan' (\"religious judge\") in Tetouan, Morocco, in 19th century; Rabbi David Edery from Morocco was member of the rabbinical tribunal of Safed, Eretz Israel. His name is mentioned in the introduction to 'Vayomer Yitshak' by Rabbi Isaac Benghalid (1872); David Edery (died 1963 in Tangiers, Morocco) was head of the graduates association of Alliance Israelite.  In the 20th century, Dari is documented with the Israeli Knesset member Rafael Edry, born 1937 in Casablanca, Morocco; and with Arye Machluf Dari, Knesset member during the 1990s and head of the Shas movement.  In the 20th century, Edery is recorded as a Jewish family name with Albert, Marcel, Mordechai, Nissim, Rosa, Annete and Haim Edery, who died in the tragic Egoz incident. The ship Egoz, carrying immigrants from Morocco to Israel, had been chartered by the Jewish underground in Morocco. It sank with the loss of 44 passengers on January 10, 1961.",
            "He" : "DARI, DERI, DEREHA, EDRY, EDERY, EDREHY\r\n\r\nשמות משפחה נובעים מכמה מקורות שונים. לעיתים לאותו שם קיים יותר מהסבר אחד. שם משפחה זה הוא מסוג השמות הטופונימיים (שם הנגזר משם של מקום כגון עיירה, עיר, מחוז או ארץ). שמות אלו, אשר נובעים משמות של מקומות, לא בהכרח מעידים על קשר היסטורי ישיר לאותו מקום, אבל יכולים להצביע על קשר בלתי ישיר בין נושא השם או אבותיו לבין מקום לידה, מגורים ארעיים, אזור מסחר או קרובי משפחה.  שם המשפחה אדרעי קשור בשמה של העיירה דרעה, במחוז דרעה, דרום מרוקו.\r\n\r\nאיזור זה הוא אחד המקומות העתיקים להתיישבות יהודית בצפון אפריקה, זמן רב לפני הכיבוש הערבי.  שם משפחה זה וצורותיו מתועדים כשמות משפחה יהודיים בדוגמאות הבאות:  במאה ה-9, משה הרופא בן אברהם אדרעי, אשר נולד בדרע, היה פייטן קראי מפורסם; במאה ה-13, יצחק דראי ובנו יעקוב מברצלוניה, ספרד, מוזכרים במסמך משפטי של דון פדרו ה-3, מלך ארגון, מ-14 באוקטובר 1285; במאה ה-17, משה בן חוליאף אדרי שימש כרב בדבדו, מרוקו (1607); במאה ה-18, אברהם בר מסעוד אדרעי (נולד ב-1771?) שימש כרב בכפר באיזה ליד מרקש, מרוקו;  הרב משה דה יצחק אדרהי ממוגדור, מרוקו, היה מקובל, סופר פורה ומורה לשפות בבית הספר \"עץ חיים\" בלונדון, אנגליה (1792) ובבית הספר של הקהילה הספרדית באמסטרדם, הולנד; הרב ראובן אדרעי היה דיין בטטואן, מרוקו, במאה ה-19; הרב דויד אדרעי ממרוקו היה דיין בבית הדין של צפת, ארץ ישראל: שמו מוזכר במבוא לספר \"ויאמר יצחק\" מאת הרב יצחק בנגליד (1872); דויד אדרעי (נפטר בטנג'יר, מרוקו, בשנת 1963) שימש כיו\"ר אגודת בוגרי בית הספר \"כל ישראל חברים\" (\"כי\"ח\").\r\n\r\nבמאה ה-20, Dari מתועד  עם ח\"כ רפאל אדרעי (נולד בקסבלנקה, מרוקו, בשנת 1937); ועם ח\"כ אריה מחלוף דרעי, יו\"ר תנועת ש\"ס בשנות ה-1990.\r\n\r\nבמאה ה-20, אדרעי מתועד כשם משפחה יהודי עם אלברט, מסל, מרדכי, נסים, רוזה, אנט וחיים אדרעי, אשר נספו  באסון אניית \"אגוז\".  האוניה \"אגוז\", אשר אורגנה ע\"י המחתרת הציונית במרוקו, הייתה ברכה לישראל עם עולים ממרוקו. האניה \"אגוז\" טבעה בים התיכון ב-10 בינואר 1961 -44 עולים מצאו את מותם באירוע טרגי זה."
          },
          "UnitText2" : {
            "En" : None,
            "He" : None
          },
          "UnitPlaces" : [ ],
          "DisplayStatusDesc" : "Museum only",
          "PrevPictureFileNames" : None,
          "RightsCode" : 1,
          "UnitId" : 77323,
          "IsValueUnit" : True,
          "StatusDesc" : "Completed",
          "UserLexicon" : None,
          "Attachments" : [ ],
          "Slug" : {
            "En" : "familyname_edrehy",
            "He" : "שםמשפחה_אדרהי"
          },
          "Header" : {
            "En" : "EDREHY",
            "He" : "אדרהי",

              "En_lc": "edrehy",
              "He_lc": "אדרהי"
          },
          "ForPreview" : False,
          "Id" : 341018
        }

PERSONALITY_WITH_MISSING_HE_HEADER_AND_SLUG = PERSONALITIES_DAVIDOV = {
          "PeriodDateTypeDesc" : {
            "En" : "Date|Date|",
            "He" : "תאריך מדויק|תאריך מדויק|"
          },
          "FirstName" : {
            "He" : "Karl Yulyevich"
          },
          "Title" : {
            "He" : "Cellist"
          },
          "LocationInMuseum" : None,
          "Pictures" : [ ],
          "PictureUnitsIds" : None,
          "related" : [
            "place_st-petersburg-leningrad-petrograd",
            "place_moscow",
            "place_kuldiga-goldingen"
          ],
          "Expr2" : "דוידוב",
          "Expr1" : "קרל יולייביץ'",
          "UpdateDate" : "2015-02-05T09:04:00",
          "OldUnitId" : "1497",
          "IsMainCreatorType" : "1|0|",
          "PersonTypeCodesDesc" : {
            "En" : "צ'לן|מלחין|",
            "He" : "Cellist|Composer|"
          },
          "NickName" : {
            "He" : None
          },
          "id" : 240792,
          "UpdateUser" : "simona",
          "UnitDisplayStatus" : 2,
          "UnitText2" : {
            "En" : None,
            "He" : None
          },
          "PrevPicturePaths" : None,
          "TS" : "\u0000\u0000\u0000\u0000\u00004ٓ",
          "FamilyNameIds" : None,
          "UnitPlaces" : [
            {
              "PlaceIds" : "70751"
            },
            {
              "PlaceIds" : "70910"
            },
            {
              "PlaceIds" : "72071"
            },
            {
              "PlaceIds" : "73578"
            }
          ],
          "PictureSources" : None,
          "UnitTypeDesc" : "Personality",
          "PeriodStartDate" : "18380315|18890226|",
          "Slug" : {
            "En" : "luminary_davydov-karl-yulyevich"
          },
          "PeriodDateTypeCode" : "2|2|",
          "RightsDesc" : "Full",
          "Bibiliography" : {
            "En" : None,
            "He" : None
          },
          "UnitText1" : {
            "En" : "Davydov, Karl Yulyevich (1838-1889) , cellist and composer. Born in Goldingen, Kurland (Latvia) (then part of the Russian Empire), he first studied mathematics at Moscow University and graduated in 1858. Between 1859-1862 he lived in Leipzig, Germany, where he performed as soloist, chamber musician and principle cellist of the Gewandhaus Orchestra, and taught at the Leipzig Conservatory. In 1862 he returned to Russia, became director of the St. Petersburg Conservatory (1876-1887) and joined the quartet of the Russian Music Society, with Leopold Auer as his partner. He eventually succeeded Anton Rubinstein as conductor of the conservatory’s orchestra, with which he traveled extensively on concert tours abroad. Davydov’s works include many compositions for the cello. He died in Moscow, Russia.",
            "He" : "דוידוב, קרל יולייביץ' (1838-1889) , צ'לן ומלחין. נולד בגולדינגן, קורלנד (לטביה). השלים לימודי מתמטיקה באוניברסיטה של מוסקבה ב-1858. בשנים 1862-1859 התגורר בלייפציג, הופיע כסולן, ניגן בתזמורת הקאמרית והיה צ'לן ראשי של תזמורת הגוואנדהאוס. כמו כן, לימד בקונסרבטוריון של לייפציג. ב-1862 חזר לרוסיה ומונה למנהל הקונסרבטוריון של סנט פטרסבורג (1887-1876) והצטרף לרביעיית האגודה למוסיקה רוסית, שבמסגרתה ניגן יחד עם ליאופולד אאואר. דוידוב ירש את מקומו של אנטון רובינשטיין כמנצח התזמורת של הקונסרבטוריון, ואתה יצא למסע הופעות נרחב בחו\"ל. בין יצירותיו, יצירות רבות לצ'לו. הוא נפטר במוסקבה, רוסיה."
          },
          "PersonTypeIds" : "1|2|",
          "MiddleName" : {
            "He" : None
          },
          "UnitStatus" : 3,
          "LastName" : {
            "He" : "Davydov"
          },
          "PeriodDesc" : {
            "En" : "15/03/1838|26/02/1889|",
            "He" : "15/03/1838|26/02/1889|"
          },
          "PersonTypeCodes" : "130|140|",
          "PrevPictureFileNames" : None,
          "RightsCode" : 1,
          "PeriodTypeCode" : "1|2|",
          "UnitId" : 93968,
          "IsValueUnit" : True,
          "StatusDesc" : "Completed",
          "DisplayStatusDesc" : "Museum only",
          "UserLexicon" : None,
          "EditorRemarks" : "Music - Persons",
          "Attachments" : [ ],
          "PeriodEndDate" : "18380315|18890226|",
          "PeriodNum" : "1|2|",
          "UnitType" : 8,
          "OtherNames" : {
            "He" : None
          },
          "Header" : {
            "En" : "Davydov, Karl Yulyevich",
            "He" : "_"
          },
          "PeriodTypeDesc" : {
            "En" : "Date of birth|Date of death|",
            "He" : "לידה|פטירה|"
          },
          "PersonalityId" : 93968,
          "ForPreview" : False
        }

PERSONALITIES_FERDINAND = {
          "PeriodDateTypeDesc" : {
            "En" : "Date|Date|",
            "He" : "תאריך מדויק|תאריך מדויק|"
          },
          "FirstName" : {
            "He" : "Ferdinand"
          },
          "Title" : {
            "He" : "Violinist"
          },
          "LocationInMuseum" : None,
          "Pictures" : [ ],
          "PictureUnitsIds" : None,
          "related" : [
            "place_hamburg"
          ],
          "Expr2" : "דוד",
          "Expr1" : "פרדיננד",
          "UpdateDate" : "2015-02-05T09:02:00",
          "OldUnitId" : "1496",
          "IsMainCreatorType" : "0|1|",
          "PersonTypeCodesDesc" : {
            "En" : "מלחין|כנר|",
            "He" : "Composer|Violinist|"
          },
          "NickName" : {
            "He" : None
          },
          "id" : 240790,
          "UpdateUser" : "simona",
          "UnitDisplayStatus" : 2,
          "UnitText2" : {
            "En" : None,
            "He" : None
          },
          "PrevPicturePaths" : None,
          "TS" : "\u0000\u0000\u0000\u0000\u00004ك",
          "FamilyNameIds" : None,
          "UnitPlaces" : [
            {
              "PlaceIds" : "71540"
            },
            {
              "PlaceIds" : "98670"
            }
          ],
          "PictureSources" : None,
          "UnitTypeDesc" : "Personality",
          "PeriodStartDate" : "18100119|18730714|",
          "Slug" : {
            "En" : "luminary_david-ferdinand",
            "He" : "אישיות_דוד-פרדיננד"
          },
          "PeriodDateTypeCode" : "2|2|",
          "RightsDesc" : "Full",
          "Bibiliography" : {
            "En" : None,
            "He" : None
          },
          "UnitText1" : {
            "En" : "David, Ferdinand (1810-1873) , violinist and composer. Born in Hamburg, Germany, the son of a wealthy merchant, he studied with the best violin teachers. In 1835 he was appointed concertmaster of the Leipzig Gewandhaus Orchestra under Mendelssohn, who was his life-long friend. In 1845 he premiered Mendelssohn’s Violin Concerto in Leipzig. From 1843 he taught violin at the Leipzig Academy. Among his students were A.Wilhelm and  J. Joachim. David’s compositions include 5 violin concertos, 2 symphonies, the opera HANS WACHT (1852), works for violin and songs. He also arranged several works by J.S.Bach. Ferdinand David died in Klosters, Switzerland. jews",
            "He" : "דוד, פרדיננד (1810-1873) , כנר ומלחין. נולד בהמבורג, גרמניה, כבנו של סוחר עשיר ולמד אצל טובי המורים לכינור. ב-1835 מונה למנהל הקונצרטים של תזמורת הגוואנדהאוס בלייפציג בניצוחו של מנדלסון, שהיה חברו במשך כל חייו. ב-1845 ביצע לראשונה בלייפציג את הקונצ'רטו לכינור מאת מנדלסון. מ-1843 לימד דוד כינור באקדמיה של לייפציג. עם תלמידיו נמנו א' וילהלמי ויוסף יואכים. דוד הלחין, בין היתר, חמישה קונצרטים לכינור, שתי סימפוניות, את האופרה הנס ואכט (1853), יצירות לכינור ושירים. כמו כן, ערך יצירות אחדות מאת יוהן סבסטיאן באך. נפטר בקלוסטר, שווייץ. יהודים"
          },
          "PersonTypeIds" : "1|2|",
          "MiddleName" : {
            "He" : None
          },
          "UnitStatus" : 3,
          "LastName" : {
            "He" : "David"
          },
          "PeriodDesc" : {
            "En" : "19/01/1810|14/07/1873|",
            "He" : "19/01/1810|14/07/1873|"
          },
          "PersonTypeCodes" : "140|248|",
          "PrevPictureFileNames" : None,
          "RightsCode" : 1,
          "PeriodTypeCode" : "1|2|",
          "UnitId" : 93967,
          "IsValueUnit" : True,
          "StatusDesc" : "Completed",
          "DisplayStatusDesc" : "Museum only",
          "UserLexicon" : None,
          "EditorRemarks" : "Music - Persons",
          "Attachments" : [ ],
          "PeriodEndDate" : "18100119|18730714|",
          "PeriodNum" : "1|2|",
          "UnitType" : 8,
          "OtherNames" : {
            "He" : None
          },
          "Header" : {
            "En" : "David, Ferdinand",
            "He" : "דוד, פרדיננד",
              "En_lc": "david, ferdinand",
              "He_lc": "דוד, פרדיננד"
          },
          "PeriodTypeDesc" : {
            "En" : "Date of birth|Date of death|",
            "He" : "לידה|פטירה|"
          },
          "PersonalityId" : 93967,
          "ForPreview" : False
        }

MOVIES_MIDAGES = {
          "ReceiveDate" : None,
          "RelatedSources" : None,
          "VersionTypeCode" : "1|",
          "MovieReceiveTypeDescHebrew" : "הפקת בית התפוצות",
          "LocationInMuseum" : None,
          "Pictures" : [
            {
              "PictureId" : "F11D8D91-B6F1-4693-AAE1-CC74F673F96A",
              "IsPreview" : "1"
            }
          ],
          "PictureUnitsIds" : "1620|",
          "ColorDesc" : {
            "En" : None,
            "He" : None
          },
          "VersionLanguageDesc" : "Hebrew|",
          "UpdateDate" : "2013-10-21T12:31:00",
          "OldUnitId" : "664000001047",
          "id" : 262367,
          "IsPrimaryVersion" : "0|",
          "UpdateUser" : "simona",
          "UnitDisplayStatus" : 2,
          "MoviePath" : "Movies\\B39_h_crop.mpg",
          "PrevPicturePaths" : "Photos\\00000444.scn\\00112000.JPG|",
          "LanguageId" : "1|",
          "TS" : "00000000001748a0",
          "VersionLanguageHebDesc" : "עברית|",
          "CatalogCodes" : "B39_h|",
          "UnitType" : 9,
          "ProductionYear" : None,
          "MovieVersionTypeDescEnglish" : "Hebrew|",
          "UnitTypeDesc" : "Film",
          "RelatedExhibitions" : None,
          "EditorRemarks" : "Hasavot - Movies",
          "RelatedPlaces" : "66070|66654|113054|",
          "DisplayStatusDesc" : "Museum only",
          "RightsDesc" : "Full",
          "FormatDesc" : "Beta-SP-PAL|",
          "Bibiliography" : {
            "En" : None,
            "He" : None
          },
          "UnitText1" : {
            "En" : "The story of the three main Jewish communities in the Middle-Ages:\nThe Jews of Babylonia and Their Spiritual Contribution; \nThe Jews of Spain from Peak to Decline ; \nThe Jews of Ashkenaz in the Shadow of the Cross\n",
            "He" : " סיפורם של שלוש הקהילות הגדולות בימי הביניים.\nיהודי בבל ויצירתם הרוחנית; \nיהודי ספרד -בין גאות ושפל; \nיהודי אשכנז בצל הצלב\n\t"
          },
          "UnitText2" : {
            "En" : None,
            "He" : None
          },
          "SectionHeader" : None,
          "UnitPlaces" : [ ],
          "MovieVersionTypeDescHebrew" : "עברית |",
          "UnitStatus" : 3,
          "SectionEndMinute" : None,
          "FormatId" : "1|",
          "PrevPictureFileNames" : "00112000.JPG|",
          "RightsCode" : 1,
          "UnitId" : 111554,
          "SectionStartMinute" : None,
          "IsValueUnit" : True,
          "StatusDesc" : "Completed",
          "Minutes" : 30,
          "RelatedPersonalitys" : None,
          "MovieFileId" : "d2c835aa-db76-4311-a006-9dace4618b92",
          "UserLexicon" : "56319|56423|93507|93518|93586|",
          "Attachments" : [ ],
          "MovieReceiveTypeDescEnglish" : "Beth Hatefutsoth Production",
          "ColorType" : None,
          "ProductionCompany" : {
            "En" : "Beth Hatefutsoth",
            "He" : "בית התפוצות"
          },
          "SectionId" : None,
          "DistributionCompany" : {
            "En" : None,
            "He" : None
          },
          "Slug" : {
            "En" : "video_jewish-communities-in-the-middle-ages-babylonia-spain-ashkenaz-hebrew",
            "He" : "וידאו_קהילות-יהודיות-בימי-הביניים-בבל-ספרד-אשכנז-עברית"
          },
          "Header" : {
            "En" : "Jewish Communities in the Middle Ages: Babylonia; Spain; Ashkenaz (Hebrew)",
            "He" : "קהילות יהודיות בימי הביניים:  בבל; ספרד; אשכנז (עברית)"
          },
          "VersionId" : "1|",
          "FormatCode" : "1|",
          "RelatedPics" : "1620|",
          "MovieFileName" : "B39_h.mpg",
          "ForPreview" : False,
          "ReceiveType" : 4
        }

MOVIES_SPAIN = {
          "ReceiveDate" : None,
          "RelatedSources" : None,
          "VersionTypeCode" : "2|",
          "MovieReceiveTypeDescHebrew" : "הפקת בית התפוצות",
          "LocationInMuseum" : None,
          "Pictures" : [
            {
              "PictureId" : "0249382A-4DEC-44E2-A36F-6A65549E6D33",
              "IsPreview" : "1"
            }
          ],
          "PictureUnitsIds" : "552|",
          "ColorDesc" : {
            "En" : None,
            "He" : None
          },
          "VersionLanguageDesc" : "English|",
          "UpdateDate" : "2013-10-21T12:31:00",
          "OldUnitId" : "664000001046",
          "id" : 262366,
          "IsPrimaryVersion" : "0|0|",
          "UpdateUser" : "simona",
          "UnitDisplayStatus" : 2,
          "MoviePath" : "Movies\\B38_e_crop.mpg",
          "PrevPicturePaths" : "Photos\\00000706.scn\\00004600.JPG|",
          "LanguageId" : "0|",
          "TS" : "000000000017489c",
          "VersionLanguageHebDesc" : "אנגלית|",
          "CatalogCodes" : "B38_e||",
          "UnitType" : 9,
          "ProductionYear" : 1992,
          "MovieVersionTypeDescEnglish" : "English|",
          "UnitTypeDesc" : "Film",
          "RelatedExhibitions" : None,
          "EditorRemarks" : "Hasavot - Movies",
          "RelatedPlaces" : "113054|",
          "DisplayStatusDesc" : "Museum only",
          "RightsDesc" : "Full",
          "FormatDesc" : "Beta-SP-PAL|Beta-SP-NTSC|",
          "Bibiliography" : {
            "En" : None,
            "He" : None
          },
          "UnitText1" : {
            "En" : "Jewish life in medieval Spain as depicted in Jewish illuminated manuscripts of the time. \nProduced in 1992",
            "He" : "אורחות חיים של היהודים בספרד בימי הביניים, כפי שבאים לידי ביטוי באיורים של כתבי יד מהתקופה. \nהופק ב – 1992. יהודים"
          },
          "UnitText2" : {
            "En" : None,
            "He" : None
          },
          "SectionHeader" : None,
          "UnitPlaces" : [ ],
          "MovieVersionTypeDescHebrew" : "אנגלית|",
          "UnitStatus" : 3,
          "SectionEndMinute" : None,
          "FormatId" : "1|2|",
          "PrevPictureFileNames" : "00004600.JPG|",
          "RightsCode" : 1,
          "UnitId" : 111553,
          "SectionStartMinute" : None,
          "IsValueUnit" : True,
          "StatusDesc" : "Completed",
          "Minutes" : 8,
          "RelatedPersonalitys" : None,
          "MovieFileId" : "47403d87-9271-4ec8-b879-b7cde2ba8f91",
          "UserLexicon" : "49342|49387|49388|",
          "Attachments" : [ ],
          "MovieReceiveTypeDescEnglish" : "Beth Hatefutsoth Production",
          "ColorType" : None,
          "ProductionCompany" : {
            "En" : "Beth Hatefutsoth",
            "He" : "בית התפוצות"
          },
          "SectionId" : None,
          "DistributionCompany" : {
            "En" : None,
            "He" : None
          },
          "Slug" : {
            "En" : "video_living-moments-in-jewish-spain-english",
            "He" : "וידאו_רגעים-עם-יהודי-ספרד-אנגלית"
          },
          "Header" : {
            "En" : "Living Moments in Jewish Spain (English)",
            "He" : "רגעים עם יהודי ספרד (אנגלית)"
          },
          "VersionId" : "1|",
          "FormatCode" : "1|2|",
          "RelatedPics" : "552|",
          "MovieFileName" : "B38_e.mpg",
          "ForPreview" : False,
          "ReceiveType" : 4
        }