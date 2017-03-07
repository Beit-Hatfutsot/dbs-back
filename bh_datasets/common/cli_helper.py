# -*- coding: utf-8 -*-
import logging
from .constants import ALL_DATASET_CLASSES
from importlib import import_module
import sys


class DatasetsCliHelper(object):

    def __init__(self, app, conf, reset_loggers=True):
        self.app = app
        self.conf = conf
        self.logger = logging.getLogger(self.__module__)
        if reset_loggers:
            [logging.root.removeHandler(handler) for handler in tuple(logging.root.handlers)]
            self.stdout_handler = logging.StreamHandler(sys.stdout)
            self.stdout_handler.setFormatter(logging.Formatter("%(name)s:%(lineno)d\t%(levelname)s\t%(message)s"))
            self.stdout_handler.setLevel(logging.DEBUG)
            logging.root.addHandler(self.stdout_handler)
            logging.root.setLevel(logging.DEBUG)

    def run(self, args):
        if args.debug:
            logging.root.setLevel(logging.DEBUG)
        else:
            logging.root.setLevel(logging.INFO)
        if args.search_query:
            self.logger.info("starting search on query {} for all known datasets".format(args.search_query))
            for dataset_class_import in ALL_DATASET_CLASSES:
                dataset_class_import = dataset_class_import.split(".")
                class_name = dataset_class_import[-1]
                self.logger.info("fetching from {}".format(class_name))
                module_name = ".".join(dataset_class_import[:-1])
                dataset_class = getattr(import_module(module_name), class_name)
                try:
                    results = dataset_class().source_search(args.search_query, rows=5, start=1)
                except Exception, e:
                    self.logger.exception(e)
                    self.logger.warn("source_search on dataset class {} raised an exception, continuing with the other sources".format(class_name))
                    results = None
                if results:
                    self.logger.info(results.get_total_results_message())
                    for result in results.items:
                        self.logger.info(result)
        else:
            raise Exception("You must specify a search query")
