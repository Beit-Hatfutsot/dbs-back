from bh_datasets.europeana.dataset import EuropeanaDataset


def test_fetch():
    # TODO: test it without depending on actually making a call to europeana
    europeana_dataset = EuropeanaDataset(wskey="End3LH3bn")
    results = europeana_dataset.source_search(query="cohen", only_images=True, rows=5, start=1)
    assert results.itemsCount == 5
    assert results.totalResults == 790
    assert results.items[0].title == u'Kabalath Chabbath'
    assert len(results.items) == 5
