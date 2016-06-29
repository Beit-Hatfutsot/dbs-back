from flask import Blueprint
from flask_security.decorators import _check_token

from utils import humanify

endpoints = Blueprint('general', __name__)

@endpoints.route('/')
def home():
    if _check_token():
        return humanify({'access': 'private'})
    else:
        return humanify({'access': 'public'})
