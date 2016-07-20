# -*- coding: utf-8 -*-
import re
import urllib

import elasticsearch
from werkzeug.exceptions import NotFound, Forbidden
from flask import current_app

import phonetic
from bhs_common.utils import get_unit_type, SEARCHABLE_COLLECTIONS
from bhs_api.utils import uuids_to_str

SHOW_FILTER = {
                'StatusDesc': 'Completed',
                'RightsDesc': 'Full',
                'DisplayStatusDesc':  {'$nin': ['Internal Use']},
                '$or':
                    [{'UnitText1.En': {'$nin': [None, '']}}, {'UnitText1.He': {'$nin': [None, '']}}]
                }


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
        "person": "genTreeIndividuals",
        u"אדם": "genTreeIndividuals",
        "familyname": "familyNames",
        u"שםמשפחה": "familyNames",
        "video": "movies",
        u"וידאו": "movies",
    }
    def __init__(self, slug):
        self.full = slug
        collection, self.local_slug = slug.split('_')
        self.collection = self.slugs_collection_map[collection]

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

def fetch_items(slug_list, db=None):
                
    if not db:
        db = current_app.data_db

    rv = []
    for slug in slug_list:
        try:
            item = fetch_item(slug, db)
            rv.append(item)
        except (Forbidden, NotFound) as e:
            rv.append({'slug': slug, 'error_code': e.code, 'msg': e.description})
    return rv


def fetch_item(slug, db=None):
    """
    Gets an item based on slug and returns it
    If slug is bad or item is not found, raises an exception.

    """
    if not db:
        db = current_app.data_db

    try:
        slug = Slug(slug)
    except ValueError:
        raise NotFound, "missing an underscore in item's slug"
    except KeyError:
        raise NotFound, "bad collection name in slug"

    #TODO: handle ugc
    if slug.collection == 'ugc':
        item = dictify(Ugc.objects(id=_id).first())
        if item:
            item = enrich_item(item, db)
            item_id = item['_id']
            item = item['ugc'] # Getting the dict out from  mongoengine
            item['_id'] = item_id
            if type(item['_id']) == dict and '$oid' in item['_id']:
                item['_id'] = item['_id']['$oid']
            return _make_serializable(item)
        else:
            raise NotFound
    else:
        item = get_item(slug, db)
        item = enrich_item(item, db)
        return _make_serializable(item)
        return item

def enrich_item(item, db):
    if not 'thumbnail' in item.keys():
        item['thumbnail'] = _get_thumbnail(item)
    if not 'main_image_url' in item.keys():
        try:
            main_image_id = [image['PictureId'] for image in item['Pictures'] if image['IsPreview'] == '1'][0]
            item['main_image_url'] = get_image_url(main_image_id)
        except (KeyError, IndexError):
            item['main_image_url'] = None
    video_id_key = 'MovieFileId'
    if video_id_key in item:
        # Try to fetch the video URL
        video_id = item[video_id_key]
        video_url = get_video_url(video_id, db)
        if video_url:
            item['video_url'] = video_url
        else:
            return {}
            #abort(404, 'No video URL was found for this movie item.')
    if 'Slug' not in item and 'GTN' in item:
        item['Slug'] = {'En': 'person_{}.{}'.format(item['GTN'], item['II'])}

    return item


def get_item_by_id(id, collection, db=None):
    if not db:
        db = current_app.data_db
    query = {"_id": id}
    return _filter_doc(query, collection, db)

def get_item_query(slug):
    if isinstance(slug, basestring):
        slug = Slug(slug)
    first = slug.full[0]
    if slug.full.startswith('person_'):
        try:
            tree, id = slug.local_slug.split('.')
            return {'GTN': int(tree), 'II': id}
        except ValueError:
            raise NotFound, "Bad person slug - "+slug.local_slug
    else:
        if first >= 'a' and first <='z':
            return {'Slug.En': slug.full}
        else:
            return {'Slug.He': slug.full}

def get_item(slug, db=None):
    if not db:
        db = current_app.data_db
    '''
    Try to return Mongo _id for the given unit_id and collection name.
    Raise HTTP exception if the _id is NOTFound or doesn't pass the show filter
    and therefore Forbidden.
    '''
    slug_query = get_item_query(slug)
    if slug_query:
        return _filter_doc(slug_query, slug.collection, db)
    else:
        return None

def _filter_doc(query, collection, db):
    search_query = query.copy()
    if collection != 'genTreeIndividuals':
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


def search_by_header(string, collection, starts_with=True, db=None):
    if not db:
        db = current_app.data_db
    if not string: # Support empty strings
        return {}
    if phonetic.is_hebrew(string):
        lang = 'He'
    else:
        lang = 'En'
    string_re = re.escape(string)
    if starts_with:
        header_regex = re.compile(u'^'+string_re, re.IGNORECASE)
    else:
        header_regex = re.compile(u'^{}$'.format(string_re), re.IGNORECASE)
    lang_header = 'Header.{}'.format(lang)
    unit_text = 'UnitText1.{}'.format(lang)
    # Search only for non empty docs with right status
    show_filter = SHOW_FILTER.copy()
    show_filter[unit_text] = {"$nin": [None, '']}
    header_search_ex = {lang_header: header_regex}
    header_search_ex.update(show_filter)
    item = db[collection].find_one(header_search_ex)

    if item:
        item = enrich_item(item, db)
        return _make_serializable(item)
    else:
        return {}

def get_image_url(image_id):
    image_bucket_url = current_app.config['IMAGE_BUCKET_URL']
    collection = current_app.data_db['photos']

    photo = collection.find_one({'PictureId': image_id})
    if photo:
        photo_path = photo['PicturePath']
        photo_fn = photo['PictureFileName']
        if not (photo_path and photo_fn):
            current_app.logger.debug('Bad picture path or filename - {}'.format(image_id))
            return None
        extension = photo_path.split('.')[-1].lower()
        url = '{}/{}.{}'.format(image_bucket_url, image_id, extension)
        return url
    else:
        current_app.logger.debug('photo with UUID {} was not found'.format(image_id))
        return None
