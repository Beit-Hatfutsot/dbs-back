# -*- coding: utf-8 -*-
import re
import urllib
import elasticsearch
from werkzeug.exceptions import NotFound, Forbidden
from flask import current_app
from slugify import Slugify
from bhs_api import phonetic
from bhs_api.fsearch import clean_person
from bhs_api.utils import uuids_to_str
from copy import deepcopy
from bhs_api.fsearch import is_living_person
import iso639
import json


SHOW_FILTER = {'StatusDesc': 'Completed',
               'RightsDesc': 'Full',
               'DisplayStatusDesc':  {'$nin': ['Internal Use']},
               '$or': [{'UnitText1.En': {'$nin': [None, '']}},
                       {'UnitText1.He': {'$nin': [None, '']}}]}


SLUG_LANGUAGES_MAP = {
    'places': {'en': 'place', 'he': u'מקום',},
    'familyNames': {'en': 'familyname', 'he': u'שםמשפחה',},
    'lexicon': {'en': 'lexicon', 'he': u'מלון',},
    'photoUnits': {'en': 'image', 'he': u'תמונה',},
    'photos': {'en': 'image', 'he': u'תמונה',},
    'synonyms': {'en': 'synonym', 'he': u'שם נרדף',},
    'personalities': {'en': 'luminary', 'he': u'אישיות',},
    'movies': {'en': 'video', 'he': u'וידאו',},
}

# all 2 letter language codes
KNOWN_LANGS = iso639.languages.part1.keys()

KNOWN_ITEM_LANG_ATTRIBUTES = ['content_html_{lang}', 'slug_{lang}', 'title_{lang}', 'title_{lang}_lc']

KNOWN_ITEM_ATTRIBUTES = ['collection', 'location', 'source', 'source_id', 'main_image_url', 'main_thumbnail_image_url', 'slugs']
for lang in KNOWN_LANGS:
    for attr in KNOWN_ITEM_LANG_ATTRIBUTES:
        KNOWN_ITEM_ATTRIBUTES.append(attr.format(lang=lang))

def get_show_metadata(collection_name, doc):
    if collection_name == "persons":
        return {"deceased": doc.get("deceased"),
                "birth_year": doc.get("birth_year")}
    else:
        if SHOW_FILTER != {'StatusDesc': 'Completed',
                           'RightsDesc': 'Full',
                           'DisplayStatusDesc':  {'$nin': ['Internal Use']},
                           '$or': [{'UnitText1.En': {'$nin': [None, '']}},
                                   {'UnitText1.He': {'$nin': [None, '']}}]}:
            raise Exception("this script has a translation of the show filter, if the mongo SHOW_FILTER is modified, this logic needs to be modified as well")
        else:
            return {"StatusDesc": doc.get('StatusDesc'),
                    "RightsDesc": doc.get('RightsDesc'),
                    "DisplayStatusDesc": doc.get("DisplayStatusDesc"),
                    "UnitText1": doc.get("UnitText1", {})}


def doc_show_filter(collection_name, doc):
    show_metadata = get_show_metadata(collection_name, doc)
    if collection_name == "persons":
        return not is_living_person(show_metadata["deceased"], show_metadata["birth_year"])
    else:
        return bool(show_metadata['StatusDesc'] == 'Completed'
                    and show_metadata['RightsDesc'] == 'Full'
                    and show_metadata['DisplayStatusDesc'] not in ['Internal Use']
                    and (show_metadata["UnitText1"].get("En") or show_metadata["UnitText1"].get("He")))


class Slug:
    slugs_collection_map = {
        "image": "photoUnits",
        u"תמונה": "photoUnits",
        "synonym": "synonyms",
        u"שם נרדף": "synonyms",
        "lexicon": "lexicon",
        u"מלון": "lexicon",
        "personality": "personalities",
        "luminary": "personalities",
        u"אישיות": "personalities",
        "place": "places",
        u"מקום": "places",
        "person": "persons",
        u"אדם": "persons",
        "familyname": "familyNames",
        u"שםמשפחה": "familyNames",
        "video": "movies",
        u"וידאו": "movies",
    }
    def __init__(self, slug):
        self.full = slug
        collection, self.local_slug = slug.split('_')
        self.collection = self.slugs_collection_map[collection]
        # handle the special case of old person slugs that are missing a
        # version
        if self.collection == 'persons':
            if ';' not in self.local_slug:
                t = self.local_slug.split('.')
                if len(t) == 2:
                    self.local_slug = "{};0.{}".format(*t)
                    self.full = "_".join((collection, self.local_slug))

    def __unicode__(self):
        return self.full

def get_item_slug(item):
    slug = item['Slug']
    if 'En' in slug:
        return slug['En']
    else:
        return slug['He']

def _get_picture(picture_id):
    found = current_app.data_db['photos'].find_one({'PictureId': picture_id})
    return found

def _get_thumbnail(doc):
    thumbnail = ''
    path = ''

    try:
        if 'Pictures' in doc.keys():
            for pic in doc['Pictures']:
                if pic['IsPreview'] == '1':
                    picture = _get_picture(pic['PictureId'])
                    thumbnail = picture['bin']
                    if 'PictureFileName' in picture.keys():
                        path = picture['PicturePath']
        elif 'RelatedPictures' in doc.keys():
            for pic in doc['RelatedPictures']:
                if pic['IsPreview'] == '1':
                    picture = _get_picture(pic['PictureId'])
                    thumbnail = picture['bin']
                    if 'PictureFileName' in picture.keys():
                        path = picture['PicturePath']

        return {
            'data': urllib.quote(thumbnail.encode('base-64')),
            'path': urllib.quote(path.replace('\\', '/'))
        }

    except (KeyError, TypeError):
        return {}

def _make_serializable(obj):
    # ToDo: Replace with json.dumps with default setting and check
    # Make problematic fields json serializable
    if obj.has_key('_id'):
        obj['_id'] = str(obj['_id'])
    if obj.has_key('UpdateDate'):
        obj['UpdateDate'] = str(obj['UpdateDate'])
    return obj

def fetch_items(slug_list):
    rv = []
    for slug in slug_list:
        try:
            item = fetch_item(slug)
            rv.append(item)
        except (Forbidden, NotFound) as e:
            rv.append({'slug': slug, 'error_code': e.code, 'msg': e.description})
    return rv


def fetch_item(slug):
    """
    Gets an item based on slug and returns it
    If slug is bad or item is not found, raises an exception.
    """
    try:
        slug = Slug(slug)
    except ValueError as e:
        raise NotFound, "missing an underscore in item's slug: {}".format(e)
    except KeyError as e:
        raise NotFound, "bad collection name in slug: {}".format(e)
    item = get_item(slug)
    if item:
        return item
    else:
        raise NotFound
    #TODO: handle ugc
    # if slug.collection == 'ugc':
    #     item = dictify(Ugc.objects(id=_id).first())
    #     if item:
    #         item = enrich_item(item, db)
    #         item_id = item['_id']
    #         item = item['ugc'] # Getting the dict out from  mongoengine
    #         item['_id'] = item_id
    #         if type(item['_id']) == dict and '$oid' in item['_id']:
    #             item['_id'] = item['_id']['$oid']
    #         return _make_serializable(item)
    #     else:
    #         raise NotFound
    # else:

def hits_to_docs(hits):
    for hit in hits:
        doc = hit["_source"]
        enrich_item(doc)
        yield doc

def html_to_text(html):
    # TODO: write a proper html to text function (or support html content)
    if html:
        return html.replace("<br/>", "\n")
    else:
        return html

def enrich_item(item):
    """
    ensure item has all needed attributes before returning it via API
    :param item: a new ES document
    :return: enriched item
    """
    collection_name = item.get("collection", None)  # all new ES items have collection attribute
    update_slugs(item, collection_name)
    for k,v in item.items():
        if k not in KNOWN_ITEM_ATTRIBUTES:
            del item[k]
        elif k.startswith("content_html_"):
            # convert html to text
            lang = k[13:]
            item["content_text_{}".format(lang)] = html_to_text(v)
            del item[k]
    return item
    # TODO: figure out the best way to handle pictures from the new ES
    # I think it's best to let all the work be done in the pipelines sync and just have image urls
    # see https://github.com/Beit-Hatfutsot/mojp-dbs-pipelines/issues/21
    # pictures = item.get('Pictures', None)
    # if pictures:
    #     main_image_id = None
    #     for image in pictures:
    #         # Add 'PictureUrl' to all images of an item
    #         picture_id = image.get('PictureId', None)
    #         if picture_id:
    #             if item.has_key('bagnowka'):
    #                 image['PictureUrl'] = '{}/{}.jpg'.format(current_app.conf.bagnowka_bucket_url, picture_id)
    #             else:
    #                 image_bucket = current_app.conf.image_bucket
    #                 image['PictureUrl'] = get_image_url(picture_id, image_bucket)
    #
    #         is_preview = image.get('IsPreview', False)
    #         if is_preview == '1':
    #             main_image_id = picture_id
    #
    #     if not main_image_id:
    #         for image in pictures:
    #             picture_id = image.get('PictureId', None)
    #             if picture_id:
    #                 main_image_id = picture_id
    #
    #     if main_image_id:
    #         if item.has_key('bagnowka'):
    #             # For bagnowka, thumbnail_bucket is the same as image_bucket (full sized images) because images are very small as it is
    #             item['main_image_url'] = '{}/{}.jpg'.format(current_app.conf.bagnowka_bucket_url, main_image_id)
    #             item['thumbnail_url'] = '{}/{}.jpg'.format(current_app.conf.bagnowka_bucket_url, main_image_id)
    #         else:
    #             image_bucket = current_app.conf.image_bucket
    #             thumbnail_bucket = current_app.conf.thumbnail_bucket
    #             item['main_image_url'] = get_image_url(main_image_id, image_bucket)
    #             item['thumbnail_url'] = get_image_url(main_image_id, thumbnail_bucket)

    # TODO: figure out how to handle videos
    # see https://github.com/Beit-Hatfutsot/mojp-dbs-pipelines/issues/22
    # video_id_key = 'MovieFileId'
    # if video_id_key in item:
    #     # Try to fetch the video URL
    #     video_id = item[video_id_key]
    #     video_url = get_video_url(video_id, db)
    #     if video_url:
    #         item['video_url'] = video_url
    #     else:
    #         return {}
    #         #abort(404, 'No video URL was found for this movie item.')


def get_item_by_id(id, collection_name, db=None):
    if collection_name == "persons":
        raise Exception("persons collection does not support getting item by id, you need to search person using multiple fields")
    if not db:
        db = current_app.data_db
    id_field = get_collection_id_field(collection_name)
    query = {id_field: id}
    return _filter_doc(query, collection_name, db)

def get_item_query(slug):
    if isinstance(slug, basestring):
        slug = Slug(slug)
    first = slug.full[0]
    # import pdb; pdb.set_trace()
    if first >= 'a' and first <='z':
        return {'Slug.En': slug.full}
    else:
        return {'Slug.He': slug.full}

def get_item(slug):
    body = {"query": {"constant_score": {"filter": {"term": {"slugs": slug.full}}}}}
    results = current_app.es.search(index=current_app.es_data_db_index_name, body=body)
    docs = list(hits_to_docs(results["hits"]["hits"]))
    if len(docs) == 0:
        return None
    elif len(docs) == 1:
        return docs[0]
    else:
        raise Exception("too many hits for slug {}".format(json.dumps(slug.full)))
    # TODO: ensure all below logic is transferred to above new code
    # '''
    # Try to return Mongo _id for the given unit_id and collection name.
    # Raise HTTP exception if the _id is NOTFound or doesn't pass the show filter
    # and therefore Forbidden.
    # '''
    # slug_query = get_item_query(slug)
    # if slug_query:
    #     return _filter_doc(slug_query, slug.collection, db)
    # else:
    #     return None

def _filter_doc(query, collection, db):
    search_query = query.copy()
    if collection != 'persons':
        search_query.update(SHOW_FILTER)
    item = db[collection].find_one(search_query)
    if item:
        if collection == 'movies':
            video_id = item['MovieFileId']
            video_url = get_video_url(video_id, db)
            if not video_url:
                current_app.logger.debug('No video for {}'.format(slug))
                return None
            else:
                return item
        elif collection == 'persons':
            return clean_person(item)
        else:
            return item
    else:
        item = db[collection].find_one(query)
        if item:
            msg = ['filter failed for {}'.format(unicode(query))]
            if item['StatusDesc'] != 'Completed':
                msg.append("Status Description is not 'Completed'")
            if item['RightsDesc'] != 'Full':
                msg.append("The  Rights of the Item are not 'Full'")
            if item['DisplayStatusDesc'] == 'Internal Use':
                msg.append("Display Status is 'Internal Use'")
            if item['UnitText1']['En'] in [None, ''] and \
               item['UnitText1']['He'] in [None, '']:
                msg.append('Empty Text (description) in both Heabrew and English')
            raise Forbidden('\n'.join(msg))
        else:
            raise NotFound

def get_collection_name(doc):
    slug = Slug(get_item_slug(doc))
    return slug.collection

def get_video_url(video_id, db):
    video_bucket_url = current_app.config['VIDEO_BUCKET_URL']
    collection = db['movies']
    # Search only within the movies filtered by rights, display status and work status
    video = collection.find_one({'MovieFileId': video_id,
                                 'RightsDesc': 'Full',
                                 'StatusDesc': 'Completed',
                                 'DisplayStatusDesc': {'$nin': ['Internal Use']},
                                 'MoviePath': {'$nin': [None, 'None']}})
    if video:
        extension = 'mp4'
        url = '{}/{}.{}'.format(video_bucket_url, video_id, extension)
        return url
    else:
        current_app.logger.debug('Video URL was not found for {}'.format(video_id))
        return None


def search_by_header(string, collection, starts_with=True):
    if not string: # Support empty strings
        return {}
    else:
        lang = 'he' if phonetic.is_hebrew(string) else 'en'
        # search for item with the specific title (lower-case)
        body = {"query": {"constant_score": {"filter": {"term": {"title_{}_lc".format(lang): string.lower()}}}}}
        results = current_app.es.search(index=current_app.es_data_db_index_name, body=body)
        docs = list(hits_to_docs(results["hits"]["hits"]))
        if len(docs) == 0:
            return None
        elif len(docs) == 1:
            return docs[0]
        else:
            return {}

def get_image_url(image_id, bucket):
    return  'https://storage.googleapis.com/{}/{}.jpg'.format(bucket, image_id)


def get_collection_id_field(collection_name):
    doc_id = 'UnitId'
    if collection_name == 'photos':
        doc_id = 'PictureId'
    # TODO: remove references to the genTreeIndividuals collection - it is irrelevant and not in use
    elif collection_name == 'genTreeIndividuals':
        doc_id = 'ID'
    elif collection_name == 'persons':
        raise Exception("persons collection does not support plain id field, but a combination of fields")
    elif collection_name == 'synonyms':
        doc_id = '_id'
    elif collection_name == 'trees':
        doc_id = 'num'
    return doc_id

def update_slugs(document, collection_name):
    slugify = None
    for lang, collection_slug in SLUG_LANGUAGES_MAP[collection_name].items():
        title = document.get("title_{}".format(lang), "")
        if title != "":
            slug = document.get("slug_{}".format(lang), "")
            if slug == "":
                if not slugify:
                    slugify = Slugify(translate=None, safe_chars='_')
                document["slug_{}".format(lang)] = slugify('_'.join([collection_slug, title.lower()])).encode("utf8")
    # TODO: figure out what's GTN
    # if 'GTN' in item:
    #     item['Slug'] = {'En': 'person_{}.{}'.format(item['GTN'], item['II'])}

def get_doc_id(collection_name, doc):
    if "source" in doc and "source_id" in doc:
        # new doc
        return "{source}_{source_id}".format(source=doc["source"], source_id=doc["source_id"])
    else:
        # legacy doc
        # TODO: remove this code!
        if collection_name == "persons":
            raise Exception("persons collection items don't have a single doc_id, you must match on multiple fields")
        id_field = get_collection_id_field(collection_name)
        return doc[id_field]
