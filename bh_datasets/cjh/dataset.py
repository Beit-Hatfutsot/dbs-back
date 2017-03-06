from bh_datasets.common.base import BaseDataset, BaseDatasetItem, BaseDatasetResults
from ..common.bh_doc import BhDoc


class CjhDataset(BaseDataset):

    def __init__(self, **kwargs):
        super(CjhDataset, self).__init__(**kwargs)

    def source_search(self, query, rows=20, start=1):
        # cjh provides direct access to their solr but only from white-listed IPs
        # http://67.111.179.108:8080/solr/diginew/select/?fl=title,dtype,description,fulllink,thumbnail&rows=5&wt=json&q=david&start=0
        if rows > 100:
            raise Exception("Not sure what the limit is but let's keep it sensible")
        res = self.requests.get("http://67.111.179.108:8080/solr/diginew/select/",
                                {"fl": "title,dtype,description,fulllink,thumbnail",
                                 "rows": rows,
                                 "wt": "json",
                                 "q": query,
                                 "start": start-1})
        res_json = res.json()
        if "docs" not in res_json:
            raise Exception("cjh search failed")
        else:
            return CjhResults.from_json_search_results(res_json)


class CjhResults(BaseDatasetResults):

    def __init__(self, docs):
        self.items = [CjhItem.from_json_search_result(doc) for doc in docs]

    @classmethod
    def from_json_search_results(cls, json_search_results):
        return cls(json_search_results["docs"])


class CjhItem(BaseDatasetItem):

    def __init__(self, item_data):
        self.item_data = item_data

    def __getattr__(self, item):
        # title = list of titles
        # description = list of descriptions
        # dtype = not sure
        # fulllink = url to the item in CJH
        # thumbnail = (optional) url to thumbnail of the item
        return self.item_data.get(item)

    def get_bh_doc(self):
        kwargs = {"titles": self.title,
                  "descriptions": self.description}
        unique_item_id = self.fulllink
        return BhDoc("CJH", unique_item_id, **kwargs)

    @classmethod
    def from_json_search_result(cls, json_search_result):
        return cls(json_search_result)
