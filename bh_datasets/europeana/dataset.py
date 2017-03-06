from bh_datasets.common.base import BaseDataset, BaseDatasetItem, BaseDatasetResults
from ..common.bh_doc import BhDoc


class EuropeanaDataset(BaseDataset):

    def __init__(self, wskey, **kwargs):
        super(EuropeanaDataset, self).__init__(**kwargs)
        self.wskey = wskey

    def source_search(self, query, only_images=False, rows=20, start=1):
        # api docs: http://labs.europeana.eu/api/search
        if rows > 100:
            raise Exception("Europeana supports up to 100 rows per request")
        qf = 'PROVIDER:"Judaica Europeana"'
        if only_images:
            qf += " TYPE:IMAGE"
        res = self.requests.get("http://www.europeana.eu/api/v2/search.json",
                                {"wskey": self.wskey, "qf": qf, "query": query, "rows": rows, "start": start,
                                 "profile": "rich"})
        res_json = res.json()
        if not res_json["success"]:
            raise Exception("europeana search failed: {}".format(res_json["error"]))
        else:
            return EuropeanaResults.from_json_search_results(res_json)


class EuropeanaResults(BaseDatasetResults):

    def __init__(self, itemsCount, totalResults, items):
        self.itemsCount = itemsCount
        self.totalResults = totalResults
        self.items = [EuropeanaItem.from_json_search_result(item) for item in items]

    @classmethod
    def from_json_search_results(cls, json_search_results):
        return cls(json_search_results["itemsCount"], json_search_results["totalResults"], json_search_results["items"])


class EuropeanaItem(BaseDatasetItem):

    def __init__(self, item_data):
        self.item_data = item_data

    def __getattr__(self, item):
        return self.item_data.get(item)

    def get_bh_doc(self):
        kwargs = {"titles": self.title,
                  "tags": []}
        if self.type == "IMAGE" and self.edmIsShownBy:
            kwargs["image_links"] = self.edmIsShownBy
            kwargs["tags"].append("TYPE:IMAGE")
        return BhDoc("EUROPEANA", self.id, **kwargs)

    @classmethod
    def from_json_search_result(cls, json_search_result):
        return cls(json_search_result)
