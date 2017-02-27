import requests


class BaseDataset(object):

    def __init__(self, requests_module=None):
        self.requests = requests if not requests_module else requests_module


class BaseDatasetResults(object):

    pass


class BaseDatasetItem(object):

    pass
