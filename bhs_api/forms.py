from wtforms import Field, StringField

from flask.ext.security.forms import PasswordlessLoginForm

class LoginForm(PasswordlessLoginForm):
    next = StringField('Next URL')
