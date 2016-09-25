import hashlib
from bson.objectid import ObjectId
from mongoengine import (ListField, StringField, EmbeddedDocumentField,
                        EmbeddedDocumentListField, EmbeddedDocument,
                        GenericEmbeddedDocumentField, BooleanField,
                        DateTimeField, ReferenceField)

from flask import current_app, abort
from flask.ext.mongoengine import Document
from flask.ext.security import UserMixin, RoleMixin
from .utils import dictify

class Role(Document, RoleMixin):
    name = StringField(max_length=80, unique=True)
    description = StringField(max_length=255)


class StoryLine(EmbeddedDocument):
    id = StringField(max_length=512, unique=True)
    in_branch = ListField(BooleanField(), default=4*[False])

class UserName(EmbeddedDocument):
    en = StringField(max_length=64)
    he = StringField(max_length=64) 


class User(Document, UserMixin):
    email = StringField(max_length=255)
    password = StringField(max_length=255, default="lookmanopassword")
    name = EmbeddedDocumentField(UserName)
    active = BooleanField(default=True)
    confirmed_at = DateTimeField()
    roles = ListField(ReferenceField(Role))
    story_items = EmbeddedDocumentListField(StoryLine)
    story_branches = ListField(field=StringField(max_length=64),
                                  default=4*[''])
    next = StringField(max_length=1023, default='/mjs')
    hash = StringField(max_length=255, default='')
    username = StringField(max_length=255)
    meta = {
        'indexes': ['email', 'username', 'hash']
    }

    safe_keys = ('email', 'name', 'confirmed_at', 'next', 'hash')

    def handle(self, request):
        method = request.method
        data = request.data
        referrer = request.referrer
        if referrer:
            referrer_host_url = get_referrer_host_url(referrer)
        else:
            referrer_host_url = None
        if data:
            try:
                data = json.loads(data)
                if not isinstance(data, dict):
                    abort(
                        400,
                        'Only dict like objects are supported for user management')
            except ValueError:
                e_message = 'Could not decode JSON from data'
                current_app.logger.debug(e_message)
                abort(400, e_message)

        if method == 'GET':
            r =  self.render()

        elif method == 'PUT':
            if not data:
                abort(400, 'No data provided')
            r = self.update(data)

        if not r:
            abort(500, 'User handler accepts only GET, PUT or DELETE')
        return r

    def update(self, user_dict):
        if 'email' in user_dict:
            self.email = user_dict['email']
        if 'name' in user_dict:
            if not self.name:
                self.name = UserName()
            for k,v in user_dict['name'].items():
                setattr(self.name, k, v)
        self.save()
        return self.render()

    def render(self):
        # some old users might not have a hash, saving will generate one
        if not self.hash:
            self.save()

        user_dict = dictify(self)
        ret = {}
        for key in self.safe_keys:
            ret[key] = user_dict.get(key, None)
        ret.update(self.get_mjs())

        return ret


    def is_admin(self):
        if self.has_role('admin'):
            return True
        else:
            return False

    def get_mjs(self):
        return {'story_items': [{'id': o.id, 'in_branch': o.in_branch} for o in self.story_items],
                'story_branches': self.story_branches}


    def clean(self):
        ''' this method is called by MongoEngine just before saving '''
        if not self.hash:
            # make sure we have a public hash
            self.hash = hashlib.md5(self.email.lower()).hexdigest()

        # Prevent a nasty bug where next points to a login link causing login
        # to fail
        if self.next.startswith('/login'):
            self.next = current_app.config['DEFAULT_NEXT']
