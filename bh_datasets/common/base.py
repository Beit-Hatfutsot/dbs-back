import requests
import logging
from .bh_doc import BhDoc


class BaseDataset(object):
    SEARCH_ROWS_LIMIT = 100

    def __init__(self, requests_module=None):
        self.requests = requests if not requests_module else requests_module
        self.logger = logging.getLogger(self.__module__)

    def source_search(self, query, rows=20, start=1):
        if rows > 100:
            raise Exception("You requested too many rows, maximum number of rows is {}".format(self.SEARCH_ROWS_LIMIT))
        if start < 1:
            raise Exception("Start item starts with 1")


class BaseDatasetResults(object):
    # if the data source returns a total items count
    HAS_TOTAL_COUNT = False
    # if the data source returns a count of items returned in a specific request
    HAS_RETURNED_COUNT = False
    # allows for automatic mapping and parsing of json response based on simple json keys
    # for more advanced functionality you will probably want to override the from_json_search_results function
    SEARCH_RESULTS_TOTAL_COUNT_KEY = None
    SEARCH_RESULTS_RETURNED_COUNT_KEY = None
    SEARCH_RESULTS_ITEMS_KEY = None
    # the related item class
    ITEM_CLASS = None

    def __init__(self, returned_results_count, total_results_count, items):
        self.returned_results_count = returned_results_count if self.HAS_RETURNED_COUNT else None
        self.total_results_count = total_results_count if self.HAS_TOTAL_COUNT else None
        self.items = [self.ITEM_CLASS.from_json_search_result(item) for item in items] if self.ITEM_CLASS else None

    @classmethod
    def from_json_search_results(cls, json_search_results):
        """
        parses the json search results as received from the datasource and construct a standard results object
        defaults to use the SEARCH_RESULTS_* attributes to provide simple mapping
        but you can override if more complex functionality is needed
        """
        if cls.HAS_RETURNED_COUNT and cls.SEARCH_RESULTS_RETURNED_COUNT_KEY:
            returned_results_count = json_search_results[cls.SEARCH_RESULTS_RETURNED_COUNT_KEY]
        else:
            returned_results_count = None
        if cls.HAS_TOTAL_COUNT and cls.SEARCH_RESULTS_TOTAL_COUNT_KEY:
            total_results_count = json_search_results[cls.SEARCH_RESULTS_TOTAL_COUNT_KEY]
        else:
            total_results_count = None
        if cls.SEARCH_RESULTS_ITEMS_KEY:
            items = json_search_results[cls.SEARCH_RESULTS_ITEMS_KEY]
        else:
            items = None
        return cls(returned_results_count, total_results_count, items)

    def get_total_results_message(self):
        """
        helper method to get a textual message saying how many results the source reports were received
        the actual count might be different and we don't want to count the actual items to support usage of generators
        this function serves both a functional purpose but also serves as documentation for the getting details
        from the results object
        """
        source_name = self.__class__.__name__
        if self.total_results_count and self.returned_results_count:
            return "dataset source ({}) reports that {} results were returned out of total {} results".format(source_name, self.returned_results_count, self.total_results_count)
        elif self.total_results_count:
            return "dataset source ({}) reports that there are a total of {} results".format(source_name, self.total_results_count)
        elif self.returned_results_count:
            return "dataset source ({}) reports that {} results were returned".format(source_name, self.returned_results_count)
        else:
            return "dataset source ({}) did not report the number of returned or total results".format(source_name)


class BaseDatasetItem(object):
    DATASET_ID = None

    def __init__(self, item_data):
        self.item_data = item_data

    def __getattr__(self, item):
        # extending classes will probably want to extend this to allow normalizing the item data
        # for example, handling encoding / date/time etc..
        return self.item_data.get(item)

    def get_bh_doc_kwargs(self):
        # should be implemented by extending classes to add relevant kwargs to this dict
        # it is then passed as kwargs to the BhDoc class constructor
        return {}

    def get_dataset_unique_item_id(self):
        raise Exception("must be implemented by extending classes")

    def get_bh_doc(self):
        if not self.DATASET_ID:
            raise Exception("extending classes must set the DATASET_ID")
        return BhDoc(self.DATASET_ID, self.get_dataset_unique_item_id(), self.get_bh_doc_kwargs())

    @classmethod
    def from_json_search_result(cls, json_search_result):
        return cls(json_search_result)

    def __str__(self):
        return "{} dataset item id = {}".format(self.DATASET_ID, self.get_dataset_unique_item_id())
