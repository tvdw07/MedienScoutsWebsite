import self
from flask import current_app
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from wtforms.validators import ValidationError
import re


class PasswordPolicy:
    def __init__(self, policy):
        self.min_length = policy['min_length']
        self.require_uppercase = policy['require_uppercase']
        self.require_lowercase = policy['require_lowercase']
        self.require_digit = policy['require_digit']
        self.require_special = policy['require_special']

    def __call__(self, form, field):
        password = field.data
        if len(password) < self.min_length:
            raise ValidationError(f'Password must be at least {self.min_length} characters long.')
        if self.require_uppercase and not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter.')
        if self.require_lowercase and not re.search(r'[a-z]', password):
            raise ValidationError('Password must contain at least one lowercase letter.')
        if self.require_digit and not re.search(r'\d', password):
            raise ValidationError('Password must contain at least one digit.')
        if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>-_]', password):
            raise ValidationError('Password must contain at least one special character.')

class MessageForm(FlaskForm):
    content = TextAreaField('Message', validators=[DataRequired()])
    submit = SubmitField('Post')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class PasswordResetRequestForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class PasswordResetForm(FlaskForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.password_policy = PasswordPolicy(current_app.config['PASSWORD_POLICY'])
        self.password.validators.append(self.password_policy)

    password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

class EditProfileForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    profile_image = FileField('Profile Image', validators=[FileAllowed(['jpg', 'png', 'jpeg'])])
    delete_image = SubmitField('Delete Profile Image')
    submit = SubmitField('Save Changes')

class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Old Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired()])
    confirm_new_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Change Password')