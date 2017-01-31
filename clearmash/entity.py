#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging.config
from datetime import datetime, timedelta

from zeep import Client, xsd
from zeep.helpers import serialize_object
from html2text import html2text

from clearmash.utils import get_clearmash_client
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

    def __init__(self, id=None, slug=None, entity=None):
        if entity:
            self._copy(entity)
        else:
            self.client = get_clearmash_client('WebContentManagement')
            self.get(id, slug)

    def get(self, id=None, slug=None):
        ''' get a specific entity from clearmash.
            Entity can be specified using `id` (==UnitId) or `slug`.
        '''

        if not id and not slug:
            return

        if id:
            r = self.client.service.GetDocument(entityId=id, changeset=0)
            if not r:
                raise self.NotFound('GetDocument failed for id {}'.format(id))
        elif slug:
            # TODO: fix lookup by slug #FAIL
            factory = self.client.type_factory('ns1')
            lookup = factory.LookupDocumentByLocalizedField(
                FieldId='_c6_beit_hatfutsot_bh_base_template_url_slug',
                Value=slug)
            r = self.client.service.LookupDocument(lookup)
            if not r or not r['Entity']:
                raise self.NotFound('GetDocument failed for id {}'.format(id))


        self.xml = r['Entity']
        row = serialize_object(self.xml['Document'])
        self._copy(row)

    def _copy(self, row):
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

        try:
            for v in e['_c6_beit_hatfutsot_bh_base_template_url_slug']['LocalizedString']:
                self.slug[v['ISO6391']] = v['Value']
        except KeyError:
            self.slug = None

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
            raise self.Slugged('set_slug failed because the slug exists')

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
        factory = self.client.type_factory('ns1')
        doc = dict(serialize_object(self.xml['Document']))
        template_reference =  doc.pop('TemplateReference')
        doc['TemplateId'] = template_reference['TemplateId']
        entity = factory.EntitySaveData(Document=doc)
        edit = factory.EditWebDocumentParameters(EntityId=self.id,
                                ApproveCriteria="AllPendingData",
                                DataBaseChangeset=self.changeset,
                                Entity=entity)

        self.client.service.EditDocument(edit)

if __name__ == '__main__':
    # doing a bit of testing
    app, conf = create_app()
    with app.app_context():
        e = CMEntity(15841)
        try:
            e.set_slug({'en':'the_slug', 'he':u'בךה'})
        except e.Slugged:
            pass
        e = CMEntity(slug='the_slug')
