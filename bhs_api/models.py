import hashlib
from mongoengine import (ListField, StringField, EmbeddedDocumentField,
                        EmbeddedDocumentListField, EmbeddedDocument,
                        GenericEmbeddedDocumentField, BooleanField,
                        DateTimeField, ReferenceField)

from flask import current_app
from flask.ext.mongoengine import Document
from flask.ext.security import UserMixin, RoleMixin


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

    def save(self):

        if not self.hash:
            self.hash = hashlib.md5(self.email.lower()).hexdigest()

        if self.next.startswith('/login'):
            self.next = current_app.config['DEFAULT_NEXT']
        super(User, self).save()
