from bh_datasets.common.base import BaseDataset, BaseDatasetItem, BaseDatasetResults
from ..common.bh_doc import BhDoc
from .constants import KNOWN_DTYPES


class CjhDataset(BaseDataset):

    def __init__(self, **kwargs):
        super(CjhDataset, self).__init__(**kwargs)

    def source_search(self, query, rows=20, start=1):
        super(CjhDataset, self).source_search(query, rows, start)
        # cjh provides direct access to their solr but only from white-listed IPs
        # http://67.111.179.108:8080/solr/diginew/select/?fl=title,dtype,description,fulllink,thumbnail&rows=5&wt=json&q=david&start=0
        res = self.requests.get("http://67.111.179.108:8080/solr/diginew/select/",
                                {"fl": "title,dtype,description,fulllink,thumbnail",

                                 # rows is the number of records to return in the request
                                 "rows": rows,

                                 # response format, if param is empty will return in xml format
                                 "wt": "json",

                                 # q defines the query term or terms.it queries a catchall the indexes the entire record fl is the list of returned data fields:
                                 #     title: record title
                                 #     dtype: document type (photographs, lithographs, finding aid, etc.)
                                 #     callnumber: call number of the record
                                 #     description: text description of the record
                                 #     language: language of the artifact/collection/etc.
                                 #     author_create: author/photographer/etc.
                                 #     corpname_create: publisher
                                 #     fulllink: external link to digitized artifact or finding aid
                                 #     repository: holding partner
                                 #     credits: credits
                                 #     rights: legal rights relating to the item/artifact/collection/record
                                 # example search values
                                 #     search for records containing "fish" - q value would be: fish
                                 #     search for records containing "fish and pond" - q value would be: %2Bfish+%2Bpond
                                 #     search for records containing "fish and not pond" - q value would be: %2Bfish+-pond
                                 #     search for records containing "fish or pond" - q value would be: fish+pond
                                 #     search for records containing the exact phrase "New York City" - q value would be: "New+York+City"
                                 "q": query,

                                 # start is the starting record in the results to be returned (starts at 0)
                                 "start": start-1})
        res_json = res.json()
        # {u'responseHeader': {u'status': 0, u'QTime': 2}, u'response': {u'start': 0, u'numFound': 860, u'docs': [...]}}
        if "response" in res_json and "docs" in res_json["response"]:
            return CjhResults.from_json_search_results(res_json["response"])
        else:
            self.logger.error("got failure response from cjh: {}".format(res_json))
            raise Exception("cjh search failed")


class CjhItem(BaseDatasetItem):
    DATASET_ID = "Cjh"

    def get_bh_doc_kwargs(self):
        # known fields:
        #   title = list of titles
        #   description = list of descriptions
        #   dtype = the cateogry of the item
        #   fulllink = url to the item in CJH
        #   thumbnail = (optional) url to thumbnail of the item
        kwargs = super(CjhItem, self).get_bh_doc_kwargs()
        kwargs.update({"titles": self.title,
                       "descriptions": self.description})
        return kwargs

    def get_dataset_unique_item_id(self):
        return self.fulllink

    def __getattr__(self, item):
        val = super(CjhItem, self).__getattr__(item)
        if item == "dtype":
            val = CjhDType(val)
        return val


class CjhResults(BaseDatasetResults):
    HAS_TOTAL_COUNT = True
    HAS_RETURNED_COUNT = False
    SEARCH_RESULTS_TOTAL_COUNT_KEY = "numFound"
    SEARCH_RESULTS_ITEMS_KEY = "docs"
    ITEM_CLASS = CjhItem


class CjhDType(object):

    def __init__(self, dtype):
        self.dtype = dtype

    def is_known_dtype(self):
        if self.dtype in KNOWN_DTYPES:
            return True
        else:
            return False
