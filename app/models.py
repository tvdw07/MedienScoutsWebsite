import enum

from argon2 import PasswordHasher
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.ext.associationproxy import association_proxy

db = SQLAlchemy()
password_hasher = PasswordHasher()


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
    profile_picture = db.Column(db.String(200), nullable=True)
    profile_picture_original_name = db.Column(db.String(255), nullable=True)
    profile_picture_uploaded_at = db.Column(DateTime, nullable=True)
    role = db.Column(db.Enum(RoleEnum), nullable=False, default=RoleEnum.MEMBER)
    active = db.Column(db.Boolean, default=True)
    active_from = db.Column(DateTime, nullable=True)  # Date when the user becomes active
    active_until = db.Column(DateTime, nullable=True)  # Date when the user becomes inactive
    last_login = db.Column(db.DateTime, nullable=True)
    session_version = db.Column(db.Integer, nullable=False, default=0)

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
    ticket_assignment_notifications = db.relationship(
        'TicketAssignmentNotification',
        back_populates='user',
        cascade='all, delete-orphan',
    )
    roles = association_proxy('user_roles', 'role', creator=lambda role: UserRole(role=role))

    def set_password(self, password):
        self.password_hash = password_hasher.hash(password)
        self.session_version = (self.session_version or 0) + 1

    def get_id(self):
        if self.id is None:
            return None
        return f'{self.id}:{self.session_version or 0}'

    @staticmethod
    def load_from_session_identifier(session_identifier):
        if not session_identifier:
            return None

        try:
            raw_user_id, raw_session_version = str(session_identifier).split(':', 1)
            user_id = int(raw_user_id)
            session_version = int(raw_session_version)
        except (AttributeError, TypeError, ValueError):
            return None

        user = db.session.get(User, user_id)
        if not user or (user.session_version or 0) != session_version:
            return None

        return user

    def check_password(self, password):
        if not self.password_hash:
            return False

        if not isinstance(self.password_hash, str) or not self.password_hash.startswith('$argon2'):
            return False

        try:
            is_valid = password_hasher.verify(self.password_hash, password)
        except Exception:
            return False
        if is_valid and password_hasher.check_needs_rehash(self.password_hash):
            self.password_hash = password_hasher.hash(password)
        return is_valid

    def _collect_permission_sources(self):
        if not self.active:
            return {}

        sources = {}

        for user_role in self.user_roles:
            role = user_role.role
            if not role:
                continue

            role_source = f'role:{role.name}'
            for permission in role.permissions:
                if not permission or not permission.name:
                    continue
                sources.setdefault(permission.name, set()).add(role_source)

        for override in self.permission_overrides:
            permission = override.permission
            if not permission or not permission.name:
                continue
            sources.setdefault(permission.name, set()).add(
                'user_allow' if override.allowed else 'user_deny'
            )

        return sources

    def get_permission_sources(self):
        sources = self._collect_permission_sources()
        return {
            permission_name: sorted(source_values)
            for permission_name, source_values in sources.items()
        }

    def get_effective_permissions(self):
        if not self.active:
            return set()

        effective_permissions = set()
        for permission_name, source_values in self._collect_permission_sources().items():
            if 'user_deny' in source_values:
                continue
            if any(source.startswith('role:') for source in source_values) or 'user_allow' in source_values:
                effective_permissions.add(permission_name)

        return effective_permissions

    def has_permission(self, permission_name):
        if not permission_name or not self.active:
            return False

        source_values = self._collect_permission_sources().get(permission_name)
        if source_values:
            if 'user_deny' in source_values:
                return False

            if any(source.startswith('role:') for source in source_values) or 'user_allow' in source_values:
                return True

        return False

    def generate_reset_password_token(self):
        serializer = URLSafeTimedSerializer(current_app.secret_key)
        salt = self.password_hash if self.password_hash else current_app.config['SECURITY_PASSWORD_SALT']
        return serializer.dumps({'email': self.email, 'id': self.id}, salt=salt)

    @staticmethod
    def validate_reset_password_token(token, user_id):
        serializer = URLSafeTimedSerializer(current_app.secret_key)
        try:
            user = db.session.get(User, user_id)
            if not user:
                return None
            salt = user.password_hash if user.password_hash else current_app.config['SECURITY_PASSWORD_SALT']
            data = serializer.loads(token, salt=salt, max_age=3600)
            user = db.session.get(User, data['id'])
            if user and user.email == data['email']:
                return user
        except (SignatureExpired, BadSignature):
            return None
        return None


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
    photo = db.Column(db.String(200), nullable=True)
    photo_original_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
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
        return db.session.get(ProblemTicket, data['ticket_id'])


# Training ticket model
class TrainingTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_teacher = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    training_type = db.Column(db.String(100), nullable=False)
    training_reason = db.Column(db.Text, nullable=True)
    proposed_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
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
        return db.session.get(TrainingTicket, data['ticket_id'])


# Miscellaneous ticket model
class MiscTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
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
        return db.session.get(MiscTicket, data['ticket_id'])


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


# Media consulting ticket model
class MediaConsultingTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    proposed_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    status_id = db.Column(db.Integer, db.ForeignKey('ticket_status.id'), default=1)
    status = db.relationship('TicketStatus', backref='media_consulting_tickets')

    def generate_token(self):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'ticket_id': self.id, 'ticket_type': 'medienberatung'})

    @staticmethod
    def verify_token(token):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=current_app.config['TICKET_TOKEN_MAX_AGE_SECONDS'])
        except (SignatureExpired, BadSignature):
            return None
        if data.get('ticket_type') != 'medienberatung':
            return None
        return db.session.get(MediaConsultingTicket, data['ticket_id'])


# Media consulting ticket user association model
class MediaConsultingTicketUser(db.Model):
    ticket_user_id = db.Column(db.Integer, primary_key=True)
    media_consulting_ticket_id = db.Column(
        db.Integer,
        db.ForeignKey('media_consulting_ticket.id'),
        nullable=False,
    )
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # ForeignKey to User
    assigned_at = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)  # Assignment timestamp

    # Relationships
    user = db.relationship('User', backref='media_consulting_ticket_assignments')
    media_consulting_ticket = db.relationship('MediaConsultingTicket', backref='assigned_users')


# Ticket history model
class TicketHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_type = db.Column(db.String(50), nullable=False)
    ticket_id = db.Column(db.Integer, nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    author_type = db.Column(db.String(50), nullable=False)  # Indicates the type of author

    def __init__(self, ticket_type, ticket_id, message, author_type):
        self.ticket_type = ticket_type
        self.ticket_id = ticket_id
        self.message = message
        self.author_type = author_type


class TicketAssignmentNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    ticket_type = db.Column(db.String(50), nullable=False)
    ticket_id = db.Column(db.Integer, nullable=False, index=True)
    message = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True, index=True)

    user = db.relationship('User', back_populates='ticket_assignment_notifications')


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
