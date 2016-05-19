from mongoengine import (ListField, StringField, EmbeddedDocumentListField,
                         EmbeddedDocument, GenericEmbeddedDocumentField,
                         BooleanField, DateTimeField, ReferenceField)
from flask.ext.mongoengine import Document
from flask.ext.security import UserMixin, RoleMixin

class Role(Document, RoleMixin):
    name = StringField(max_length=80, unique=True)
    description = StringField(max_length=255)


class StoryLine(EmbeddedDocument):
    id = StringField(max_length=512, unique=True)
    in_branch = ListField(BooleanField(), default=4*[False])


class User(Document, UserMixin):
    email = StringField(max_length=255)
    password = StringField(max_length=255)
    name = StringField(max_length=255)
    next = StringField(max_length=1023)
    active = BooleanField(default=True)
    confirmed_at = DateTimeField()
    roles = ListField(ReferenceField(Role))
    story_items = EmbeddedDocumentListField(StoryLine)
    story_branches = ListField(field=StringField(max_length=64),
                                  default=4*[''])
    next_state = StringField(max_length=31, default='mjs')
    next_params = GenericEmbeddedDocumentField()


