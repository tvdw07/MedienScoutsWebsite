import pytest
from werkzeug.datastructures import MultiDict

from app.forms import (
    LoginForm,
    MEDIA_CONSULTING_TOPIC_CHOICES,
    PasswordResetForm,
    SendTicketForm,
    TicketResponseForm,
)
from app.models import (
    MediaConsultingTicket,
    MediaConsultingTicketUser,
    Permission,
    Role,
    RoleEnum,
    TicketHistory,
    User,
    db,
)
from tests.helpers import create_test_app, extract_csrf_token, login_as


@pytest.fixture()
def app(tmp_path):
    app = create_test_app(tmp_path, csrf_enabled=False, database_name='regressions.db')
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def csrf_app(tmp_path):
    app = create_test_app(tmp_path, csrf_enabled=True, database_name='regressions_csrf.db')
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def csrf_client(csrf_app):
    return csrf_app.test_client()


def create_role(name, permission_names=None, *, is_system_role=False):
    role = Role(name=name, description=f'{name} role', is_system_role=is_system_role)
    db.session.add(role)
    for permission_name in permission_names or []:
        permission = Permission.query.filter_by(name=permission_name).one()
        role.permissions.append(permission)
    db.session.commit()
    db.session.refresh(role)
    return role


def create_user(username, email, *, password='Secret123!', roles=None, active=True, role=RoleEnum.MEMBER):
    user = User(
        username=username,
        email=email,
        first_name='Test',
        last_name='User',
        role=role,
        active=active,
    )
    if password:
        user.set_password(password)
    db.session.add(user)
    for assigned_role in roles or []:
        user.roles.append(assigned_role)
    db.session.commit()
    db.session.refresh(user)
    return user


def create_media_ticket(**overrides):
    ticket = MediaConsultingTicket(
        first_name=overrides.get('first_name', 'Ada'),
        last_name=overrides.get('last_name', 'Lovelace'),
        email=overrides.get('email', 'ada@example.com'),
        class_name=overrides.get('class_name', '9A'),
        topic=overrides.get('topic', 'Social Media'),
        description=overrides.get('description', 'Need help with media literacy.'),
        proposed_date=overrides.get('proposed_date'),
        status_id=overrides.get('status_id', 2),
    )
    db.session.add(ticket)
    db.session.commit()
    db.session.refresh(ticket)
    return ticket


def test_login_form_requires_credentials(app):
    with app.test_request_context('/login', method='POST'):
        form = LoginForm(formdata=MultiDict({}))

        assert form.validate() is False
        assert form.username.errors == ['This field is required.']
        assert form.password.errors == ['This field is required.']


def test_password_reset_form_enforces_password_policy(app):
    too_short_password = 'Aa1!'

    with app.test_request_context('/reset_password/token/1', method='POST'):
        form = PasswordResetForm(
            formdata=MultiDict(
                {
                    'password': too_short_password,
                    'confirm_password': too_short_password,
                }
            )
        )

        assert form.validate() is False
        assert form.password.errors == ['Password must be at least 8 characters long.']


def test_media_consulting_topic_choices_remain_stable(app):
    with app.test_request_context('/send_ticket'):
        form = SendTicketForm()

        assert [value for value, _ in form.media_topic.choices][1:] == [
            value for value, _ in MEDIA_CONSULTING_TOPIC_CHOICES
        ]


def test_send_ticket_form_requires_media_consulting_topic(app):
    with app.test_request_context('/send_ticket', method='POST'):
        form = SendTicketForm(
            formdata=MultiDict(
                {
                    'ticket_type': 'medienberatung',
                    'media_first_name': 'Ada',
                    'media_last_name': 'Lovelace',
                    'media_email': 'ada@example.com',
                    'media_class_name': '9A',
                    'media_description': 'Need support for the classroom workshop.',
                }
            )
        )

        assert form.validate() is False
        assert form.media_topic.errors == ['Dieses Feld ist erforderlich.']


def test_ticket_response_form_requires_message(app):
    with app.test_request_context('/ticket/1', method='POST'):
        form = TicketResponseForm(formdata=MultiDict({'response_message': '   '}))

        assert form.validate() is False
        assert form.response_message.errors == ['This field is required.']


def test_login_requires_csrf_token(csrf_client):
    response = csrf_client.post(
        '/login',
        data={
            'username': 'csrf-login-user',
            'password': 'Secret123!',
        },
    )

    assert response.status_code == 400


def test_login_accepts_valid_csrf_token(csrf_client, csrf_app):
    with csrf_app.app_context():
        user = create_user('valid-login-user', 'valid-login@example.com')
        user_id = user.id
        username = user.username

    login_page = csrf_client.get('/login')
    csrf_token = extract_csrf_token(login_page.data)

    response = csrf_client.post(
        '/login',
        data={
            'csrf_token': csrf_token,
            'username': username,
            'password': 'Secret123!',
        },
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/')

    with csrf_app.app_context():
        stored_user = db.session.get(User, user_id)
        assert stored_user is not None
        assert stored_user.last_login is not None

    with csrf_client.session_transaction() as session:
        assert session['_user_id'] == str(user_id)


def test_inactive_user_cannot_log_in_with_valid_csrf(csrf_client, csrf_app):
    with csrf_app.app_context():
        user = create_user('inactive-login-user', 'inactive-login@example.com', active=False)
        user_id = user.id
        username = user.username

    login_page = csrf_client.get('/login')
    csrf_token = extract_csrf_token(login_page.data)

    response = csrf_client.post(
        '/login',
        data={
            'csrf_token': csrf_token,
            'username': username,
            'password': 'Secret123!',
        },
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login')

    with csrf_app.app_context():
        stored_user = db.session.get(User, user_id)
        assert stored_user is not None
        assert stored_user.last_login is None

    with csrf_client.session_transaction() as session:
        assert '_user_id' not in session


def test_send_ticket_requires_csrf_token(csrf_client, monkeypatch):
    monkeypatch.setattr('app.blueprints.main.tickets.send_ticket_link', lambda ticket: None)

    response = csrf_client.post(
        '/send_ticket',
        data={
            'ticket_type': 'medienberatung',
            'media_first_name': 'Ada',
            'media_last_name': 'Lovelace',
            'media_email': 'ada@example.com',
            'media_class_name': '9A',
            'media_topic': 'Social Media',
            'media_description': 'Need help with media literacy.',
        },
    )

    assert response.status_code == 400


def test_send_ticket_with_csrf_creates_media_consulting_ticket(csrf_client, csrf_app, monkeypatch):
    monkeypatch.setattr('app.blueprints.main.tickets.send_ticket_link', lambda ticket: None)

    response_page = csrf_client.get('/send_ticket')
    csrf_token = extract_csrf_token(response_page.data)

    response = csrf_client.post(
        '/send_ticket',
        data={
            'csrf_token': csrf_token,
            'ticket_type': 'medienberatung',
            'media_first_name': 'Marie',
            'media_last_name': 'Curie',
            'media_email': 'marie@example.com',
            'media_class_name': '10B',
            'media_topic': 'Social Media',
            'media_description': 'Workshop support request.',
        },
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/')

    with csrf_app.app_context():
        ticket = MediaConsultingTicket.query.one()
        assert ticket.first_name == 'Marie'
        assert ticket.last_name == 'Curie'
        assert ticket.email == 'marie@example.com'
        assert ticket.class_name == '10B'
        assert ticket.topic == 'Social Media'
        assert ticket.description == 'Workshop support request.'
        assert ticket.status_id == 1


def test_public_ticket_reply_with_csrf_records_history(csrf_client, csrf_app, monkeypatch):
    monkeypatch.setattr('app.blueprints.main.tickets.notify_user_about_ticket_change', lambda ticket, message, ticket_type: None)

    with csrf_app.app_context():
        ticket = create_media_ticket(status_id=2)
        ticket_id = ticket.id
        token = ticket.generate_token()

    reply_page = csrf_client.get(f'/ticket/{token}')
    csrf_token = extract_csrf_token(reply_page.data)

    response = csrf_client.post(
        f'/ticket/{token}',
        data={
            'csrf_token': csrf_token,
            'response_message': 'We will review this with the school team.',
        },
    )

    assert response.status_code == 302

    with csrf_app.app_context():
        entries = TicketHistory.query.filter_by(ticket_type='medienberatung', ticket_id=ticket_id).all()
        assert len(entries) == 1
        assert entries[0].message == 'We will review this with the school team.'


def test_media_consulting_ticket_details_respect_assignment_and_permissions(client, app):
    with app.app_context():
        viewer_role = create_role('TicketViewer', ['tickets.view'])
        viewer = create_user(
            'ticket-viewer',
            'ticket-viewer@example.com',
            roles=[viewer_role],
        )
        ticket = create_media_ticket(status_id=2, topic='Social Media')
        viewer_id = viewer.id
        ticket_id = ticket.id

    login_as(client, viewer_id)

    denied_response = client.get(f'/ticket/medienberatung/{ticket_id}/details')
    assert denied_response.status_code == 302
    assert denied_response.headers['Location'].endswith('/ticketverwaltung')

    with app.app_context():
        db.session.add(
            MediaConsultingTicketUser(
                media_consulting_ticket_id=ticket_id,
                user_id=viewer_id,
            )
        )
        db.session.commit()

    allowed_response = client.get(f'/ticket/medienberatung/{ticket_id}/details')
    assert allowed_response.status_code == 200
    assert b'Medienberatung Ticket' in allowed_response.data
    assert b'name="response_message"' in allowed_response.data

