import requests


class BaseDataset(object):

    def __init__(self, requests_module=None):
        self.requests = requests if not requests_module else requests_module

    def source_search(self, *args, **kwargs):
        raise NotImplementedError("should be implemented by extending classes to to allow searching the source data directly")


class BaseDatasetItems(object):

    pass


class BaseDatasetItem(object):

    pass
