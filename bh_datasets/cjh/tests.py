from bh_datasets.cjh.dataset import CjhDataset, CjhResults, CjhItem, CjhDType
from ..common.bh_doc import BhDoc
from ..common.mocks import MockRequests, MockJsonResponse


use_mock_requests = True  # you can change to False if you want to make the actual Europeana http request
                          # this should only be used for local testing because we can't be sure they will always
                          # return the same results


COHEN_SEARCH_URL = "http://67.111.179.108:8080/solr/diginew/select/"
COHEN_SEARCH_PARAMS = {"fl": "title,dtype,description,fulllink,thumbnail",
                       "rows": 5,
                       "wt": "json",
                       "q": "cohen",
                       "start": 0}
COHEN_SEARCH_DOCS = [{"thumbnail": "http://url/to/thumbnail/image",
                      "dtype": "Tombstones",
                      "title": ["array", "of", "titles"],
                      "fulllink": "url of the item page in CJH",
                      "description": ["array", "of", "descriptions"]},
                     {"title": ["item can also be without thumbnail url"],
                      "dtype": "Acrylic paintings",
                      "fulllink": "url of the item page in CJH", "description": ["array", "of", "descriptions"]}]


def given_cohen_search_mock_requests():
    requests = MockRequests()
    requests.expect_get(url=COHEN_SEARCH_URL,
                        params=COHEN_SEARCH_PARAMS,
                        response=MockJsonResponse({"docs": COHEN_SEARCH_DOCS}))
    return requests


def given_dataset_object(requests_module=None):
    return CjhDataset(requests_module=requests_module)


def when_searching_for_cohen(dataset):
    return dataset.source_search(query="cohen", rows=5, start=1)


def assert_results_for_cohen_search(results):
    assert isinstance(results, CjhResults)
    assert isinstance(results.items[0], CjhItem)
    assert results.items[0].title == COHEN_SEARCH_DOCS[0]["title"]
    assert len(results.items) == len(COHEN_SEARCH_DOCS)
    assert isinstance(results.items[1].dtype, CjhDType)
    assert results.items[1].dtype.dtype == "Acrylic paintings"
    assert results.items[1].dtype.is_known_dtype() == True


def assert_bh_docs_for_cohen_search(items):
    bh_docs = [item.get_bh_doc() for item in items]
    bh_doc = bh_docs[0]
    assert isinstance(bh_doc, BhDoc)
    assert bh_doc.source == "CJH"
    assert bh_doc.id == COHEN_SEARCH_DOCS[0]["fulllink"]
    assert bh_doc.titles == COHEN_SEARCH_DOCS[0]["title"]
    return bh_docs


def assert_es_docs_for_cohen_search(bh_docs):
    es_docs = [bh_doc.get_es_doc() for bh_doc in bh_docs]
    assert es_docs[0] == {
        "id": COHEN_SEARCH_DOCS[0]["fulllink"],
        "titles": COHEN_SEARCH_DOCS[0]["title"],
        "image_links": None,
        "tags": None
    }
    assert "BH_SCRAPE_TIME" in bh_docs[0].get_es_doc(with_current_time=True)


def test_cohen_search():
    requests = given_cohen_search_mock_requests() if use_mock_requests else None
    europeana = given_dataset_object(requests)
    results = when_searching_for_cohen(europeana)
    assert_results_for_cohen_search(results)
    bh_docs = assert_bh_docs_for_cohen_search(results.items)
    assert_es_docs_for_cohen_search(bh_docs)
