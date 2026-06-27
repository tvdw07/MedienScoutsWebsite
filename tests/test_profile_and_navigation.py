from pathlib import Path

import pytest
from flask import Flask
from flask_login import LoginManager
from flask_wtf import CSRFProtect

from app.blueprints.bp_admin import bp_admin
from app.blueprints.bp_auth import bp_auth
from app.models import Permission, Role, RoleEnum, User, db
from app.permission_seed import seed_permissions_and_roles
from app.routes import bp_main


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / 'profile_navigation.db'
    templates_path = Path(__file__).resolve().parents[1] / 'app' / 'templates'

    app = Flask(__name__, template_folder=str(templates_path))
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{database_path.as_posix()}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY='test-secret-key',
        SECURITY_PASSWORD_SALT='test-security-salt',
        WTF_CSRF_ENABLED=False,
        TICKET_TOKEN_MAX_AGE_SECONDS=3600,
        UPLOAD_FOLDER=str(tmp_path / 'uploads'),
        USER_PROFILES=str(tmp_path / 'profiles'),
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
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login_as(client, user):
    user_id = user if isinstance(user, int) else user.id
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True


def create_role(name, permission_names=None, *, is_system_role=False):
    role = Role(name=name, description=f'{name} role', is_system_role=is_system_role)
    db.session.add(role)
    db.session.flush()
    for permission_name in permission_names or []:
        permission = Permission.query.filter_by(name=permission_name).one()
        role.permissions.append(permission)
    db.session.commit()
    return role


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
    return user.id


def test_profile_shows_roles(client, app):
    with app.app_context():
        media_scout_role = db.session.query(Role).filter_by(name='MediaScout').one()
        helper_role = create_role('Helper')
        user_id = create_user('profile-user', 'profile@example.com', roles=[media_scout_role, helper_role])

    login_as(client, user_id)
    response = client.get('/profile')

    assert response.status_code == 200
    assert b'Assigned roles' in response.data
    assert b'MediaScout' in response.data
    assert b'Helper' in response.data


def test_profile_shows_no_internal_permissions(client, app):
    with app.app_context():
        media_scout_role = db.session.query(Role).filter_by(name='MediaScout').one()
        user_id = create_user('profile-user', 'profile@example.com', roles=[media_scout_role])

    login_as(client, user_id)
    response = client.get('/profile')

    assert response.status_code == 200
    assert b'Effective permissions' not in response.data
    assert b'Permission sources' not in response.data
    assert b'Override' not in response.data
    assert b'tickets.view' not in response.data
    assert b'users.manage_roles' not in response.data


def test_admin_sees_admin_navigation(client, app):
    with app.app_context():
        admin_role = db.session.query(Role).filter_by(name='Admin').one()
        admin_id = create_user('admin-user', 'admin@example.com', roles=[admin_role], role=RoleEnum.ADMIN)

    login_as(client, admin_id)
    response = client.get('/profile')

    assert response.status_code == 200
    assert b'Admin Panel' in response.data
    assert b'href="/roles/administration"' in response.data
    assert b'href="/members/administration"' in response.data


def test_mediascout_sees_no_roles_management(client, app):
    with app.app_context():
        media_scout_role = db.session.query(Role).filter_by(name='MediaScout').one()
        user_id = create_user('mediascout-user', 'mediascout@example.com', roles=[media_scout_role])

    login_as(client, user_id)
    response = client.get('/profile')

    assert response.status_code == 200
    assert b'href="/roles/administration"' not in response.data
    assert b'href="/members/administration"' not in response.data


def test_user_without_ticket_rights_sees_no_internal_ticket_links(client, app):
    with app.app_context():
        user_role = db.session.query(Role).filter_by(name='User').one()
        user_id = create_user('plain-user', 'plain@example.com', roles=[user_role])

    login_as(client, user_id)
    response = client.get('/profile')

    assert response.status_code == 200
    assert b'href="/ticketverwaltung"' not in response.data
    assert b'href="/archiv"' not in response.data


def test_legacy_route_and_navigation_are_removed(client, app):
    with app.app_context():
        admin_role = db.session.query(Role).filter_by(name='Admin').one()
        admin_id = create_user('admin-forum-check', 'admin-forum-check@example.com', roles=[admin_role], role=RoleEnum.ADMIN)

    login_as(client, admin_id)
    profile_response = client.get('/profile')
    legacy_response = client.get('/forum')

    assert profile_response.status_code == 200
    assert b'href="/forum"' not in profile_response.data
    assert legacy_response.status_code == 404


def test_message_model_is_not_registered(app):
    with app.app_context():
        assert 'message' not in db.metadata.tables
