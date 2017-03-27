from bh_datasets.europeana.dataset import EuropeanaDataset, EuropeanaResults, EuropeanaItem
from ..common.bh_doc import BhDoc
from ..common.mocks import MockRequests, MockJsonResponse
from .constants import EUROPEANA_WSKEY


use_mock_requests = True  # you can change to False if you want to make the actual Europeana http request
                          # this should only be used for local testing because we can't be sure they will always
                          # return the same results

COHEN_IMAGES_SEARCH_URL = "http://www.europeana.eu/api/v2/search.json"
COHEN_IMAGES_SEARCH_PARAMS = {'query': 'cohen',
                              'rows': 5,
                              'start': 1,
                              'wskey': EUROPEANA_WSKEY,
                              'qf': 'PROVIDER:"Judaica Europeana" TYPE:IMAGE',
                              'profile': 'rich'}
COHEN_IMAGES_SEARCH_RESULT_ITEMS = [{"id": "/09326/7FC7D5A44D10440D527780E04801BE725B292883",
                                     "title": ["Kabalath Chabbath"],
                                     "type": "IMAGE",
                                     "edmIsShownBy": ["https://www.google.co.il/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"]},
                                    {},
                                    {},
                                    {},
                                    {}]

def given_cohen_images_mock_requests():
    requests = MockRequests()
    requests.expect_get(url=COHEN_IMAGES_SEARCH_URL,
                        params=COHEN_IMAGES_SEARCH_PARAMS,
                        response=MockJsonResponse({"success": True,
                                                   "itemsCount": 5,
                                                   "totalResults": 790,
                                                   "items": COHEN_IMAGES_SEARCH_RESULT_ITEMS}))
    return requests


def given_europeana_dataset_object(requests_module=None):
    return EuropeanaDataset(wskey=EUROPEANA_WSKEY, requests_module=requests_module)


def when_searching_for_cohen_images(europeana_dataset):
    return europeana_dataset.source_search(query="cohen", only_images=True, rows=5, start=1)


def assert_results_for_cohen_images(results):
    assert isinstance(results, EuropeanaResults)
    assert results.itemsCount == 5
    assert results.totalResults == 790
    assert isinstance(results.items[0], EuropeanaItem)
    assert results.items[0].title == [u'Kabalath Chabbath']
    assert results.items[0].edmIsShownBy == COHEN_IMAGES_SEARCH_RESULT_ITEMS[0]["edmIsShownBy"]
    assert len(results.items) == 5


def assert_bh_docs_for_cohen_images(items):
    bh_docs = [item.get_bh_doc() for item in items]
    bh_doc = bh_docs[0]
    assert isinstance(bh_doc, BhDoc)
    assert bh_doc.source == "EUROPEANA"
    assert bh_doc.id == COHEN_IMAGES_SEARCH_RESULT_ITEMS[0]["id"]
    assert bh_doc.titles == COHEN_IMAGES_SEARCH_RESULT_ITEMS[0]["title"]
    assert bh_doc.image_links == COHEN_IMAGES_SEARCH_RESULT_ITEMS[0]["edmIsShownBy"]
    assert bh_doc.tags == ["TYPE:IMAGE"]
    return bh_docs


def assert_es_docs_for_cohen_images(bh_docs):
    es_docs = [bh_doc.get_es_doc() for bh_doc in bh_docs]
    assert es_docs[0] == {
        "id": COHEN_IMAGES_SEARCH_RESULT_ITEMS[0]["id"],
        "titles": COHEN_IMAGES_SEARCH_RESULT_ITEMS[0]["title"],
        "image_links": COHEN_IMAGES_SEARCH_RESULT_ITEMS[0]["edmIsShownBy"],
        "tags": ["TYPE:IMAGE"]
    }
    assert "BH_SCRAPE_TIME" in bh_docs[0].get_es_doc(with_current_time=True)


def test_cohen_images():
    requests = given_cohen_images_mock_requests() if use_mock_requests else None
    europeana = given_europeana_dataset_object(requests)
    results = when_searching_for_cohen_images(europeana)
    assert_results_for_cohen_images(results)
    bh_docs = assert_bh_docs_for_cohen_images(results.items)
    assert_es_docs_for_cohen_images(bh_docs)
