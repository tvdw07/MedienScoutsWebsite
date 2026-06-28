from pathlib import Path

import pytest
from flask import Flask
from flask_login import LoginManager
from flask_wtf import CSRFProtect

from app.blueprints.bp_admin import bp_admin
from app.blueprints.bp_auth import bp_auth
from app.models import db, ProblemTicket, Role, TicketStatus, User
from app.permission_seed import seed_permissions_and_roles
from app.blueprints.main import bp_main


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / 'routes.db'
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
    CSRFProtect(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.session_protection = None
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_admin)
    app.register_blueprint(bp_main)

    with app.app_context():
        db.create_all()
        seed_permissions_and_roles()
        db.session.add_all(
            [
                TicketStatus(id=1, status='Open'),
                TicketStatus(id=2, status='In Progress'),
                TicketStatus(id=3, status='Waiting'),
                TicketStatus(id=4, status='Solved'),
            ]
        )
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login_as(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = str(user)
        session['_fresh'] = True


def create_user_with_role(role_name, username, email):
    role = Role.query.filter_by(name=role_name).one()
    user = User(
        username=username,
        email=email,
        first_name='Test',
        last_name='User',
    )
    db.session.add(user)
    db.session.flush()
    user_id = user.id
    user.roles.append(role)
    db.session.commit()
    return user_id


def test_admin_can_open_admin_area(client, app):
    with app.app_context():
        admin_user = create_user_with_role('Admin', 'admin-user', 'admin-user@example.com')

    login_as(client, admin_user)
    response = client.get('/admin/panel')

    assert response.status_code == 200
    assert b'Admin Panel' in response.data


def test_mediascout_can_see_tickets_but_not_manage_roles(client, app):
    with app.app_context():
        mediascout_user = create_user_with_role('MediaScout', 'mediascout-user', 'mediascout@example.com')

    login_as(client, mediascout_user)
    ticket_response = client.get('/ticketverwaltung')
    roles_response = client.get('/members/administration')

    assert ticket_response.status_code == 200
    assert b'Ticketverwaltung' in ticket_response.data
    assert roles_response.status_code == 403


def test_user_without_ticket_rights_sees_no_internal_tickets(client, app):
    with app.app_context():
        user = create_user_with_role('User', 'plain-user', 'plain-user@example.com')

    login_as(client, user)
    response = client.get('/ticketverwaltung')

    assert response.status_code == 403


def test_public_ticket_creation_rejects_old_field_names(client, app, monkeypatch):
    monkeypatch.setattr('app.blueprints.main.tickets.send_ticket_link', lambda ticket: None)

    response = client.post(
        '/send_ticket',
        data={
            'ticket_type': 'problem',
            'first_name': 'Ada',
            'last_name': 'Lovelace',
            'email_problem': 'ada@example.com',
            'class': '9A',
            'problem_description': 'Notebook will not boot',
        },
    )

    assert response.status_code == 200
    with app.app_context():
        assert ProblemTicket.query.count() == 0


def test_public_ticket_link_still_works(client, app):
    with app.app_context():
        ticket = ProblemTicket(
            first_name='Ada',
            last_name='Lovelace',
            email='ada@example.com',
            class_name='9A',
            problem_description='Notebook will not boot',
            steps_taken='Pressed power, Waited',
            status_id=1,
        )
        db.session.add(ticket)
        db.session.commit()
        token = ticket.generate_token()

    response = client.get(f'/ticket/{token}')

    assert response.status_code == 200
    assert b'Ticket Details' in response.data

