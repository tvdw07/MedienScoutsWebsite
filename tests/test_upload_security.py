import re
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.models import Permission, ProblemTicket, ProblemTicketUser, Role, RoleEnum, User, db
from tests.helpers import create_test_app, login_as


@pytest.fixture()
def app(tmp_path):
    app = create_test_app(tmp_path, csrf_enabled=False, database_name='upload_security.db')
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def create_user(username, email, *, roles=None, role=RoleEnum.MEMBER):
    user = User(
        username=username,
        email=email,
        first_name='Test',
        last_name='User',
        role=role,
        active=True,
    )
    db.session.add(user)
    db.session.flush()
    for assigned_role in roles or []:
        user.roles.append(assigned_role)
    db.session.commit()
    return user


def make_image_bytes(format='PNG', color=(255, 0, 0)):
    buffer = BytesIO()
    Image.new('RGB', (1, 1), color).save(buffer, format=format)
    buffer.seek(0)
    return buffer


def make_invalid_image_bytes():
    return BytesIO(b'not-an-image')


def _upload_root(app):
    return Path(app.config['UPLOAD_ROOT'])


def _profile_upload_path(app, filename):
    return _upload_root(app) / app.config['PROFILE_PICTURE_FOLDER'] / filename


def _ticket_upload_path(app, filename):
    return _upload_root(app) / app.config['TICKET_ATTACHMENT_FOLDER'] / filename


def create_role(name, permission_names=None, *, is_system_role=False):
    role = Role(name=name, description=f'{name} role', is_system_role=is_system_role)
    db.session.add(role)
    db.session.flush()
    for permission_name in permission_names or []:
        permission = Permission.query.filter_by(name=permission_name).one()
        role.permissions.append(permission)
    db.session.commit()
    return role


def test_profile_upload_uses_uuid_filename_and_serves_own_picture(client, app):
    with app.app_context():
        user_role = Role.query.filter_by(name='User').one()
        owner = create_user('profile-owner', 'owner@example.com', roles=[user_role])
        owner_id = owner.id

    login_as(client, owner_id)
    response = client.post(
        '/profile',
        data={
            'first_name': 'Profile',
            'last_name': 'Owner',
            'email': 'owner@example.com',
            'profile_image': (make_image_bytes('PNG'), 'owner.png'),
        },
        content_type='multipart/form-data',
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/profile')

    with app.app_context():
        stored_user = db.session.get(User, owner_id)
        stored_filename = stored_user.profile_picture
        assert stored_filename is not None
        assert re.fullmatch(r'[0-9a-f-]{36}\.png', stored_filename)
        assert stored_user.profile_picture_original_name == 'owner.png'
        stored_path = _profile_upload_path(app, stored_filename)
        assert stored_path.exists()
        assert 'static' not in stored_path.parts

    picture_response = client.get(f'/profile_picture/{owner_id}')
    assert picture_response.status_code == 200
    assert picture_response.headers['Content-Type'].startswith('image/png')
    assert picture_response.data.startswith(b'\x89PNG')

    assert client.get(f'/static/uploads/profile_pictures/{stored_filename}').status_code == 404


def test_profile_picture_route_allows_users_view_for_other_profiles(client, app):
    with app.app_context():
        user_role = Role.query.filter_by(name='User').one()
        viewer_role = create_role('ProfileViewer', ['users.view'])
        owner = create_user('profile-target', 'target@example.com', roles=[user_role])
        viewer = create_user('profile-viewer', 'viewer@example.com', roles=[viewer_role])
        owner_id = owner.id
        viewer_id = viewer.id
        profile_path = _profile_upload_path(app, 'example.png')
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (1, 1), (255, 0, 0)).save(profile_path, format='PNG')
        owner.profile_picture = 'example.png'
        db.session.commit()

    login_as(client, viewer_id)
    response = client.get(f'/profile_picture/{owner_id}')

    assert response.status_code == 200
    assert response.headers['Content-Type'].startswith('image/png')


def test_profile_picture_route_denies_unauthorized_users(client, app):
    with app.app_context():
        user_role = Role.query.filter_by(name='User').one()
        owner = create_user('profile-target', 'target@example.com', roles=[user_role])
        plain_user = create_user('plain-user', 'plain@example.com', roles=[user_role])
        owner_id = owner.id
        plain_user_id = plain_user.id
        owner.profile_picture = 'example.png'
        db.session.commit()

    login_as(client, plain_user_id)
    response = client.get(f'/profile_picture/{owner_id}')

    assert response.status_code == 403


def test_profile_upload_rejects_oversized_image(client, app):
    with app.app_context():
        user_role = Role.query.filter_by(name='User').one()
        owner = create_user('profile-owner', 'owner@example.com', roles=[user_role])
        owner_id = owner.id

    login_as(client, owner_id)
    response = client.post(
        '/profile',
        data={
            'first_name': 'Profile',
            'last_name': 'Owner',
            'email': 'owner@example.com',
            'profile_image': (BytesIO(b'a' * (2 * 1024 * 1024 + 1)), 'oversized.png'),
        },
        content_type='multipart/form-data',
    )

    assert response.status_code == 413


def test_profile_upload_rejects_invalid_image(client, app):
    with app.app_context():
        user_role = Role.query.filter_by(name='User').one()
        owner = create_user('profile-owner', 'owner@example.com', roles=[user_role])
        owner_id = owner.id

    login_as(client, owner_id)
    response = client.post(
        '/profile',
        data={
            'first_name': 'Profile',
            'last_name': 'Owner',
            'email': 'owner@example.com',
            'profile_image': (make_invalid_image_bytes(), 'broken.png'),
        },
        content_type='multipart/form-data',
    )

    assert response.status_code == 400

    with app.app_context():
        stored_user = db.session.get(User, owner_id)
        assert stored_user.profile_picture is None


def test_ticket_upload_uses_uuid_filename_and_serves_attachment(client, app, monkeypatch):
    monkeypatch.setattr('app.blueprints.main.tickets.send_ticket_link', lambda ticket: None)

    with app.app_context():
        viewer_role = create_role('TicketViewer', ['tickets.view_all'])
        viewer = create_user('ticket-viewer', 'viewer@example.com', roles=[viewer_role])
        viewer_id = viewer.id

    response = client.post(
        '/send_ticket',
        data={
            'ticket_type': 'problem',
            'problem_first_name': 'Ada',
            'problem_last_name': 'Lovelace',
            'problem_email': 'ada@example.com',
            'problem_class_name': '9A',
            'problem_serial_number': 'SN-42',
            'problem_description': 'Broken device.',
            'problem_steps': 'neugestartet',
            'photo': (make_image_bytes('JPEG'), 'ticket.jpg'),
        },
        content_type='multipart/form-data',
    )

    assert response.status_code == 302

    with app.app_context():
        ticket = ProblemTicket.query.one()
        ticket_id = ticket.id
        stored_filename = ticket.photo
        assert stored_filename is not None
        assert re.fullmatch(r'[0-9a-f-]{36}\.jpg', stored_filename)
        assert ticket.photo_original_name == 'ticket.jpg'
        stored_path = _ticket_upload_path(app, stored_filename)
        assert stored_path.exists()
        assert 'static' not in stored_path.parts

    login_as(client, viewer_id)
    attachment_response = client.get(f'/ticket/problem/{ticket_id}/attachment')

    assert attachment_response.status_code == 200
    assert attachment_response.headers['Content-Type'].startswith('image/jpeg')
    assert 'no-store' in attachment_response.headers['Cache-Control']
    assert 'private' in attachment_response.headers['Cache-Control']
    assert attachment_response.data.startswith(b'\xff\xd8')

    assert client.get(f'/static/uploads/tickets/{stored_filename}').status_code == 404


def test_public_problem_ticket_view_displays_uploaded_attachment(client, app, monkeypatch):
    monkeypatch.setattr('app.blueprints.main.tickets.send_ticket_link', lambda ticket: None)

    response = client.post(
        '/send_ticket',
        data={
            'ticket_type': 'problem',
            'problem_first_name': 'Ada',
            'problem_last_name': 'Lovelace',
            'problem_email': 'ada@example.com',
            'problem_class_name': '9A',
            'problem_serial_number': 'SN-42',
            'problem_description': 'Broken device.',
            'problem_steps': 'neugestartet',
            'photo': (make_image_bytes('PNG'), 'stundenplan.png'),
        },
        content_type='multipart/form-data',
    )

    assert response.status_code == 302

    with app.app_context():
        ticket = ProblemTicket.query.one()
        token = ticket.generate_token()

    page_response = client.get(f'/ticket/{token}')

    assert page_response.status_code == 200
    assert f'/ticket/{token}/attachment'.encode() in page_response.data
    assert b'Datei: stundenplan.png' in page_response.data

    attachment_response = client.get(f'/ticket/{token}/attachment')
    assert attachment_response.status_code == 200
    assert attachment_response.headers['Content-Type'].startswith('image/png')
    assert 'no-store' in attachment_response.headers['Cache-Control']
    assert attachment_response.data.startswith(b'\x89PNG')


def test_public_ticket_attachment_route_rejects_invalid_token(client):
    response = client.get('/ticket/not-a-real-token/attachment')

    assert response.status_code == 404


def test_ticket_attachment_route_denies_unauthorized_users(client, app, monkeypatch):
    monkeypatch.setattr('app.blueprints.main.tickets.send_ticket_link', lambda ticket: None)

    with app.app_context():
        user_role = Role.query.filter_by(name='User').one()
        owner = create_user('ticket-owner', 'owner@example.com', roles=[user_role])
        plain_user = create_user('plain-user', 'plain@example.com', roles=[user_role])
        owner_id = owner.id
        plain_user_id = plain_user.id

        ticket = ProblemTicket(
            first_name='Ada',
            last_name='Lovelace',
            email='ada@example.com',
            class_name='9A',
            problem_description='Broken device.',
            steps_taken='neugestartet',
            photo='example.jpg',
            status_id=1,
        )
        db.session.add(ticket)
        db.session.flush()
        db.session.add(ProblemTicketUser(problem_ticket_id=ticket.id, user_id=owner_id))
        db.session.commit()
        ticket_id = ticket.id

    login_as(client, plain_user_id)
    response = client.get(f'/ticket/problem/{ticket_id}/attachment')

    assert response.status_code == 403


def test_ticket_upload_rejects_oversized_image(client, app, monkeypatch):
    monkeypatch.setattr('app.blueprints.main.tickets.send_ticket_link', lambda ticket: None)

    response = client.post(
        '/send_ticket',
        data={
            'ticket_type': 'problem',
            'problem_first_name': 'Ada',
            'problem_last_name': 'Lovelace',
            'problem_email': 'ada@example.com',
            'problem_class_name': '9A',
            'problem_serial_number': 'SN-42',
            'problem_description': 'Broken device.',
            'problem_steps': 'neugestartet',
            'photo': (BytesIO(b'a' * (5 * 1024 * 1024 + 1)), 'oversized.jpg'),
        },
        content_type='multipart/form-data',
    )

    assert response.status_code == 413


def test_ticket_upload_rejects_invalid_image(client, app, monkeypatch):
    monkeypatch.setattr('app.blueprints.main.tickets.send_ticket_link', lambda ticket: None)

    response = client.post(
        '/send_ticket',
        data={
            'ticket_type': 'problem',
            'problem_first_name': 'Ada',
            'problem_last_name': 'Lovelace',
            'problem_email': 'ada@example.com',
            'problem_class_name': '9A',
            'problem_serial_number': 'SN-42',
            'problem_description': 'Broken device.',
            'problem_steps': 'neugestartet',
            'photo': (make_invalid_image_bytes(), 'broken.png'),
        },
        content_type='multipart/form-data',
    )

    assert response.status_code == 400

    with app.app_context():
        assert ProblemTicket.query.count() == 0


def test_ticket_upload_accepts_valid_image(client, app, monkeypatch):
    monkeypatch.setattr('app.blueprints.main.tickets.send_ticket_link', lambda ticket: None)

    response = client.post(
        '/send_ticket',
        data={
            'ticket_type': 'problem',
            'problem_first_name': 'Ada',
            'problem_last_name': 'Lovelace',
            'problem_email': 'ada@example.com',
            'problem_class_name': '9A',
            'problem_serial_number': 'SN-42',
            'problem_description': 'Broken device.',
            'problem_steps': 'neugestartet',
            'photo': (make_image_bytes('PNG'), 'accepted.png'),
        },
        content_type='multipart/form-data',
    )

    assert response.status_code == 302

    with app.app_context():
        ticket = ProblemTicket.query.one()
        assert ticket.photo_original_name == 'accepted.png'

