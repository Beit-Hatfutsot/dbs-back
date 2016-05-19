from wtforms import Field, StringField

from flask.ext.security.forms import PasswordlessLoginForm

class LoginForm(PasswordlessLoginForm):
    next_state = StringField('Next State')
    next_params = Field('Next Params')

