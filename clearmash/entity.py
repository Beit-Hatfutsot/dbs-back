#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging.config
from datetime import datetime, timedelta

from flask import current_app
from zeep import Client, xsd
from zeep.helpers import serialize_object
from html2text import html2text

from bhs_api import create_app

LOGLEVEL='DEBUG'

logging.config.dictConfig({
    'version': 1,
    'formatters': {
        'verbose': {
            'format': '%(name)s: %(message)s'
        }
    },
    'handlers': {
        'console': {
            'level': LOGLEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'zeep.transports': {
            'level': LOGLEVEL,
            'propagate': True,
            'handlers': ['console'],
        },
    }
})

def get_clearmash_client():

    client = Client("{}/API/V5/Services/WebContentManagement.svc?wsdl"
                    .format(current_app.conf.clearmash_url))
    header = xsd.Element(
        '',
        xsd.ComplexType([
            xsd.Element(
                'ClientToken',
                xsd.String()),
        ])
    )
    header_value = header(ClientToken=current_app.conf.clearmash_token)
    return client, header_value


def ticks_to_dt(ticks):
    return datetime(1, 1, 1) + timedelta(microseconds=ticks/10)


class CMEntity():
    ''' a class to hold a clear mash entity and update it '''

    # entity's data, field on init
    title = {}
    description = {}
    slug = {}
    pending_changes = False
    entity_type_id = None
    view_count = None
    is_deleted = None
    update_date = None
    is_archived = None
    community_id = None
    place_type = None
    creation_date = None
    publish_date = None
    from_date = None
    to_date = None
    id = None
    # the lxml representation of the enity
    xml = None

    class Empty(Exception):
        pass

    class NotFound(Exception):
        pass

    class Slugged(Exception):
        pass

    def __init__(self, unit_id):
        client, soapheaders = get_clearmash_client()
        r = client.service.GetDocument(unit_id,
                        _soapheaders=[soapheaders])
        if not r:
            raise self.NotFound('GetDocument failed for id {}'.format(unit_id))
        self.xml = r['Entity']
        row = serialize_object(self.xml['Document'])

        self.changeset = r['Entity']['Changeset']
        # loop on all fields and output the `e` dict 
        e = {}
        for k, v in row.items():
            if not v or not k.startswith('Fields_'):
                continue
            for j in v.values()[0]:
                try:
                    e[j['Id']] = j['Value']
                except KeyError:
                    e[j['Id']] = j['DatasourceItemsIds']

        self.id = e['entity_id']
        self.is_deleted = e['is_deleted']
        self.is_archived = e['is_archived']
        self.view_count = e['EntityViewsCount']
        self.community_id = e['community_id']
        self.publish_date = ticks_to_dt(e['EntityFirstPublishDate']['UtcTicks'])
        self.creation_date = ticks_to_dt(e['entity_creation_date']['UtcTicks'])
        self.update_date = ticks_to_dt(e['EntityLastPublishDate']['UtcTicks'])
        self.entity_type_id = e['entity_type_id']
        self.pending_changes = e['entity_has_pending_changes']

        for v in e['entity_name']['LocalizedString']:
            self.title[v['ISO6391']] = v['Value']

        for v in e['_c6_beit_hatfutsot_bh_base_template_description']['LocalizedString']:
            self.description[v['ISO6391']] = html2text(v['Value'])
        '''
        for v in e['_c6_beit_hatfutsot_bh_base_template_url_slug']['LocalizedString']:
            self.slug[v['ISO6391']] = v['Value']
        '''
        try:
            self.place_type = e['_c6_beit_hatfutsot_bh_place_place_type']['string']
        except KeyError:
            pass
        self.from_date = dict(e['_c6_beit_hatfutsot_bh_base_template_from_date'])
        self.to_date = dict(e['_c6_beit_hatfutsot_bh_base_template_to_date'])

    def set_slug(self, slug):
        ''' set the entity's slug

            :param:slug - a dictionary like {'en': 'slug', 'he': 'סלאג'}
        '''
        if not self.xml:
            raise self.Empty('failed because object is empty')

        if self.slug:
            import pdb; pdb.set_trace()
            raise self.Slugged('failed because object already has a slug')

        self.slug = slug
        parent = self.xml['Document']['Fields_LocalizedText']['LocalizedTextDocumentField']
        parent.append({
                        'Id': '_c6_beit_hatfutsot_bh_base_template_url_slug',
                        'Value': {
                            'LocalizedString': [
                                {'ISO6391': 'en', 'Value': slug['en']},
                                {'ISO6391': 'he', 'Value': slug['he']},
                            ]
                        }
                    })
        client, soapheaders = get_clearmash_client()
        factory = client.type_factory('ns1')
        doc = dict(serialize_object(self.xml['Document']))
        del doc['TemplateReference']
        entity = factory.EntitySaveData(Document=doc)
        edit = factory.EditWebDocumentParameters(EntityId=self.id,
                                                 ApproveCriteria="OnlyNewData",
                                                 DataBaseChangeset=self.changeset,
                                                 Entity=entity)
        r = client.service.EditDocument(edit,
                        _soapheaders=[soapheaders])

if __name__ == '__main__':
    app, conf = create_app()
    with app.app_context():
        e = CMEntity(15841)
        e.set_slug({'en':'some_slug', 'he':u'בךה'})
