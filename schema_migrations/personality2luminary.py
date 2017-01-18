import pymongo
from bhs_api import create_app

if __name__ == "__main__":
    app, conf = create_app(testing=True)
    app.testing = True
    for i in app.data_db.personalities.find({'Slug.En': {'$regex': r'^personality_'}}):
        try:
            s = i['Slug']['En']
        except KeyError:
            continue
        l = s.split('_')[1]
        i['Slug']['En'] = 'luminary_'+l
        app.data_db.personalities.save(i)

    client_user_db = pymongo.MongoClient(conf.user_db_host, conf.user_db_port)[conf.user_db_name]
    user_db = client_user_db['user']
    for i in user_db.find():
        if 'story_items' not in i:
            continue
        changed = False
        for j in i['story_items']:
            slug = j['id']
            if slug.startswith('personality'):
                l = slug.split('_')[1]
                j['id'] = 'luminary_'+l
                app.logger.debug('changed {} to {}'.format(slug, j['id']))
                changed = True
        if changed:
            user_db.update_one({'_id': i['_id']}, 
                               {'$set' : {'story_items': i['story_items']}})

