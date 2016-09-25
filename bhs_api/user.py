import json
import cPickle


# from flask import Flask, Blueprint, request, abort, url_for, current_app
from flask import Blueprint, request, abort, current_app
from flask.ext.security import current_user, auth_token_required
from flask.ext.security.utils import encrypt_password, verify_password
from flask.ext.security.passwordless import send_login_instructions
from flask.ext.security.decorators import _check_token

from utils import get_referrer_host_url, humanify, dictify, send_gmail
from .models import StoryLine, UserName 
from .item import fetch_item


user_endpoints = Blueprint('user', __name__)

@user_endpoints.route('/')
def home():
    if _check_token():
        return humanify({'access': 'private'})
    else:
        return humanify({'access': 'public'})

@user_endpoints.route('/user', methods=['GET', 'PUT'])
@user_endpoints.route('/user/<user_id>', methods=['GET', 'PUT'])
@auth_token_required
def manage_user(user_id=None):
    '''
    Manage user accounts. If routed as /user, gives access only to logged in
    user, else if routed as /user/<user_id>, allows administrative level access
    if the looged in user is in the admin group.
    '''
    if user_id:
        # admin access_mode
        if current_user.is_admin():
            user = get_user_or_error(user_id)
            return humanify(user.handle(request))
        else:
            current_app.logger.debug('Non-admin user {} tried to access user id {}'.format(
                                                  current_user.email, user_id))
            abort(403)
    else:
        # Deny POSTing to logged in non-admin users to avoid confusion with PUT
        if request.method == 'POST':
            abort(400, 'POST method is not supported for logged in users.')
        return humanify(current_user.handle(request))


@user_endpoints.route('/mjs/<item_id>', methods=['DELETE'])
@auth_token_required
def delete_item_from_story(item_id):
    remove_item_from_story(item_id)
    return humanify(current_user.get_mjs())

@user_endpoints.route('/mjs/<branch_num>/<item_id>', methods=['DELETE'])
@auth_token_required
def remove_item_from_branch(item_id, branch_num=None):
    try:
        branch_num = int(branch_num)
    except ValueError:
        raise BadRequest("branch number must be an integer")

    set_item_in_branch(item_id, branch_num-1, False)
    return humanify(current_user.get_mjs())


@user_endpoints.route('/mjs/<branch_num>', methods=['POST'])
@auth_token_required
def add_to_story_branch(branch_num):
    item_id = request.data
    try:
        branch_num = int(branch_num)
    except ValueError:
        raise BadRequest("branch number must be an integer")
    set_item_in_branch(item_id, branch_num-1, True)
    return humanify(current_user.get_mjs())


@user_endpoints.route('/mjs/<branch_num>/name', methods=['POST'])
@auth_token_required
def set_story_branch_name(branch_num):

    name = request.data
    current_user.story_branches[int(branch_num)-1] = name
    current_user.save()
    return humanify(current_user.get_mjs())


@user_endpoints.route('/mjs', methods=['GET', 'POST'])
@auth_token_required
def manage_jewish_story():
    '''Logged in user may GET or POST their jewish story links.
    the links are stored as an array of items where each item has a special
    field: `branch` with a boolean array indicating which branches this item is
    part of.
    POST requests should be sent with a string in form of "collection_name.id".
    '''
    if request.method == 'GET':
        return humanify(current_user.get_mjs())

    elif request.method == 'POST':
        try:
            data = request.data
            # Enforce mjs structure:
            if not isinstance(data, str):
                abort(400, 'Expecting a string')

        except ValueError:
            e_message = 'Could not decode JSON from data'
            current_app.logger.debug(e_message)
            abort(400, e_message)

        add_to_my_story(data)
        return humanify(current_user.get_mjs())

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


def get_user_or_error(user_id):
    user = current_app.user_datastore.get_user(user_id)
    if user:
        return user
    else:
        raise abort(404, 'User not found')


def get_user(user_id):
    user = get_user_or_error(user_id)
    return user.render()


def add_to_my_story(item_id):
    current_user.story_items.append(StoryLine(id=item_id,
                                              in_branch=4*[False]))
    current_user.save()

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

def collect_editors_items(name):
    """
        look for a branch named `name` in all editors stories, collect the items
        and return them
    """
    redis_key = 'collection:'+name
    cache = current_app.redis.get(redis_key)
    if cache:
        return cPickle.loads(cache)

    editor_role = current_app.user_datastore.find_role('editor')
    editors = current_app.user_datastore.user_model.objects(roles=editor_role,
                                                            story_branches=name)
    items = []
    for user in editors:
        i = user.story_branches.index(name)
        for j in user.story_items:
            if j.in_branch[i]:
                items.append(fetch_item(j.id))
    current_app.redis.set(redis_key,
                          cPickle.dumps(items),
                          ex=current_app.config['CACHING_TTL'])
    return items
