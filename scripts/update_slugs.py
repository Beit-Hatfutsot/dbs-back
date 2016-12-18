#!/usr/bin/env python
import argparse
import logging.config
from httplib import HTTPConnection # py2

import pymongo
import requests
from zeep import Client, xsd
from zeep.helpers import serialize_object

from bhs_api import create_app
from bhs_api.utils import SEARCHABLE_COLLECTIONS
from bhs_api.item import get_collection_id_field, get_item_slug

logging.config.dictConfig({
    'version': 1,
    'formatters': {
        'verbose': {
            'format': '%(name)s: %(message)s'
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'zeep.transports': {
            'level': 'DEBUG',
            'propagate': True,
            'handlers': ['console'],
        },
    }
})


def parse_args():
    parser = argparse.ArgumentParser(description=
                    'update the slugs from the app db to clearmash items')
    return parser.parse_args()

if __name__ == '__main__':

    args = parse_args()
    app, conf = create_app()

    client = Client("{}/API/V5/Services/WebContentManagement.svc?wsdl"
                    .format(conf.clearmash_url))
    header = xsd.Element(
        '',
        xsd.ComplexType([
            xsd.Element(
                'ClientToken',
                xsd.String()),
        ])
    )
    header_value = header(ClientToken=conf.clearmash_token)
    r = client.service.GetDocument(15841,
                    _soapheaders=[header_value])
    row = serialize_object(r['Entity']['Document'])
    doc = {}
    for k, v in row.items():
        if not k.startswith('Fields_'):
            continue
        for j in v.values()[0]:
            print j
            doc[j['Id']] = doc[j['Value']]
    print doc

    import pdb; pdb.set_trace()

    HTTPConnection.debuglevel = 1

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True
    r = requests.post("{}/API/V5/Services/WebContentManagement.svc/Document/Get"
                    .format(conf.clearmash_url),
                      params={'entityId': 15841},
                      headers={"ClientToken": conf.clearmash_token})
