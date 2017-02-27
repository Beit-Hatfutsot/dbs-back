from bh_datasets.europeana.dataset import EuropeanaDataset, EuropeanaResults, EuropeanaItem
from ..common.bh_doc import BhDoc
from ..common.mocks import MockRequests, MockJsonResponse


use_mock_requests = True  # you can change to False if you want to make the actual Europeana http request
                          # this should only be used for local testing because we can't be sure they will always
                          # return the same results


def given_cohen_images_mock_requests():
    requests = MockRequests()
    requests.expect_get(url="http://www.europeana.eu/api/v2/search.json",
                        params={'query': 'cohen', 'rows': 5, 'start': 1, 'wskey': 'End3LH3bn',
                                'qf': 'PROVIDER:"Judaica Europeana" TYPE:IMAGE'},
                        response=MockJsonResponse({"success": True,
                                                   "itemsCount": 5,
                                                   "totalResults": 790,
                                                   "items": [{"title": "Kabalath Chabbath"},
                                                             {}, {}, {}, {}]}))
    return requests


def given_europeana_dataset_object(requests_module=None):
    return EuropeanaDataset(wskey="End3LH3bn", requests_module=requests_module)


def when_searching_for_cohen_images(europeana_dataset):
    return europeana_dataset.source_search(query="cohen", only_images=True, rows=5, start=1)


def assert_results_for_cohen_images(results):
    assert isinstance(results, EuropeanaResults)
    assert results.itemsCount == 5
    assert results.totalResults == 790
    assert isinstance(results.items[0], EuropeanaItem)
    assert results.items[0].title == u'Kabalath Chabbath'
    assert len(results.items) == 5


def assert_bh_docs_for_cohen_images(results):
    bh_doc = results.items[0].get_bh_doc()
    assert isinstance(bh_doc, BhDoc)
    assert bh_doc.title == u'Kabalath Chabbath'


def test_cohen_images():
    requests = given_cohen_images_mock_requests() if use_mock_requests else None
    europeana = given_europeana_dataset_object(requests)
    results = when_searching_for_cohen_images(europeana)
    assert_results_for_cohen_images(results)
    assert_bh_docs_for_cohen_images(results)