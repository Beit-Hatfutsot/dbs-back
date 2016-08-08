import re
import pymongo
from bhs_api import create_app

if __name__ == "__main__":
    app, conf = create_app(testing=True)
    app.testing = True
    mongo = pymongo.MongoClient(app.config['MONGODB_HOST'])
    user_db = mongo[conf.user_db_name]

    is_english = re.compile('^[a-zA-Z]')

    for i in user_db['user'].find({'name': {'$exists': True}}):
        name = i['name']
        if is_english.match(name):
            new_name = {'en': name}
        else:
            new_name = {'he': name}
        user_db['user'].update_one({'_id': i['_id']},
                                   {'$set': {'name': new_name}})
