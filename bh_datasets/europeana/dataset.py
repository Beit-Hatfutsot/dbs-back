from bh_datasets.common.base import BaseDataset, BaseDatasetItem, BaseDatasetResults
from ..common.bh_doc import BhDoc
from .constants import EUROPEANA_WSKEY


class EuropeanaDataset(BaseDataset):
    SEARCH_ROWS_LIMIT = 100  # Europeana has a limit of 100 rows for search results

    def __init__(self, wskey=None, **kwargs):
        super(EuropeanaDataset, self).__init__(**kwargs)
        self.wskey = EUROPEANA_WSKEY if not wskey else wskey

    def source_search(self, query, only_images=False, rows=20, start=1):
        super(EuropeanaDataset, self).source_search(query, rows, start)
        # api docs: http://labs.europeana.eu/api/search
        qf = 'PROVIDER:"Judaica Europeana"'
        if only_images:
            qf += " TYPE:IMAGE"
        res = self.requests.get("http://www.europeana.eu/api/v2/search.json",
                                {"wskey": self.wskey, "qf": qf, "query": query, "rows": rows, "start": start,
                                 "profile": "rich"})
        self.logger.debug("got response from url {} with status code {}".format(res.request.url, res.status_code))
        res_json = res.json()
        if not res_json["success"]:
            self.logger.error("got failure response from Europeana: {}".format(res_json))
            raise Exception("europeana search failed: {}".format(res_json["error"]))
        else:
            self.logger.debug("got successfull response from Europeana")
            return EuropeanaResults.from_json_search_results(res_json)


class EuropeanaItem(BaseDatasetItem):
    DATASET_ID = "Europeana"

    def get_bh_doc_kwargs(self):
        kwargs = super(EuropeanaItem, self).get_bh_doc_kwargs()
        kwargs.update({"titles": self.title,
                       "tags": []})
        if self.type == "IMAGE" and self.edmIsShownBy:
            kwargs.update({"image_links": self.edmIsShownBy})
            kwargs["tags"].append("TYPE:IMAGE")
        return kwargs

    def get_dataset_unique_item_id(self):
        return self.id


class EuropeanaResults(BaseDatasetResults):
    HAS_TOTAL_COUNT = True
    HAS_RETURNED_COUNT = True
    SEARCH_RESULTS_TOTAL_COUNT_KEY = "totalResults"
    SEARCH_RESULTS_RETURNED_COUNT_KEY = "itemsCount"
    SEARCH_RESULTS_ITEMS_KEY = "items"
    ITEM_CLASS = EuropeanaItem
