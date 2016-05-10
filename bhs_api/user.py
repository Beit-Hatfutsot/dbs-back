import json

from flask import request, abort, current_app
from flask.ext.security import current_user
from flask.ext.security.utils import encrypt_password, verify_password
from flask.ext.security.passwordless import send_login_instructions

from utils import get_referrer_host_url, humanify, dictify, send_gmail
from .models import StoryLine

SAFE_KEYS = ('email', 'name', 'confirmed_at', 'next')

# Ensure we have a user to test with
'''
@current_app.before_first_request
def setup_users():
    for role_name in ('user', 'admin'):
        if not current_app.user_datastore.find_role(role_name):
            current_app.logger.debug('Creating role {}'.format(role_name))
            current_app.user_datastore.create_role(name=role_name)

    user_role = current_app.user_datastore.find_role('user')
    test_user = current_app.user_datastore.get_user('tester@example.com')
    if test_user:
        test_user.delete()
    current_app.logger.debug('Creating test user.')
    current_app.user_datastore.create_user(email='tester@example.com',
                                name='Test User',
                                password=encrypt_password('password'),
                                roles=[user_role])
'''


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
            current_app.logger.debug(e_message)
            abort(400, e_message)

    if method == 'GET':
        return humanify(get_user(user_id))

    elif method == 'POST':
        if not data:
            abort(400, 'No data provided')
        return humanify(send_ticket(data, referrer_host_url))

    elif method == 'PUT':
        if not data:
            abort(400, 'No data provided')
        return humanify(update_user(user_id, data))

    elif method == 'DELETE':
        return humanify(delete_user(user_id))


def get_user_or_error(user_id):
    user = current_app.user_datastore.get_user(user_id)
    if user:
        return user
    else:
        raise abort(404, 'User not found')


def clean_user(user_obj):
    user_dict = dictify(user_obj)
    ret = {}
    for key in SAFE_KEYS:
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


def send_ticket(user_dict, referrer_host_url=None):
    next = getattr(user_dict, 'next', '/welcome')
    try:
        email = user_dict['email']
        # enc_password = encrypt_password(user_dict['password'])
    except KeyError as e:
        e_message = '{} key is missing from data'.format(e)
        current_app.logger.debug(e_message)
        abort(400, e_message)

    user = current_app.user_datastore.get_user(email)
    if not user:
        user = current_app.user_datastore.create_user(email=email, next=next)
        # Add default role to a newly created user
        current_app.user_datastore.add_role_to_user(user, 'user')

    send_login_instructions(user)
    return clean_user(user)


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
    s = URLSafeSerializer(current_app.secret_key)
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
        current_app.logger.error(e_message)
        abort(500, e_message)
    return humanify({'sent': email})


def _generate_confirmation_body(template_fn, name, activation_link):
    try:
        fh = open(template_fn)
        template = fh.read()
        fh.close()
        return template.format(name, activation_link)
    except:
        current_app.logger.debug("Couldn't open template file {}".format(template_fn))
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
    current_user.story_items = [i for i in current_user.story_items if i.id != item_id]
    current_user.save()
