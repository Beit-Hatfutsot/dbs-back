from bh_datasets.europeana.dataset import EuropeanaDataset
from ..common.mocks import MockRequests, MockResponse


class MockRequestsCohenImages(MockRequests):

    def get(self, url, params):
        super(MockRequestsCohenImages, self).get(url, params)
        return MockResponse()


def given_europeana_dataset_object(requests_module):
    return EuropeanaDataset(wskey="End3LH3bn", requests_module=requests_module)


def when_searching_for_cohen_images(europeana_dataset):
    return europeana_dataset.source_search(query="cohen", only_images=True, rows=5, start=1)


def assert_http_request_to_euorpeana_for_cohen_images(requests_module):
    assert requests_module.gets == []


def assert_results_for_cohen_images(results):
    assert results.itemsCount == 5
    assert results.totalResults == 790
    assert results.items[0].title == u'Kabalath Chabbath'
    assert len(results.items) == 5


def test_fetch():
    requests = MockRequestsCohenImages()
    europeana = given_europeana_dataset_object(requests)
    results = when_searching_for_cohen_images(europeana)
    assert_http_request_to_euorpeana_for_cohen_images(requests)
    assert_results_for_cohen_images(results)

    # europeana_dataset = EuropeanaDataset(wskey="End3LH3bn", requests_module=requests)
    # results = europeana_dataset.source_search(query="cohen", only_images=True, rows=5, start=1)
    # assert results.itemsCount == 5
    # assert results.totalResults == 790
    # assert results.items[0].title == u'Kabalath Chabbath'
    # assert len(results.items) == 5
