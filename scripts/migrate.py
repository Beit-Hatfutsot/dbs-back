# -*- coding: utf-8 -*-
import re
import os
import sys
import logging
from argparse import ArgumentParser
from decimal import Decimal
import datetime
import calendar
import time
from functools import partial

from pymongo import MongoClient
from pymongo.errors import BulkWriteError
from bson.code import Code

from gedcom import Gedcom, GedcomParseError
from migration.migration_sqlclient import MigrationSQLClient
from migration.tasks import update_row
from migration.files import upload_photo
from migration.family_trees import Gedcom2Persons
from bhs_api.utils import get_conf, create_thumb, get_unit_type
from bhs_api import phonetic
from bhs_api.item import get_collection_id_field


conf = get_conf(set(['queries_repo_path',
                     'sql_server',
                     'sql_user',
                     'sql_password',
                     'collections_to_migrate',
                     'sql_db',
                     'photos_mount_point',
                     'movies_mount_point',
                     'gentree_mount_point',
                     'gentree_bucket_name',
                     'photos_bucket_name',
                     'movies_bucket_name']),
                    os.path.join('/etc/bhs/'
                             'migrate_config.yaml'))

sqlClient = MigrationSQLClient(conf.sql_server, conf.sql_user, conf.sql_password, conf.sql_db)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)-15s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger('scripts.migrate')
logger.setLevel(logging.getLevelName('INFO'))

repeated_slugs = {'He': {}, 'En': {}}

split = lambda x: re.split(',|\||;| ', x)

def parse_args():
    parser = ArgumentParser()
    parser.add_argument('-c', '--collection')
    parser.add_argument('--host', default='localhost')
    parser.add_argument('-s', '--since', default=0)
    parser.add_argument('-u', '--until', default=calendar.timegm(time.localtime()))
    parser.add_argument('-i', '--unitid', type=int,
                        help='migrate a specifc unit/tree id')
    parser.add_argument('-g', '--gedcom_path',
                        help='file path to a gedcom file. works only when -i XXX -c genTrees is used')
    parser.add_argument('--lasthours',
                        help="migrate all content changed in the last LASTHOURS")
    parser.add_argument('--dryrun', help="don't update data, just print what will be done")

    return parser.parse_args()

def get_now_str():
    format = '%d.%h-%H:%M:%S'
    now = datetime.datetime.now()
    now_str = datetime.datetime.strftime(now, format)
    return now_str

def get_queries(collection_name=None, repo_path=conf.queries_repo_path):
    ''' return a dictionary with values of MSSQL query template and filenames
        keys.

        :param collection_name: the name of the collection, if False or missing
                                return the queries for all the collections
        :param repo_path: where all the files are. defaults to the value from
                          the conf file
    '''
    queries = {}

    if repo_path[-1] != '/':
        repo_path = repo_path + '/'

    if collection_name:
        filenames = [collection_name + '.sql']
    else:
        # No single collection specified, migrating all the collections from conf
        filenames = [col_name + '.sql' for col_name in conf.collections_to_migrate]

    for filename in filenames:
        try:
            fh = open(os.path.join(repo_path, filename))
        except IOError:
            logger.error('Could not open file \'{}\' in {}.'.format(filename,
                                                                    os.getcwd())
                        )
            sys.exit(1)

        queries[filename[:-4]] = fh.read()
        fh.close()

    return queries

def make_array(val, to_int=False):
    ''' make an array from a string of values separated by ',', '|' or ' ' '''
    if val == None:
        return []
    else:
        if not to_int:
            return split(val[:-1])
        else:
            try:
                return [int(x) for x in split(val[:-1])]
            except ValueError:
                logger.error('Value error while converting {}'.format(val))
                return []

def make_subdocument_array(doc_arr, key, val_string):
    returned_arr = doc_arr

    if val_string == None:
        return returned_arr
    elif len(val_string) > 10000:
        doc_id = None
        logger.error('Given string is too long for {}!'.format(doc_id))
        return returned_arr

    sub_values = make_array(val_string)
    for i in range(len(sub_values)):
        val = sub_values[i]
        if i >= len(returned_arr):
            returned_arr.append({})
        if is_lang_aware_key(key):
            lang_prefix = key[:2]
            lang_agnostic_key = key[2:]
            if lang_agnostic_key in returned_arr[i]:
                returned_arr[i][lang_agnostic_key][lang_prefix] = val
            else:
                doc = {}
                doc[lang_prefix] = val
                returned_arr[i][lang_agnostic_key] = doc
        else:
            returned_arr[i][key] = val

    return returned_arr

def is_lang_aware_key(key):
    lang_prefix = key[:2]
    if lang_prefix == 'He' or lang_prefix == 'En':
        return True
    return False

def parse_common(doc):
    parsed_doc = {}
    parsed_doc['Attachments']   = []
    parsed_doc['UnitPlaces']    = []
    parsed_doc['Pictures']      = []

    for key, val in doc.items():
        if isinstance(val, Decimal):
            parsed_doc[key] = float(val)
            continue
        elif isinstance(val, str):
            try:
                parsed_doc[key] = val.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    if key == 'TS':
                        parsed_doc[key] = val.encode('hex')
                        continue
                except:
                    logger.warning('failed to migrate key: %s' % key)
            except:
                logger.warning('failed to migrate key: %s' % key)

        if key == 'LexiconIds':
            parsed_doc[key] = make_array(val)
        elif key in ('AttachmentFileName', 'AttachmentPath', 'AttachmentNum'):
            parsed_doc['Attachments'] = make_subdocument_array(
                parsed_doc['Attachments'], key, val)
        elif key in ('PlaceIds', 'PlaceTypeCodes', 'EnPlaceTypeCodesDesc',
                     'HePlaceTypeCodesDesc'):
            parsed_doc['UnitPlaces'] = make_subdocument_array(
                parsed_doc['UnitPlaces'], key, val)
        elif key in ('PictureId', 'IsPreview'):
            parsed_doc['Pictures'] = make_subdocument_array(
                parsed_doc['Pictures'], key, val)
        elif is_lang_aware_key(key):
            lang_prefix = key[:2]
            lang_agnostic_key = key[2:]
            if lang_agnostic_key in parsed_doc:
                try:
                    parsed_doc[lang_agnostic_key][lang_prefix] = val
                except:
                    d = {}
                    d[lang_prefix] = val
                    parsed_doc[lang_agnostic_key] = d
            else:
                d = {}
                d[lang_prefix] = val
                parsed_doc[lang_agnostic_key] = d
        else:
            parsed_doc[key] = val

    return parsed_doc

def parse_image_unit(doc):
    image_unit_doc = parse_common(doc)
    image_unit_doc['PreviewPics']       = []
    image_unit_doc['UnitPersonalities'] = []
    image_unit_doc['UnitPeriod']        = []
    image_unit_doc['Exhibitions']       = []
    if not image_unit_doc.has_key('Pictures'):
        image_unit_doc['Pictures'] = []

    for key, val in doc.items():
        if key in ('IsPreviewPreview', 'PrevPictureId'):
            image_unit_doc['PreviewPics'] = make_subdocument_array(image_unit_doc['PreviewPics'], key, val)
        elif key in ('PersonalityId', 'PersonalityType', 'EnPersonalityTypeDesc', 'HePersonalityTypeDesc', 'PerformerType', 'EnPerformerTypeDesc', 'HePerformerTypeDesc', 'OrderBy'):
            image_unit_doc['UnitPersonalities'] = make_subdocument_array(image_unit_doc['UnitPersonalities'], key, val)
        elif key in ('PicId', 'OldPictureNumber', 'PictureTypeCode', 'EnPictureTypeDesc', 'HePictureTypeDesc', 'Resolution', 'NegativeNumber', 'PictureLocation', 'LocationCode', 'ToScan', 'ForDisplay', 'IsLandscape'):
            image_unit_doc['Pictures'] = make_subdocument_array(image_unit_doc['Pictures'], key, val)
        elif key in ('PeriodNum', 'PeriodTypeCode', 'EnPeriodTypeDesc', 'HePeriodTypeDesc', 'PeriodDateTypeCode', 'EnPeriodDateTypeDesc', 'HePeriodDateTypeDesc', 'PeriodStartDate', 'PeriodEndDate', 'EnPeriodDesc', 'HePeriodDesc'):
            image_unit_doc['UnitPeriod'] = make_subdocument_array(image_unit_doc['UnitPeriod'], key, val)
        elif key in ('ExhibitionId', 'ExhibitionIsPreview'):
            image_unit_doc['Exhibitions'] = make_subdocument_array(image_unit_doc['Exhibitions'], key, val)
        elif key in ('AttachmentFileName', 'AttachmentPath', 'AttachmentNum'):
            image_unit_doc['Attachments'] = make_subdocument_array(image_unit_doc['Attachments'], key, val)
        elif key in ('SourceIds', 'PIctureReceived'):
            # REALLY PIctureReceived?!
            image_unit_doc[key] = make_array(val)

    return image_unit_doc

def parse_image(doc):
    image_doc = doc.copy()

    # create thumbnail and attach to document
    thumb_binary = create_thumb(image_doc, conf.photos_mount_point)
    if thumb_binary:
        image_doc['bin'] = thumb_binary

    return image_doc


def parse_person(doc):
    indi_doc = {}
    for key, val in doc.items():
        if key in ('BIRT_PLAC', 'MARR_PLAC', 'DEAT_PLAC'):
            indi_doc[key] = val
            if val:
                indi_doc[key + '_lc'] = val.lower()
            else:
                indi_doc[key + '_lc'] = val
        elif key in ['MSD', 'MED']:
            indi_doc[key] = make_array(val, to_int=True)
        elif key =='name':
            indi_doc[key] = val
            indi_doc['name_lc'] = map(unicode.lower, val)
            indi_doc['name_S'] = map(phonetic.get_bhp_soundex, val)
        else:
            indi_doc[key] = val
        if key in ('BIRT_PLAC', 'MARR_PLAC', 'DEAT_PLAC'):
             indi_doc[key + '_S'] = phonetic.get_bhp_soundex(val)

    return indi_doc

def parse_identity(doc):
    return doc

def parse_synonym(doc):
    parsed = {}
    parsed['_id'] = doc['SynonymKey']
    if doc['LanguageCode'] == 0:
        parsed['lang'] = 'En'
    else:
        parsed['lang'] = 'He'
    parsed['s_group'] = doc['Num']
    parsed['str'] = doc['Synonym']
    parsed['str_lc'] = doc['Synonym'].lower()

    return parsed

def parse_doc(doc, collection_name):
    collection_procedure_map = {
        'places':               parse_common,
        'familyNames':          parse_common,
        'lexicon':              parse_common,
        'photoUnits':           parse_image_unit,
        'photos':               parse_image,
        'persons':              parse_person,
        'synonyms':             parse_synonym,
        'personalities':        parse_common,
        'movies':               parse_common,
    }
    return collection_procedure_map[collection_name](doc)


def parse_n_update(row, collection_name, dryrun=False):
    doc = parse_doc(row, collection_name)
    id_field = get_collection_id_field(collection_name)
    logger.info('{}:Updating {}: {}, updated {}'.format(
        collection_name, id_field, doc[id_field],
        doc.get('UpdateDate', '?')))
    if not dryrun:
        update_row.delay(doc, collection_name)
    return doc


def get_file_descriptors(tree, gedcom_path):
    ''' returns both the file_id and the full file name of the gedcom file '''
    if not gedcom_path:
        gedcom_path = tree['GenTreePath']
    file_id = os.path.split(gedcom_path)[-1].split('.')[0]
    file_name = os.path.join(conf.gentree_mount_point,
                             gedcom_path)
    return file_id, file_name


def migrate_trees(cursor, treenum=None, gedcom_path=None, on_save=None, dryrun=False):
    count = 0

    for row in cursor:
        if treenum:
            if row['GenTreeNumber'] != treenum:
                continue
        file_id, file_name = get_file_descriptors(row, gedcom_path)
        try:
            gedcom_fd = open(file_name)
        except IOError, e:
            logger.error('failed to open gedocm file tree number {}, path {}: {}'
                         .format(row['GenTreeNumber'], file_name, str(e)))
            continue

        try:
            g = Gedcom(fd=gedcom_fd)
        except (SyntaxError, GedcomParseError) as e:
            logger.error('failed to parse tree number {}, path {}: {}'
                         .format(row['GenTreeNumber'], file_name, str(e)))
            continue
        logger.info('>>> migrating tree {}, path {}'
                    .format(row['GenTreeNumber'], file_name))
        if not on_save:
            on_save = partial(parse_n_update, dryrun=dryrun)
        elif dryrun:
            raise Exception("dryrun is not supported with on_save")
        Gedcom2Persons(g, row['GenTreeNumber'], file_id, on_save)
        logger.info('<<< migrated tree {}, path {}'
                    .format(row['GenTreeNumber'], file_name))
        count += 1
    return count


if __name__ == '__main__':
    args = parse_args()
    until = int(args.until)

    since_file = None
    if not args.since:
        if args.lasthours:

            past = datetime.datetime.now() -\
                    datetime.timedelta(hours=int(args.lasthours))
            since = calendar.timegm(past.timetuple())
        else:
            try:
                since_file = open('/var/run/bhs/last_update', 'r+')
                since = since_file.read()
                since = int(since) + 1
            except IOError:
                since_file = None
                since = 0
    else:
        since = int(args.since)

    collection = args.collection
    queries = get_queries(collection)
    logger.info('looking for changed items in {}-{}'.format(since, until))
    photos_to_update = []
    for collection_name, query in queries.items():
        if collection_name == 'genTrees':
            tree_nums = [args.unitid] if args.unitid else None
            sql_cursor = sqlClient.execute(query, since=since, until=until)
            count = migrate_trees(sql_cursor, args.unitid, args.gedcom_path, dryrun=args.dryrun)
            if not count:
                logger.info('{}:Skipping'.format(collection_name))

            continue

        if args.unitid:
            sql_cursor = sqlClient.execute(query, unit_ids=[args.unitid])
        else:
            sql_cursor = sqlClient.execute(query, since=since, until=until)

        if sql_cursor:
            for row in sql_cursor:
                doc = parse_n_update(row, collection_name, dryrun=args.dryrun)
                # collect all the photos
                pictures = doc.get('Pictures', None)
                if pictures:
                    for pic in pictures:
                        if 'PictureId' in pic:
                            photos_to_update.append(pic['PictureId'])
        else:
            logger.warn('failed getting updated units {}:{}'
                        .format(collection_name, ','.join(units)))

        # TODO:
        # rsync_media(collection_name)

    # update photos
    if len(photos_to_update) > 0:
        photos_query = get_queries('photos')['photos']
        photos_cursor = sqlClient.execute(photos_query,
                                          unit_ids=photos_to_update,
                                          )
        for row in photos_cursor:
            upload_photo(row, conf, dryrun=args.dryrun)

    if since_file and not args.dryrun:
        since_file.seek(0)
        since_file.write(str(until))
        since_file.close()
    logger.info("closing sql connection...")
    sqlClient.close_connections()
