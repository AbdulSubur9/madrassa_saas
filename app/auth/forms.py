"""Authentication forms."""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from app.models import User


class LoginForm(FlaskForm):
    """User login form."""

    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=80)
    ])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')


class CreateUserForm(FlaskForm):
    """Form for creating a new user."""

    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=80)
    ])
    full_name = StringField('Full Name', validators=[
        DataRequired(),
        Length(min=2, max=200)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters.')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match.')
    ])
    role = SelectField('Role', choices=[
        ('school_admin', 'School Admin'),
        ('collector', 'Collector'),
        ('accountant', 'Accountant')
    ], validators=[DataRequired()])
    submit = SubmitField('Create User')

    def validate_username(self, field):
        """Check if username already exists."""
        user = User.query.filter_by(username=field.data).first()
        if user:
            raise ValidationError('Username already taken. Please choose a different one.')


class ChangePasswordForm(FlaskForm):
    """Form for changing password."""

    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters.')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match.')
    ])
    submit = SubmitField('Change Password')
