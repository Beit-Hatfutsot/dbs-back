import urllib

from werkzeug.exceptions import NotFound, Forbidden

import phonetic
from bhs_common.utils import get_unit_type, SEARCHABLE_COLLECTIONS
from bhs_api import logger, data_db, conf

show_filter = {
                'StatusDesc': 'Completed',
                'RightsDesc': 'Full',
                'DisplayStatusDesc':  {'$nin': ['Internal Use']},
                '$or':
                    [{'UnitText1.En': {'$nin': [None, '']}}, {'UnitText1.He': {'$nin': [None, '']}}]
                }


class Slug:
    slugs_to_collection = {
        'personality': 'personality',
        '%D7%90%D7%99%D7%A9%D7%99%D7%95%D7%AA': 'personality'
    }
    def __init__(self, slug):
        self.full = slug
        collection, self.local_slug = slug.split('.')
        self.collection = self.slugs_to_collection[collection]

    def __unicode__(self):
        return self.full

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

def fetch_items(slug_list, db=data_db):
    '''
    # Fetch 2 items - 1 good and 1 bad
    >>> movie_id = data_db.movies.find_one(show_filter, {'_id': 1})['_id']
    >>> item_id = 'movies.{}'.format(movie_id)
    >>> items = fetch_items([item_id, 'places.00000'])
    >>> len(items)
    2
    >>> int(items[0]['_id']) ==  int(movie_id)
    True
    >>> items[1]['error_code']
    404
    '''

    rv = []
    for slug in slug_list:
        try:
            item = _fetch_item(slug, db)
            rv.append(item)
        except (Forbidden, NotFound) as e:
            rv.append({'slug': slug, 'error_code': e.code, 'msg': e.description})
    return rv


def _fetch_item(slug, db):
    """
    Gets item_id string and return an item
    If item_id is bad or item is not found, raises an exception.

    # A regular non-empty item - setup
    >>> movie_id = data_db.movies.find_one(show_filter, {'_id': 1})['_id']
    >>> item_id = 'movies.{}'.format(movie_id)
    >>> item = _fetch_item(item_id, data_db)
    >>> item != {}
    True

    >>> _fetch_item('unknown.', data_db)
    Traceback (most recent call last):
        ...
    NotFound: 404: Not Found
    >>> _fetch_item('places.00000', data_db)
    Traceback (most recent call last):
        ...
    NotFound: 404: Not Found

    # Item that doesn't pass filter
    >>> bad_filter_id = data_db.movies.find_one({"StatusDesc": "Edit"}, {'_id': 1})['_id']
    >>> bad_filter_item_id = 'movies.{}'.format(bad_filter_id)
    >>> _fetch_item(bad_filter_item_id, data_db)
    Traceback (most recent call last):
        ...
    Forbidden: 403: Forbidden

    """

    try:
        slug = Slug(slug)
    except ValueError:
        raise NotFound, "missing a dot in item's slug"
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
        item = filter_doc_id(slug, db)
        item = enrich_item(item, db)

        return _make_serializable(item)

def enrich_item(item, db):
    if 'related' not in item or not item['related']:
        m = 'Hit bhp related in enrich_item - {}'.format(get_item_name(item))
        logger.debug(m)
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
    return item

def get_text_related(doc, max_items=3):
    """Look for documents in `collections` where one or more of the words
    from the headers (English and Hebrew) of the given `doc` appear inside
    UnitText1 field.
    """
    related = []
    collections = SEARCHABLE_COLLECTIONS
    en_header = doc['Header']['En']
    if en_header == None:
        en_header = ''
    he_header = doc['Header']['He']
    if he_header == None:
        he_header = ''

    for collection_name in collections:
        col = data_db[collection_name]
        headers = en_header + ' ' + he_header
        if headers == ' ':
            # No headers at all - empty doc - no relateds
            return []
        # Create text indices for text search to work:
        # db.YOUR_COLLECTION.createIndex({"UnitText1.En": "text", "UnitText1.He": "text"})
        header_text_search = {'$text': {'$search': headers}}
        header_text_search.update(show_filter)
        projection = {'score': {'$meta': 'textScore'}}
        sort_expression = [('score', {'$meta': 'textScore'})]
        # http://api.mongodb.org/python/current/api/pymongo/cursor.html
        cursor = col.find(header_text_search, projection).sort(sort_expression).limit(max_items)
        if cursor:
            try:
                for related_item in cursor:
                    related_item = _make_serializable(related_item)
                    if not _make_serializable(doc)['_id'] == related_item['_id']:
                        # Exclude the doc iteself from its relateds
                        related_string = collection_name + '.' + related_item['_id']
                        related.append(related_string)
            except pymongo.errors.OperationFailure as e:
                # Create a text index
                logger.debug('Creating a text index for collection {}'.format(collection_name))
                col.ensure_index([('UnitText1.En', pymongo.TEXT), ('UnitText1.He', pymongo.TEXT)])
                continue
        else:
            continue

    return related

def get_es_text_related(doc, items_per_collection=1):
    related = []
    related_fields = ['Header.En', 'UnitText1.En', 'Header.He', 'UnitText1.He']
    collections = SEARCHABLE_COLLECTIONS
    self_collection = get_collection_name(doc)
    if not self_collection:
        logger.info('Unknown collection for document {}'.format(doc['_id']))
        return []
    for collection_name in collections:
        found_related = es_mlt_search(
                                    data_db.name,
                                    doc,
                                    related_fields,
                                    collection_name,
                                    items_per_collection)
        if found_related:
            related.extend(found_related)

    # Filter results
    for item_name in related:
        collection, _id = item_name.split('.')[:2]
        try:
            filter_doc_id(_id, collection)
        except (Forbidden, NotFound):
            continue
        related.append(filtered)
    return related

def get_bhp_related(doc, max_items=6, bhp_only=False, delimeter='|'):
    """
    Bring the documents that were manually marked as related to the current doc
    by an editor.
    Unfortunately there are not a lot of connections, so we only check the more
    promising vectors:
    places -> photoUnits
    personalities -> photoUnits, familyNames, places
    photoUnits -> places, personalities
    If no manual marks are found for the document, return the result of es mlt
    related search.
    """
    # A map of fields that we check for each kind of document (by collection)
    related_fields = {
            'places': ['PictureUnitsIds'],
            'personalities': ['PictureUnitsIds', 'FamilyNameIds', 'UnitPlaces'],
            'photoUnits': ['UnitPlaces', 'PersonalityIds']}

    # A map of document fields to related collections
    collection_names = {
            'PersonalityIds': 'personalities',
            'PictureUnitsIds': 'photoUnits',
            'FamilyNameIds': 'familyNames',
            'UnitPlaces': 'places'}

    # Check what is the collection name for the current doc and what are the
    # related fields that we have to check for it
    rv = []
    self_collection_name = get_collection_name(doc)

    if not self_collection_name:
        logger.debug('Unknown collection')
        return get_es_text_related(doc)[:max_items]
    elif self_collection_name not in related_fields:
        if not bhp_only:
            logger.debug(
                'BHP related not supported for collection {}'.format(
                self_collection_name))
            return get_es_text_related(doc)[:max_items]
        else:
            return []

    # Turn each related field into a list of BHP ids if it has content
    fields = related_fields[self_collection_name]
    for field in fields:
        collection = collection_names[field]
        if field in doc and doc[field]:
            related_value = doc[field]
            if type(related_value) == list:
                # Some related ids are encoded in comma separated strings
                # and others are inside lists
                related_value_list = [i['PlaceIds'] for i in related_value]
            else:
                related_value_list = related_value.split(delimeter)

            for i in related_value_list:
                if not i:
                    continue
                else:
                    i = int(i)
                    try:
                        filter_doc_id(i, collection)
                    except (Forbidden, NotFound):
                        continue
                    rv.append(collection + '.' + i)

    if bhp_only:
        # Don't pad the results with es_mlt related
        return rv
    else:
        # If we didn't find enough related items inside the document fields,
        # get more items using elasticsearch mlt search.
        if len(rv) < max_items:
            es_text_related = get_es_text_related(doc)
            rv.extend(es_text_related)
            rv = list(set(rv))
            # Using list -> set -> list conversion to avoid adding the same item
            # multiple times.
        return rv[:max_items]

def invert_related_vector(vector_dict):
    rv = []
    key = vector_dict.keys()[0]
    for value in vector_dict.values()[0]:
        rv.append({value: [key]})
    return rv

def reverse_related(direct_related):
    rv = []
    for vector in direct_related:
        for r in invert_related_vector(vector):
            rv.append(r)

    return rv

def reduce_related(related_list):
    reduced = {}
    for r in related_list:
        key = r.keys()[0]
        value = r.values()[0]
        if key in reduced:
            reduced[key].extend(value)
        else:
            reduced[key] = value

    rv = []
    for key in reduced:
        rv.append({key: reduced[key]})
    return rv

def unify_related_lists(l1, l2):
    rv = l1[:]
    rv.extend(l2)
    return reduce_related(rv)

def sort_related(related_items):
    '''Put the more diverse items in the beginning'''
    # Sort the related ids by collection names...
    by_collection = {}
    rv = []
    for item_name in related_items:
        collection, _id = item_name.split('.')
        if collection in by_collection:
            by_collection[collection].append(item_name)
        else:
            by_collection[collection] = [item_name]

    # And pop 1 item form each collection as long as there are items
    while [v for v in by_collection.values() if v]:
        for c in by_collection:
            if by_collection[c]:
                rv.append(by_collection[c].pop())
    return rv

def filter_doc_id(slug, db):
    '''
    Try to return Mongo _id for the given unit_id and collection name.
    Raise HTTP exception if the _id is NOTFound or doesn't pass the show filter
    and therefore Forbidden.
    '''
    if slug.full[0].isalpha():
        slug_query = {'Slug.En': slug.full}
    else:
        slug_query = {'Slug.He': slug.full}
    search_query = slug_query.copy()
    search_query.update(show_filter)
    item = db[slug.collection].find_one(search_query)
    if item:
        if slug.collection == 'movies':
            video_id = item['MovieFileId']
            video_url = get_video_url(video_id, db)
            if not video_url:
                logger.debug('No video for {}'.format(slug))
                return None
            else:
                return item
        else:
            return item
    else:
        item = db[slug.collection].find_one(slug_query)
        if item:
            msg = ['filter failed for {}'.format(slug)]
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
    if 'UnitType' in doc:
        unit_type = doc['UnitType']
    else:
        return None
    return get_unit_type(unit_type)

def get_item_name(doc):
    collection_name = get_collection_name(doc)
    item_name = '{}.{}'.format(collection_name, doc['_id'])
    return item_name

def get_video_url(video_id, db):
    video_bucket_url = conf.video_bucket_url
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
        logger.debug('Video URL was not found for {}'.format(video_id))
        return None


def search_by_header(string, collection, starts_with=True, db=data_db):
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
    show_filter[unit_text] = {"$nin": [None, '']}
    header_search_ex = {lang_header: header_regex}
    header_search_ex.update(show_filter)
    item = db[collection].find_one(header_search_ex)

    if item:
        item = enrich_item(item, db)
        return _make_serializable(item)
    else:
        return {}
