import re
import logging
import pymongo

logging.basicConfig(level=logging.INFO)

#c=MongoClient("mongodb://{}".format(db_address))
if __name__ == "__main__":
    c = pymongo.MongoClient()
    db = c.bhp6
    all_places = db.places
    valid_name = re.compile("^[\w\s]+$", re.U)
    logging.info('total places: {}'.format(all_places.count()))
    for lang in ['En', 'He']:
        header_key = "Header.{}".format(lang)
        text_key = 'UnitText1.{}'.format(lang)
        # '{{id:this.UnitId, len:this.{}.length}}); }}'.format(text_key),
        map_function = '''
            function()
            {{ emit (this.{0},
                     {{id:this.UnitId,
                       len:(this.{1})?this.{1}.length:0}}); }}
        '''.format(header_key, text_key) # .replace('\n','')
        places = all_places.map_reduce(
            map_function,
            'function(key, values) { return null; }',
            out='unique_places')
        for i in places.find({"value.len": {'$gt': 100}}):
            name = i['_id'].encode('utf-8')
            logging.info('looking for occurances of {}'.format(name))
            regx = re.compile(u"(\s)({})(\s)".format(re.escape(name.decode('utf=8'))),
                              re.I|re.U)
            place_url = 'http://bhsclient/places/'+str(i['value']['id'])
            r = []
            for j in db.personalities.find({text_key: regx}):
                logging.info('>>> adding link in {}'.format(j["Header"][lang].encode("utf-8")))
                text = regx.sub(r'\1[\2]({})\3'.format(place_url), # marked_url.pattern,
                                j['UnitText1'][lang])
                r.append(pymongo.operations.UpdateOne({'UnitId': j['UnitId']},
                                   {'$set': { text_key: text }}))
            if r: db.personalities.bulk_write(r)




