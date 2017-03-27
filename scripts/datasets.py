#!/usr/bin/env python
from bh_datasets.common.cli_helper import DatasetsCliHelper
from bhs_api import create_app
import argparse


def main():
    parser = argparse.ArgumentParser(description='CLI Helper to manage the datasets')
    parser.add_argument('--search-query', type=str, default='', help='start a search on all datasets using the given query')
    parser.add_argument('--debug', action="store_true", help="show debug logs and enable debug features")
    app, conf = create_app()
    helper = DatasetsCliHelper(app, conf)
    args = parser.parse_args()
    helper.run(args)


if __name__ == "__main__":
    main()
