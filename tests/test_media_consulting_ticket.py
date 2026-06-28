from datetime import datetime
from pathlib import Path

import pytest
from flask import Flask
from flask_login import LoginManager
from flask_wtf import CSRFProtect

from app.blueprints.bp_admin import bp_admin
from app.blueprints.bp_auth import bp_auth
from app.models import (
    MediaConsultingTicket,
    MediaConsultingTicketUser,
    ProblemTicket,
    Role,
    RoleEnum,
    TicketHistory,
    TicketStatus,
    User,
    db,
)
from app.permission_seed import seed_permissions_and_roles
from app.blueprints.main import bp_main


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / 'media_consulting.db'
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
        return User.load_from_session_identifier(user_id)

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


def login_as(client, user_id):
    with client.application.app_context():
        resolved_user = db.session.get(User, user_id)
    with client.session_transaction() as session:
        session['_user_id'] = resolved_user.get_id()
        session['_fresh'] = True


def create_user_with_role(role_name, username, email, *, role=RoleEnum.MEMBER, active=True):
    assigned_role = Role.query.filter_by(name=role_name).one()
    user = User(
        username=username,
        email=email,
        first_name='Test',
        last_name='User',
        role=role,
        active=active,
    )
    db.session.add(user)
    db.session.flush()
    user.roles.append(assigned_role)
    db.session.commit()
    return user.id


def create_media_consulting_ticket(**overrides):
    ticket = MediaConsultingTicket(
        first_name=overrides.get('first_name', 'Ada'),
        last_name=overrides.get('last_name', 'Lovelace'),
        email=overrides.get('email', 'ada@example.com'),
        class_name=overrides.get('class_name', '9A'),
        topic=overrides.get('topic', 'Social Media'),
        description=overrides.get('description', 'Need support with media literacy.'),
        proposed_date=overrides.get('proposed_date'),
        status_id=overrides.get('status_id', 1),
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket


def create_admin_user():
    return create_user_with_role('Admin', 'admin-user', 'admin@example.com', role=RoleEnum.ADMIN)


def test_media_consulting_ticket_creation(app):
    with app.app_context():
        ticket = create_media_consulting_ticket(
            proposed_date=datetime(2026, 6, 27, 12, 30),
        )

        stored_ticket = db.session.get(MediaConsultingTicket, ticket.id)
        assert stored_ticket is not None
        assert stored_ticket.first_name == 'Ada'
        assert stored_ticket.class_name == '9A'
        assert stored_ticket.status_id == 1


def test_media_consulting_ticket_token_roundtrip(app):
    with app.app_context():
        ticket = create_media_consulting_ticket()
        token = ticket.generate_token()

        assert isinstance(token, str)
        assert MediaConsultingTicket.verify_token(token).id == ticket.id
        assert ProblemTicket.verify_token(token) is None


def test_media_consulting_ticket_user_assignment_via_claim(client, app):
    with app.app_context():
        admin_id = create_admin_user()
        ticket = create_media_consulting_ticket()
        ticket_id = ticket.id

    login_as(client, admin_id)
    response = client.post(
        f'/ticket/{ticket_id}/claim',
        data={
            'ticket_type': 'medienberatung',
            'user_id': admin_id,
        },
    )

    assert response.status_code == 302
    with app.app_context():
        stored_ticket = db.session.get(MediaConsultingTicket, ticket_id)
        assert stored_ticket.status_id == 2
        assert MediaConsultingTicketUser.query.filter_by(media_consulting_ticket_id=ticket_id).count() == 1


def test_ticket_overview_lists_media_consulting_ticket(client, app):
    with app.app_context():
        admin_id = create_admin_user()
        ticket = create_media_consulting_ticket(topic='Digitale Medien')

    login_as(client, admin_id)
    response = client.get('/ticketverwaltung')

    assert response.status_code == 200
    assert b'Medienberatung Ticket ID' in response.data
    assert b'Digitale Medien' in response.data


def test_ticket_details_renders_flask_wtf_response_form(client, app):
    with app.app_context():
        admin_id = create_admin_user()
        ticket = create_media_consulting_ticket(status_id=2)
        ticket_id = ticket.id

    login_as(client, admin_id)
    response = client.get(f'/ticket/medienberatung/{ticket_id}/details')

    assert response.status_code == 200
    assert b'name="response_message"' in response.data
    assert b'Antwort senden' in response.data


def test_public_media_consulting_ticket_creation(client, app, monkeypatch):
    monkeypatch.setattr('app.blueprints.main.tickets.send_ticket_link', lambda ticket: None)

    response = client.post(
        '/send_ticket',
        data={
            'ticket_type': 'medienberatung',
            'media_first_name': 'Marie',
            'media_last_name': 'Curie',
            'media_email': 'marie@example.com',
            'media_class_name': '10B',
            'media_topic': 'Social Media',
            'media_description': 'Need support for a workshop.',
        },
    )

    assert response.status_code == 302

    with app.app_context():
        ticket = MediaConsultingTicket.query.one()
        assert ticket.first_name == 'Marie'
        assert ticket.last_name == 'Curie'
        assert ticket.class_name == '10B'
        assert ticket.topic == 'Social Media'
        assert ticket.description == 'Need support for a workshop.'
        assert ticket.proposed_date is None
        assert ticket.status_id == 1


def test_public_media_consulting_ticket_view_renders_flask_wtf_response_form(client, app):
    with app.app_context():
        ticket = create_media_consulting_ticket(status_id=2)
        token = ticket.generate_token()

    response = client.get(f'/ticket/{token}')

    assert response.status_code == 200
    assert b'name="response_message"' in response.data
    assert b'Antwort senden' in response.data


def test_media_consulting_ticket_response_function(client, app, monkeypatch):
    monkeypatch.setattr('app.blueprints.main.tickets.notify_client', lambda ticket, message: None)

    with app.app_context():
        admin_id = create_admin_user()
        ticket = create_media_consulting_ticket(status_id=2)
        ticket_id = ticket.id

    login_as(client, admin_id)
    response = client.post(
        f'/ticket/{ticket_id}/submit_response',
        data={
            'ticket_type': 'medienberatung',
            'response_message': 'Thanks, we will review this.',
        },
    )

    assert response.status_code == 302
    with app.app_context():
        stored_ticket = db.session.get(MediaConsultingTicket, ticket_id)
        assert stored_ticket.status_id == 3
        assert TicketHistory.query.filter_by(ticket_type='medienberatung', ticket_id=ticket_id).count() == 1


def test_media_consulting_help_request_route(client, app, monkeypatch):
    monkeypatch.setattr('app.blueprints.main.tickets.notify_admin', lambda ticket, ticket_type, message: None)

    with app.app_context():
        admin_id = create_admin_user()
        ticket = create_media_consulting_ticket(status_id=2)
        ticket_id = ticket.id

    login_as(client, admin_id)
    response = client.post(
        f'/ticket/{ticket_id}/request_help',
        data={'ticket_type': 'medienberatung'},
    )

    assert response.status_code == 302


def test_media_consulting_ticket_close_route(client, app):
    with app.app_context():
        admin_id = create_admin_user()
        ticket = create_media_consulting_ticket(status_id=2)
        ticket_id = ticket.id

    login_as(client, admin_id)
    response = client.post(
        f'/ticket/{ticket_id}/mark_solved',
        data={'ticket_type': 'medienberatung'},
    )

    assert response.status_code == 302
    with app.app_context():
        stored_ticket = db.session.get(MediaConsultingTicket, ticket_id)
        assert stored_ticket.status_id == 4


def test_media_consulting_archive_lists_solved_ticket(client, app):
    with app.app_context():
        admin_id = create_admin_user()
        ticket = create_media_consulting_ticket(status_id=4, topic='Archive check')

    login_as(client, admin_id)
    response = client.get('/archiv')

    assert response.status_code == 200
    assert b'Medienberatung Ticket ID' in response.data
    assert b'Archive check' in response.data

