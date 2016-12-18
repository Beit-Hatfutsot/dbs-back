#!/usr/bin/env python
import argparse

import pymongo
from zeep import Client

from bhs_api import create_app
from bhs_api.utils import SEARCHABLE_COLLECTIONS
from bhs_api.item import get_collection_id_field, get_item_slug


def parse_args():
    parser = argparse.ArgumentParser(description=
                    'update the slugs from the app db to clearmash items')
    return parser.parse_args()

if __name__ == '__main__':

    args = parse_args()
    app, conf = create_app()
    client = Client("{}/API/V5/Services/WebContentManagement.svc?wsdl"
                    .format(conf.clearmash_url))
    tokens = client.service.GetDocument(15841,
                    _soapheaders={"ClientToken": conf.clearmash_token})
    import pdb; pdb.set_trace()
