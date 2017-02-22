from bh_datasets.europeana.dataset import EuropeanaDataset, EuropeanaItems, EuropeanaItem
from ..common.mocks import MockRequests, MockJsonResponse


use_mock_requests = True  # you can change to False if you want to make the actual Europeana request


def given_cohen_images_mock_requests():
    requests = MockRequests()
    requests.expect_get("http://www.europeana.eu/api/v2/search.json",
                        {'query': 'cohen', 'rows': 5, 'start': 1, 'wskey': 'End3LH3bn',
                         'qf': 'PROVIDER:"Judaica Europeana" TYPE:IMAGE'},
                        MockJsonResponse({"success": True,
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
    assert results.itemsCount == 5
    assert results.totalResults == 790
    assert isinstance(results.items, EuropeanaItems)
    assert isinstance(results.items[0], EuropeanaItem)
    assert results.items[0].title == u'Kabalath Chabbath'
    assert len(results.items) == 5


def test_fetch():
    requests = given_cohen_images_mock_requests() if use_mock_requests else None
    europeana = given_europeana_dataset_object(requests)
    results = when_searching_for_cohen_images(europeana)
    assert_results_for_cohen_images(results)
