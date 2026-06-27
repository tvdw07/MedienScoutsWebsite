from flask import current_app
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, HiddenField
from wtforms.validators import DataRequired, EqualTo, Length, Optional
from wtforms.validators import ValidationError
import re


# Custom validator for password policy
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
        if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>_\-]', password):
            raise ValidationError('Password must contain at least one special character.')


class SimpleEmail:
    def __call__(self, form, field):
        value = (field.data or '').strip()
        if not value:
            return
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', value):
            raise ValidationError('Invalid email address.')


# Form for user login
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


# Form for requesting password reset
class PasswordResetRequestForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), SimpleEmail()])
    submit = SubmitField('Request Password Reset')


# Form for resetting password
class PasswordResetForm(FlaskForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.password_policy = PasswordPolicy(current_app.config['PASSWORD_POLICY'])
        self.password.validators.append(self.password_policy)

    password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')


# Form for editing user profile
class EditProfileForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), SimpleEmail()])
    profile_image = FileField('Profile Image', validators=[FileAllowed(['jpg', 'png', 'jpeg'])])
    delete_image = SubmitField('Delete Profile Image')
    submit = SubmitField('Save Changes')


MEDIA_CONSULTING_TOPIC_CHOICES = [
    ('Social Media', 'Social Media'),
    ('Datenschutz / Privatsphäre', 'Datenschutz / Privatsphäre'),
    ('Cybermobbing', 'Cybermobbing'),
    ('Gaming / Bildschirmzeit', 'Gaming / Bildschirmzeit'),
    ('Mediensucht', 'Mediensucht'),
    ('iPad / Apps / Schulgeräte', 'iPad / Apps / Schulgeräte'),
    ('Sonstiges', 'Sonstiges'),
]


class SendTicketForm(FlaskForm):
    ticket_type = SelectField(
        'Ticket Art',
        choices=[
            ('problem', 'Problem'),
            ('fortbildung', 'Fortbildung'),
            ('medienberatung', 'Medienberatung'),
            ('sonstiges', 'Sonstiges'),
        ],
        default='problem',
        validators=[DataRequired()],
    )

    problem_first_name = StringField('Vorname', validators=[Optional(), Length(max=50)])
    problem_last_name = StringField('Nachname', validators=[Optional(), Length(max=50)])
    problem_email = StringField('E-Mail-Adresse', validators=[Optional(), SimpleEmail(), Length(max=100)])
    problem_class_name = StringField('Klasse/Stufe', validators=[Optional(), Length(max=50)])
    problem_serial_number = StringField('Seriennummer', validators=[Optional(), Length(max=50)])
    problem_description = TextAreaField('Beschreibung des Problems', validators=[Optional()])
    problem_steps = HiddenField()
    photo = FileField('Foto', validators=[Optional(), FileAllowed(['jpg', 'png', 'jpeg'])])

    training_class_teacher = StringField('Klassenlehrer', validators=[Optional(), Length(max=50)])
    training_email = StringField('E-Mail-Adresse', validators=[Optional(), SimpleEmail(), Length(max=100)])
    training_type = StringField('Art der Fortbildung', validators=[Optional(), Length(max=100)])
    training_reason = TextAreaField('Grund für die Fortbildung', validators=[Optional()])
    training_proposed_date = StringField('Vorgeschlagenes Datum & Uhrzeit', validators=[Optional(), Length(max=32)])

    media_first_name = StringField('Vorname', validators=[Optional(), Length(max=50)])
    media_last_name = StringField('Nachname', validators=[Optional(), Length(max=50)])
    media_email = StringField('E-Mail-Adresse', validators=[Optional(), SimpleEmail(), Length(max=100)])
    media_class_name = StringField('Klasse', validators=[Optional(), Length(max=50)])
    media_topic = SelectField(
        'Thema',
        choices=[('', 'Bitte Thema auswählen')] + MEDIA_CONSULTING_TOPIC_CHOICES,
        validators=[Optional()],
    )
    media_description = TextAreaField('Beschreibung', validators=[Optional()])
    media_proposed_date = StringField('Terminvorschlag', validators=[Optional(), Length(max=32)])

    misc_first_name = StringField('Vorname', validators=[Optional(), Length(max=50)])
    misc_last_name = StringField('Nachname', validators=[Optional(), Length(max=50)])
    misc_email = StringField('E-Mail-Adresse', validators=[Optional(), SimpleEmail(), Length(max=100)])
    misc_message = TextAreaField('Nachricht', validators=[Optional()])

    submit = SubmitField('Ticket absenden')

    @staticmethod
    def _has_value(field):
        value = field.data
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return bool(value)

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        ticket_type = (self.ticket_type.data or '').strip()
        required_fields_by_type = {
            'problem': [
                self.problem_first_name,
                self.problem_last_name,
                self.problem_email,
                self.problem_class_name,
                self.problem_description,
                self.problem_steps,
            ],
            'fortbildung': [
                self.training_class_teacher,
                self.training_email,
                self.training_type,
                self.training_reason,
                self.training_proposed_date,
            ],
            'medienberatung': [
                self.media_first_name,
                self.media_last_name,
                self.media_email,
                self.media_class_name,
                self.media_topic,
                self.media_description,
            ],
            'sonstiges': [
                self.misc_first_name,
                self.misc_last_name,
                self.misc_email,
                self.misc_message,
            ],
        }

        if ticket_type not in required_fields_by_type:
            self.ticket_type.errors.append('Ungültiger Ticket-Typ.')
            return False

        is_valid = True
        for field in required_fields_by_type[ticket_type]:
            if not self._has_value(field):
                field.errors.append('Dieses Feld ist erforderlich.')
                is_valid = False

        return is_valid


