import json

from flask_jwt import JWT
from flask.ext.jwt import current_user
from flask import request, abort
from flask.ext.security import (Security, MongoEngineUserDatastore,
                                UserMixin, RoleMixin)
from flask.ext.security.utils import encrypt_password, verify_password

from bhs_api import app, db
from utils import get_logger, get_referrer_host_url, humanify, dictify, send_gmail

logger = get_logger()


class Role(db.Document, RoleMixin):
    name = db.StringField(max_length=80, unique=True)
    description = db.StringField(max_length=255)


class StoryLine(db.EmbeddedDocument):
    id = db.StringField(max_length=512, unique=True)
    in_branch = db.ListField(db.BooleanField(), default=4*[False])


class User(db.Document, UserMixin):
    email = db.StringField(max_length=255)
    password = db.StringField(max_length=255)
    name = db.StringField(max_length=255)
    active = db.BooleanField(default=True)
    confirmed_at = db.DateTimeField()
    roles = db.ListField(db.ReferenceField(Role))
    story_items = db.EmbeddedDocumentListField(StoryLine)
    story_branches = db.ListField(field=db.StringField(max_length=64),
                                  default=4*[''])

user_datastore = MongoEngineUserDatastore(db, User, Role)
security = Security(app, user_datastore)
jwt = JWT(app)


# Ensure we have a user to test with
@app.before_first_request
def setup_users():
    for role_name in ('user', 'admin'):
        if not user_datastore.find_role(role_name):
            logger.debug('Creating role {}'.format(role_name))
            user_datastore.create_role(name=role_name)

    user_role = user_datastore.find_role('user')
    test_user = user_datastore.get_user('tester@example.com')
    if not test_user:
        logger.debug('Creating test user.')
        user_datastore.create_user(email='tester@example.com',
                                   name='Test User',
                                   password=encrypt_password('password'),
                                   roles=[user_role])


@jwt.authentication_handler
def authenticate(username, password):
    # We must use confusing email=username alias until the flask-jwt
    # author merges request #31
    # https://github.com/mattupstate/flask-jwt/pull/31
    user_obj = user_datastore.find_user(email=username)
    if not user_obj:
        logger.debug('User {} not found'.format(username))
        return None

    if verify_password(password, user_obj.password):
        # make user.id jsonifiable
        user_obj.id = str(user_obj.id)
        return user_obj
    else:
        logger.debug('Wrong password for {}'.format(username))
        return None


@jwt.user_handler
def load_user(payload):
    user_obj = user_datastore.find_user(id=payload['user_id'])
    return user_obj


def is_admin(flask_user_obj):
    if flask_user_obj.has_role('admin'):
        return True
    else:
        return False


def user_handler(user_id, request):
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
            logger.debug(e_message)
            abort(400, e_message)

    if method == 'GET':
        return humanify(get_user(user_id))

    elif method == 'POST':
        if not data:
            abort(400, 'No data provided')
        return humanify(create_user(data, referrer_host_url))

    elif method == 'PUT':
        if not data:
            abort(400, 'No data provided')
        return humanify(update_user(user_id, data))

    elif method == 'DELETE':
        return humanify(delete_user(user_id))


def get_user_or_error(user_id):
    user = user_datastore.get_user(user_id)
    if user:
        return user
    else:
        raise abort(404, 'User not found')


def clean_user(user_obj):
    user_dict = dictify(user_obj)
    ret = {}
    for key in ['email', 'name', 'confirmed_at']:
        ret[key] = user_dict.get(key, None)
    ret.update(get_mjs(user_obj))
    return ret


def get_user(user_id):
    user_obj = get_user_or_error(user_id)
    return clean_user(user_obj)


def delete_user(user_id):
    user = get_user_or_error(user_id)
    if is_admin(user):
        return {'error': 'God Mode!'}
    else:
        user.delete()
        return {}


def create_user(user_dict, referrer_host_url=None):
    try:
        email = user_dict['email']
        name = user_dict['name']
        enc_password = encrypt_password(user_dict['password'])
    except KeyError as e:
        e_message = '{} key is missing from data'.format(e)
        logger.debug(e_message)
        abort(400, e_message)

    user_exists = user_datastore.get_user(email)
    if user_exists:
        e_message = 'User {} with email {} already exists'.format(
            str(user_exists.id), email)
        logger.debug(e_message)
        abort(409, e_message)

    created = user_datastore.create_user(email=email,
                                         name=name,
                                         password=enc_password)
    # Add default role to a newly created user
    user_datastore.add_role_to_user(created, 'user')
    # Send an email confirmation link only if referrer is specified
    if referrer_host_url:
        user_id = str(created.id)
        send_activation_email(user_id, referrer_host_url)

    return clean_user(created)


def update_user(user_id, user_dict):
    user_obj = get_user_or_error(user_id)
    if 'email' in user_dict.keys():
        user_obj.email = user_dict['email']
    if 'name' in user_dict.keys():
        user_obj.email = user_dict['name']
    if 'password' in user_dict.keys():
        enc_password = encrypt_password(user_dict['password'])
        user_obj.password = enc_password

    user_obj.save()
    return clean_user(user_obj)


def get_frontend_activation_link(user_id, referrer_host_url):
    s = URLSafeSerializer(app.secret_key)
    payload = s.dumps(user_id)
    return '{}/verify_email/{}'.format(referrer_host_url, payload)


def send_activation_email(user_id, referrer_host_url):
    user = get_user_or_error(user_id)
    email = user.email
    name = user.name
    activation_link = get_frontend_activation_link(user_id, referrer_host_url)
    body = _generate_confirmation_body('email_verfication_template.html',
                                       name, activation_link)
    subject = 'My Jewish Story: please confirm your email address'
    sent = send_gmail(subject, body, email, message_mode='html')
    if not sent:
        e_message = 'There was an error sending an email to {}'.format(email)
        logger.error(e_message)
        abort(500, e_message)
    return humanify({'sent': email})


def _generate_confirmation_body(template_fn, name, activation_link):
    try:
        fh = open(template_fn)
        template = fh.read()
        fh.close()
        return template.format(name, activation_link)
    except:
        logger.debug("Couldn't open template file {}".format(template_fn))
        abort(500, "Couldn't open template file")

    body = '''Hello {}!
    Please click on <a href="{}">activation link</a> to activate your user at My Jewish Story web site.
    If you received this email by mistake, simply delete it.

    Thanks, Beit HaTfutsot Online team.'''
    return body.format(name, activation_link)

def add_to_my_story(item_id):
    current_user.story_items.append(StoryLine(id=item_id,
                                              in_branch=4*[False]))
    current_user.save()

def get_mjs(user=current_user):
    return {'story_items': [{'id': o.id, 'in_branch': o.in_branch} for o in user.story_items],
            'story_branches': user.story_branches}

def set_item_in_branch(item_id, branch_num, value):
    line = None
    for i in current_user.story_items:
        if i.id == item_id:
            line = i
            break
    if not line:
        abort(400, 'item must be part of the story'.format(item_id))
    line.in_branch[branch_num] = value
    current_user.save()

def remove_item_from_story(item_id):
    current_user.story_items.filter(id=item_id).delete()
