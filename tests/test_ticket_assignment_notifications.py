from pathlib import Path

import pytest
from flask import Flask
from flask_login import LoginManager
from flask_wtf import CSRFProtect

from app.blueprints.bp_admin import bp_admin
from app.blueprints.bp_auth import bp_auth
from app.models import (
    MediaConsultingTicket,
    Role,
    RoleEnum,
    TicketAssignmentNotification,
    TicketStatus,
    User,
    db,
)
from app.permission_seed import seed_permissions_and_roles
from app.blueprints.main import bp_main
from app.ticket_assignments import get_current_ticket_assignee


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / 'ticket_assignment.db'
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


def create_user(username, email, first_name, last_name, role_name, *, role=RoleEnum.MEMBER, active=True):
    assigned_role = Role.query.filter_by(name=role_name).one()
    user = User(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
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


def test_ticket_assignment_notification_flow(client, app, monkeypatch):
    sent_notifications = []

    def capture_notification(ticket, ticket_type, user, assigned_by_name=None):
        sent_notifications.append(
            {
                'ticket_id': ticket.id,
                'ticket_type': ticket_type,
                'user_id': user.id,
                'assigned_by_name': assigned_by_name,
            }
        )

    monkeypatch.setattr('app.blueprints.main.tickets.notify_user_about_ticket_assignment', capture_notification)

    with app.app_context():
        assigner_id = create_user(
            'teacher-assigner',
            'teacher@example.com',
            'Lena',
            'Lehr',
            'Teacher',
            role=RoleEnum.TEACHER,
        )
        assignee_one_id = create_user(
            'user-one',
            'user1@example.com',
            'Mila',
            'Muster',
            'User',
        )
        assignee_two_id = create_user(
            'user-two',
            'user2@example.com',
            'Nina',
            'Neu',
            'User',
        )
        ticket = create_media_consulting_ticket()
        ticket_id = ticket.id

    login_as(client, assigner_id)
    response = client.post(
        f'/ticket/{ticket_id}/assign',
        data={'ticket_type': 'medienberatung', 'assignee_id': assignee_one_id},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        ticket = db.session.get(MediaConsultingTicket, ticket_id)
        assert ticket.status_id == 2
        assert get_current_ticket_assignee('medienberatung', ticket_id).id == assignee_one_id
        notification = TicketAssignmentNotification.query.filter_by(
            user_id=assignee_one_id,
            ticket_id=ticket_id,
            read_at=None,
        ).one()
        assert notification.message == (
            f'Dir wurde das Medienberatung-Ticket #{ticket_id} von Lena Lehr zugewiesen.'
        )

    assert sent_notifications == [
        {
            'ticket_id': ticket_id,
            'ticket_type': 'medienberatung',
            'user_id': assignee_one_id,
            'assigned_by_name': 'Lena Lehr',
        }
    ]

    login_as(client, assignee_one_id)
    response = client.get('/', follow_redirects=True)
    assert response.status_code == 200
    assert b'Logout' in response.data

    with app.app_context():
        notification = TicketAssignmentNotification.query.filter_by(
            user_id=assignee_one_id,
            ticket_id=ticket_id,
            read_at=None,
        ).one()

    response = client.post(
        f'/ticket-assignment-notifications/{notification.id}/dismiss',
        follow_redirects=True,
    )
    assert response.status_code == 200

    response = client.get('/', follow_redirects=True)
    assert response.status_code == 200
    assert b'Logout' in response.data

    login_as(client, assigner_id)
    response = client.post(
        f'/ticket/{ticket_id}/assign',
        data={'ticket_type': 'medienberatung', 'assignee_id': assignee_two_id},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        ticket = db.session.get(MediaConsultingTicket, ticket_id)
        assert get_current_ticket_assignee('medienberatung', ticket_id).id == assignee_two_id
        first_notifications = TicketAssignmentNotification.query.filter_by(
            user_id=assignee_one_id,
            ticket_id=ticket_id,
        ).all()
        assert first_notifications
        assert all(notification.read_at is not None for notification in first_notifications)

        second_notification = TicketAssignmentNotification.query.filter_by(
            user_id=assignee_two_id,
            ticket_id=ticket_id,
            read_at=None,
        ).one()
        assert second_notification.message == (
            f'Dir wurde das Medienberatung-Ticket #{ticket_id} von Lena Lehr zugewiesen.'
        )

    response = client.post(
        f'/ticket/{ticket_id}/assign',
        data={'ticket_type': 'medienberatung', 'assignee_id': ''},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        ticket = db.session.get(MediaConsultingTicket, ticket_id)
        assert ticket.status_id == 1
        assert get_current_ticket_assignee('medienberatung', ticket_id) is None
        second_notifications = TicketAssignmentNotification.query.filter_by(
            user_id=assignee_two_id,
            ticket_id=ticket_id,
        ).all()
        assert second_notifications
        assert all(notification.read_at is not None for notification in second_notifications)

