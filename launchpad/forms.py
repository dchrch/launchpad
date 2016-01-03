"""Forms for the bull application."""
from flask_wtf import Form
from wtforms import TextField, PasswordField, SelectField
from wtforms.validators import DataRequired

from .models import *

class LoginForm(Form):
    """Form class for user login."""
    email = TextField('email', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])