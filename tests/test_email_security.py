from pathlib import Path

import pytest
from flask import Flask
from flask_login import LoginManager

from app.blueprints.bp_admin import bp_admin
from app.blueprints.bp_auth import bp_auth
from app.models import Permission, ProblemTicket, Role, RoleEnum, User, db
from app.permission_seed import seed_permissions_and_roles
from app.blueprints.main import bp_main
from email_tools import notify_admin, send_reset_email, send_ticket_link


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / 'email_security.db'
    templates_path = Path(__file__).resolve().parents[1] / 'app' / 'templates'

    app = Flask(__name__, template_folder=str(templates_path))
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{database_path.as_posix()}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY='test-secret-key',
        SECURITY_PASSWORD_SALT='test-security-salt',
        APP_BASE_URL='https://example.com',
        WTF_CSRF_ENABLED=False,
        TICKET_TOKEN_MAX_AGE_SECONDS=3600,
        MAX_CONTENT_LENGTH=6 * 1024 * 1024,
        MAX_PROFILE_IMAGE_SIZE=2 * 1024 * 1024,
        MAX_TICKET_ATTACHMENT_SIZE=5 * 1024 * 1024,
        UPLOAD_ROOT=str(tmp_path / 'instance' / 'uploads'),
        PROFILE_PICTURE_FOLDER='profile_pictures',
        TICKET_ATTACHMENT_FOLDER='tickets',
    )

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.session_protection = None
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.load_from_session_identifier(user_id)

    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_admin)
    app.register_blueprint(bp_main)

    with app.app_context():
        db.create_all()
        seed_permissions_and_roles()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def create_role(name, permission_names):
    role = Role(name=name, description=f'{name} role', is_system_role=False)
    db.session.add(role)
    db.session.flush()
    for permission_name in permission_names:
        permission = Permission.query.filter_by(name=permission_name).one()
        role.permissions.append(permission)
    db.session.commit()
    return role


def create_user(username, email, *, roles=None, active=True):
    user = User(
        username=username,
        email=email,
        first_name='Test',
        last_name='User',
        role=RoleEnum.MEMBER,
        active=active,
    )
    db.session.add(user)
    db.session.flush()
    for assigned_role in roles or []:
        user.roles.append(assigned_role)
    db.session.commit()
    return user


def create_problem_ticket():
    ticket = ProblemTicket(
        first_name='Ada',
        last_name='Lovelace',
        email='ada@example.com',
        class_name='10A',
        problem_description='Projector does not start',
        steps_taken='Checked cables',
        status_id=1,
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket


def test_password_reset_link_uses_app_base_url_and_ignores_host_header(app, monkeypatch):
    captured = {}

    def capture_email(template, recipient, **variables):
        captured['template'] = template
        captured['recipient'] = recipient
        captured['variables'] = variables

    monkeypatch.setattr('email_tools.send_email', capture_email)

    with app.app_context():
        user = create_user('profile-user', 'profile@example.com')
        with app.test_request_context('/', headers={'Host': 'attacker.example'}):
            send_reset_email(user)

    reset_url = captured['variables']['reset_url']
    assert reset_url.startswith('https://example.com/')
    assert 'attacker.example' not in reset_url
    assert '/reset_password/' in reset_url


def test_public_ticket_link_uses_app_base_url_and_ignores_host_header(app, monkeypatch):
    captured = {}

    def capture_email(template, recipient, **variables):
        captured['template'] = template
        captured['recipient'] = recipient
        captured['variables'] = variables

    monkeypatch.setattr('email_tools.send_email', capture_email)

    with app.app_context():
        ticket = create_problem_ticket()
        with app.test_request_context('/', headers={'Host': 'attacker.example'}):
            send_ticket_link(ticket)

    ticket_link = captured['variables']['link']
    assert ticket_link.startswith('https://example.com/')
    assert 'attacker.example' not in ticket_link
    assert '/ticket/' in ticket_link


def test_admin_notification_uses_app_base_url(app, monkeypatch):
    captured = {}

    def capture_email(template, recipient, **variables):
        captured['template'] = template
        captured['recipient'] = recipient
        captured['variables'] = variables

    monkeypatch.setattr('email_tools.send_email', capture_email)

    with app.app_context():
        admin_role = create_role('AdminNotifier', ['admin.view'])
        create_user('admin-user', 'admin@example.com', roles=[admin_role])
        ticket = create_problem_ticket()
        ticket_id = ticket.id

        with app.test_request_context('/', headers={'Host': 'attacker.example'}):
            notify_admin(ticket, 'problem', 'Help is requested for the following ticket:')

    ticket_details_url = captured['variables']['link']
    assert ticket_details_url.startswith('https://example.com/')
    assert 'attacker.example' not in ticket_details_url
    assert f'/ticket/problem/{ticket_id}/details' in ticket_details_url

