#!/usr/bin/env python
import os
from datetime import datetime
from uuid import UUID
import argparse
import urllib2
from subprocess import call
from ftplib import FTP

import unicodecsv


from bhs_api import create_app
from bhs_api.utils import SEARCHABLE_COLLECTIONS
from bhs_api.item import SHOW_FILTER


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--out', default ='/tmp',
                        help='the directory to store the csvs in. defaults to /tmp')
    parser.add_argument('--debug', action='store_true',
                        help='debug mode, dump only 100 records of each collection')
    parser.add_argument('--db',
                        help='the db to run on defaults to the value in /etc/bhs/config.yml')
    parser.add_argument('--ftp_server',
                        help='the address of the ftp server to push mojp-dump.tgz to')
    parser.add_argument('--ftp_user', default='anonymous')
    parser.add_argument('--ftp_password', default=None)
    parser.add_argument('--ftp_dir', default='incoming',
                        help='the ftp directory where to store the file')
    return parser.parse_args()

def clean(row):
    r = []
    for i in row:
        if isinstance(i, basestring) and i and i[-1] == '|':
            r.append(i[:-1])
        else:
            r.append(i)
    return r

if __name__ == '__main__':

    args = parse_args()
    app, conf = create_app()
    if args.db:
        db = app.client_data_db[args.db]
    else:
        db = app.data_db

    index_name = db.name

    # for collection in SEARCHABLE_COLLECTIONS:
    collections =  ['personalities', 'places', 'familyNames', 'photoUnits']
    for collection in collections:
        outfile = open("{}/{}.csv".format(args.out, collection), "wb")
        writer = unicodecsv.writer(outfile, encoding="utf-8")
        if collection == 'personalities':
            header = ['URL', 'ID', 'Title', 'Type', 'Period', 'Body', 'Places']
        elif collection == 'places':
            header = ['URL', 'ID', 'Title']
        if collection == 'familyNames':
            header = ['URL', 'ID', 'Title', 'Body']
        if collection == 'photoUnits':
            header = ['URL', 'ID', 'Title', 'Period', 'Body', 'Places']

        writer.writerow(header)
        started = datetime.now()
        cursor = db[collection].find(SHOW_FILTER)
        if args.debug:
            import pdb; pdb.set_trace()
            cursor = cursor.limit(100)
        for doc in db[collection].find(SHOW_FILTER):
            if "En" not in doc["Slug"]:
                continue

            try:
                if collection == 'personalities':
                    places = ','.join(map(lambda x: x["PlaceIds"],
                                        doc["UnitPlaces"]))
                    row = [doc["UnitId"],
                            doc["Header"]["En"],
                            doc["PersonTypeCodesDesc"]["He"],
                            doc["PeriodDesc"]["En"],
                            doc["UnitText1"]["En"],
                            places,
                           ]
                elif collection == 'places':
                    row = [doc["UnitId"],
                            doc["Header"]["En"],
                            doc["UnitText1"]["En"],
                           ]
                elif collection == 'familyNames':
                    row = [doc["UnitId"],
                            doc["Header"]["En"],
                            doc["UnitText1"]["En"],
                           ]
                elif collection == 'photoUnits':
                    places = ','.join(map(lambda x: x["PlaceIds"],
                                        doc["UnitPlaces"]))
                    row = [doc["UnitId"],
                           doc["Header"]["En"],
                           doc["PeriodDesc"]["En"],
                           doc["UnitText1"]["En"],
                           places,
                          ]
            except KeyError:
                continue
            url = "http://dbs.bh.org.il/" + \
                  urllib2.quote(doc["Slug"]["En"]
                                .replace('_', '/')
                                .encode("utf8"))
            row.insert(0, url)
            writer.writerow(clean(row))
        outfile.close()
        finished = datetime.now()
        print 'Collection {} took {}'.format(collection, finished-started)
    fns = [i+'.csv' for i in collections]
    tgz_fn = 'mojp-csv-dump.{}.tgz'.format(
            datetime.now().strftime("%d.%m.%y-%H:%M:%S"))
    tgz_path = os.path.join(args.out, tgz_fn)
    call(['tar','-C', args.out,
          '-czf', tgz_path] + fns)

    if args.ftp_server:
        ftp = FTP(args.ftp_server, args.ftp_user, args.ftp_password)
        tgz = open(tgz_path)
        ftp.cwd(args.ftp_dir)
        ftp.storbinary('STOR '+ tgz_fn, tgz)
        tgz.close()
        ftp.quit()
