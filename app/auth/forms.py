"""Authentication forms."""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Length


class LoginForm(FlaskForm):
    """Admin login form."""

    username = StringField(
        "Username",
        validators=[DataRequired(message="Username ထည့်ပါ။"), Length(min=1, max=64)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Password ထည့်ပါ။"), Length(min=1, max=256)],
    )
    remember = BooleanField("Remember me")
    submit = SubmitField("Login")
