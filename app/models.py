import enum

from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.ext.associationproxy import association_proxy

db = SQLAlchemy()


# Enum for user ranks
class RankEnum(enum.Enum):
    KEIN = 'KEIN'
    BRONZE = 'BRONZE'
    SILBER = 'SILBER'
    GOLD = 'GOLD'
    PLATIN = 'PLATIN'


# Enum for user roles
class RoleEnum(enum.Enum):
    ADMIN = 'ADMIN'
    TEACHER = 'TEACHER'
    MEMBER = 'MEMBER'


# User model
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
    active_from = db.Column(DateTime, nullable=True)  # Date when the user becomes active
    active_until = db.Column(DateTime, nullable=True)  # Date when the user becomes inactive
    last_login = db.Column(db.DateTime, nullable=True)

    user_roles = db.relationship(
        'UserRole',
        back_populates='user',
        cascade='all, delete-orphan',
    )
    permission_overrides = db.relationship(
        'UserPermissionOverride',
        back_populates='user',
        cascade='all, delete-orphan',
    )
    roles = association_proxy('user_roles', 'role', creator=lambda role: UserRole(role=role))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == RoleEnum.ADMIN or self.has_permission('admin.access')

    @property
    def is_teacher(self):
        return self.role == RoleEnum.TEACHER

    def has_permission(self, permission_name):
        if self.role == RoleEnum.ADMIN:
            return True

        for override in self.permission_overrides:
            if override.permission and override.permission.name == permission_name:
                return override.allowed

        for role in self.roles:
            for permission in role.permissions:
                if permission.name == permission_name:
                    return True

        return False

    @property
    def user_privileges(self):
        return self.permission_overrides

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


# Message model
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(64), nullable=False)  # Role of the author
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.now())
    deleted = db.Column(db.Boolean, default=False)  # Indicates if the message is deleted


# Ticket status model
class TicketStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50), nullable=False)


# Problem ticket model
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
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'ticket_id': self.id, 'ticket_type': 'problem'})

    @staticmethod
    def verify_token(token):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=current_app.config['TICKET_TOKEN_MAX_AGE_SECONDS'])
        except (SignatureExpired, BadSignature):
            return None
        if data.get('ticket_type') != 'problem':
            return None
        return ProblemTicket.query.get(data['ticket_id'])


# Training ticket model
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
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'ticket_id': self.id, 'ticket_type': 'training'})

    @staticmethod
    def verify_token(token):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=current_app.config['TICKET_TOKEN_MAX_AGE_SECONDS'])
        except (SignatureExpired, BadSignature):
            return None
        if data.get('ticket_type') != 'training':
            return None
        return TrainingTicket.query.get(data['ticket_id'])


# Miscellaneous ticket model
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
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'ticket_id': self.id, 'ticket_type': 'misc'})

    @staticmethod
    def verify_token(token):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=current_app.config['TICKET_TOKEN_MAX_AGE_SECONDS'])
        except (SignatureExpired, BadSignature):
            return None
        if data.get('ticket_type') != 'misc':
            return None
        return MiscTicket.query.get(data['ticket_id'])


# Problem ticket user association model
class ProblemTicketUser(db.Model):
    ticket_user_id = db.Column(db.Integer, primary_key=True)
    problem_ticket_id = db.Column(db.Integer, db.ForeignKey('problem_ticket.id'), nullable=False)  # ForeignKey to ProblemTicket
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # ForeignKey to User
    assigned_at = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)  # Assignment timestamp

    # Relationships
    user = db.relationship('User', backref='problem_ticket_assignments')
    problem_ticket = db.relationship('ProblemTicket', backref='assigned_users')


# Training ticket user association model
class TrainingTicketUser(db.Model):
    ticket_user_id = db.Column(db.Integer, primary_key=True)
    training_ticket_id = db.Column(db.Integer, db.ForeignKey('training_ticket.id'), nullable=False)  # ForeignKey to TrainingTicket
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # ForeignKey to User
    assigned_at = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)  # Assignment timestamp

    # Relationships
    user = db.relationship('User', backref='training_ticket_assignments')
    training_ticket = db.relationship('TrainingTicket', backref='assigned_users')


# Miscellaneous ticket user association model
class MiscTicketUser(db.Model):
    ticket_user_id = db.Column(db.Integer, primary_key=True)
    misc_ticket_id = db.Column(db.Integer, db.ForeignKey('misc_ticket.id'), nullable=False)  # ForeignKey to MiscTicket
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # ForeignKey to User
    assigned_at = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)  # Assignment timestamp

    # Relationships
    user = db.relationship('User', backref='misc_ticket_assignments')
    misc_ticket = db.relationship('MiscTicket', backref='assigned_users')


# Ticket history model
class TicketHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_type = db.Column(db.String(50), nullable=False)
    ticket_id = db.Column(db.Integer, nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    author_type = db.Column(db.String(50), nullable=False)  # Indicates the type of author

    def __init__(self, ticket_type, ticket_id, message, author_type):
        self.ticket_type = ticket_type
        self.ticket_id = ticket_id
        self.message = message
        self.author_type = author_type


class Permission(db.Model):
    __tablename__ = 'permission'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    role_permissions = db.relationship(
        'RolePermission',
        back_populates='permission',
        cascade='all, delete-orphan',
    )
    user_permission_overrides = db.relationship(
        'UserPermissionOverride',
        back_populates='permission',
        cascade='all, delete-orphan',
    )
    roles = association_proxy('role_permissions', 'role', creator=lambda role: RolePermission(role=role))

    def __init__(self, **kwargs):
        category = kwargs.pop('category', None)
        if category is not None and 'description' not in kwargs:
            kwargs['description'] = category
        super().__init__(**kwargs)


class Role(db.Model):
    __tablename__ = 'role'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_system_role = db.Column(db.Boolean, nullable=False, default=False)

    user_roles = db.relationship(
        'UserRole',
        back_populates='role',
        cascade='all, delete-orphan',
    )
    role_permissions = db.relationship(
        'RolePermission',
        back_populates='role',
        cascade='all, delete-orphan',
    )
    users = association_proxy('user_roles', 'user', creator=lambda user: UserRole(user=user))
    permissions = association_proxy(
        'role_permissions',
        'permission',
        creator=lambda permission: RolePermission(permission=permission),
    )


class RolePermission(db.Model):
    __tablename__ = 'role_permission'

    role_id = db.Column(db.Integer, db.ForeignKey('role.id', ondelete='CASCADE'), primary_key=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permission.id', ondelete='CASCADE'), primary_key=True)

    role = db.relationship('Role', back_populates='role_permissions')
    permission = db.relationship('Permission', back_populates='role_permissions')


class UserRole(db.Model):
    __tablename__ = 'user_role'

    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id', ondelete='CASCADE'), primary_key=True)

    user = db.relationship('User', back_populates='user_roles')
    role = db.relationship('Role', back_populates='user_roles')


class UserPermissionOverride(db.Model):
    __tablename__ = 'user_permission_override'

    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permission.id', ondelete='CASCADE'), primary_key=True)
    allowed = db.Column(db.Boolean, nullable=False, default=True)
    reason = db.Column(db.Text, nullable=True)

    user = db.relationship('User', back_populates='permission_overrides')
    permission = db.relationship('Permission', back_populates='user_permission_overrides')

    def __init__(self, **kwargs):
        privilege_id = kwargs.pop('privilege_id', None)
        if privilege_id is not None and 'permission_id' not in kwargs:
            kwargs['permission_id'] = privilege_id
        kwargs.setdefault('allowed', True)
        super().__init__(**kwargs)

    @property
    def privilege_id(self):
        return self.permission_id

    @privilege_id.setter
    def privilege_id(self, value):
        self.permission_id = value


# Backward-compatible aliases for existing imports and admin flows.
Privilege = Permission
UserPrivilege = UserPermissionOverride
