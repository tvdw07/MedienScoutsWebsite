import enum

from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from itsdangerous import URLSafeSerializer, URLSafeTimedSerializer, SignatureExpired, BadSignature
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import DateTime

db = SQLAlchemy()

class RankEnum(enum.Enum):
    KEIN = 'KEIN'
    BRONZE = 'BRONZE'
    SILBER = 'SILBER'
    GOLD = 'GOLD'
    PLATIN = 'PLATIN'



class RoleEnum(enum.Enum):
    ADMIN = 'ADMIN'
    TEACHER = 'TEACHER'
    MEMBER = 'MEMBER'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.Enum(RoleEnum), nullable=False, default=RoleEnum.MEMBER)
    rank = db.Column(db.Enum(RankEnum), nullable=True, default=RankEnum.KEIN)
    active = db.Column(db.Boolean, default=True)
    active_from = db.Column(DateTime, nullable=True)  # Zeitpunkt, ab dem das Mitglied aktiv ist
    active_until = db.Column(DateTime, nullable=True)  # Zeitpunkt, bis zu dem das Mitglied aktiv ist
    last_login = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == RoleEnum.ADMIN

    def generate_reset_password_token(self):
        serializer = URLSafeTimedSerializer(current_app.secret_key)
        salt = self.password_hash if self.password_hash else current_app.config['SECURITY_PASSWORD_SALT']
        return serializer.dumps({'email': self.email, 'id': self.id}, salt=salt)

    @staticmethod
    def validate_reset_password_token(token, user_id):
        serializer = URLSafeTimedSerializer(current_app.secret_key)
        try:
            user = User.query.get(user_id)
            salt = user.password_hash if user.password_hash else current_app.config['SECURITY_PASSWORD_SALT']
            data = serializer.loads(token, salt=salt, max_age=3600)
            user = User.query.get(data['id'])
            if user and user.email == data['email']:
                return user
        except (SignatureExpired, BadSignature):
            return None
        return None

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(64), nullable=False)  # Add this line
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.now())
    deleted = db.Column(db.Boolean, default=False)  # Add this line



class TicketStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50), nullable=False)

class ProblemTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    serial_number = db.Column(db.String(50), nullable=True)
    problem_description = db.Column(db.Text, nullable=False)
    steps_taken = db.Column(db.Text, nullable=True)
    photo = db.Column(db.String(200), nullable=True)  # Assuming file path stored
    created_at = db.Column(db.DateTime, default=datetime.now())
    status_id = db.Column(db.Integer, db.ForeignKey('ticket_status.id'), default=1)  # Default to "open"
    status = db.relationship('TicketStatus', backref='problem_tickets')

    def generate_token(self):
        s = URLSafeSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'ticket_id': self.id})

    @staticmethod
    def verify_token(token):
        s = URLSafeSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except Exception as e:
            print(f"Token verification error: {e}")
            return None
        return ProblemTicket.query.get(data['ticket_id'])

class TrainingTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_teacher = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    training_type = db.Column(db.String(100), nullable=False)
    training_reason = db.Column(db.Text, nullable=True)
    proposed_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now())
    status_id = db.Column(db.Integer, db.ForeignKey('ticket_status.id'), default=1)
    status = db.relationship('TicketStatus', backref='training_tickets')

    def generate_token(self):
        s = URLSafeSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'ticket_id': self.id})

    @staticmethod
    def verify_token(token):
        s = URLSafeSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except Exception as e:
            print(f"Token verification error: {e}")
            return None
        return TrainingTicket.query.get(data['ticket_id'])

class MiscTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    status_id = db.Column(db.Integer, db.ForeignKey('ticket_status.id'), default=1)
    status = db.relationship('TicketStatus', backref='misc_tickets')

    def generate_token(self):
        s = URLSafeSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'ticket_id': self.id})

    @staticmethod
    def verify_token(token):
        s = URLSafeSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except Exception as e:
            print(f"Token verification error: {e}")
            return None
        return MiscTicket.query.get(data['ticket_id'])

class ProblemTicketUser(db.Model):
    ticket_user_id = db.Column(db.Integer, primary_key=True)
    problem_ticket_id = db.Column(db.Integer, db.ForeignKey('problem_ticket.id'), nullable=False)  # ForeignKey to ProblemTicket
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # ForeignKey to User
    assigned_at = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)  # Assignment timestamp

    # Relationships
    user = db.relationship('User', backref='problem_ticket_assignments')
    problem_ticket = db.relationship('ProblemTicket', backref='assigned_users')

class TrainingTicketUser(db.Model):
    ticket_user_id = db.Column(db.Integer, primary_key=True)
    training_ticket_id = db.Column(db.Integer, db.ForeignKey('training_ticket.id'), nullable=False)  # ForeignKey to TrainingTicket
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # ForeignKey to User
    assigned_at = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)  # Assignment timestamp

    # Relationships
    user = db.relationship('User', backref='training_ticket_assignments')
    training_ticket = db.relationship('TrainingTicket', backref='assigned_users')


class MiscTicketUser(db.Model):
    ticket_user_id = db.Column(db.Integer, primary_key=True)
    misc_ticket_id = db.Column(db.Integer, db.ForeignKey('misc_ticket.id'), nullable=False)  # ForeignKey to MiscTicket
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # ForeignKey to User
    assigned_at = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)  # Assignment timestamp

    # Relationships
    user = db.relationship('User', backref='misc_ticket_assignments')
    misc_ticket = db.relationship('MiscTicket', backref='assigned_users')

class TicketHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_type = db.Column(db.String(50), nullable=False)
    ticket_id = db.Column(db.Integer, nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    author_type = db.Column(db.String(50), nullable=False)  # New column to indicate author type

    def __init__(self, ticket_type, ticket_id, message, author_type):
        self.ticket_type = ticket_type
        self.ticket_id = ticket_id
        self.message = message
        self.author_type = author_type