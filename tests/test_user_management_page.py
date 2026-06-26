from pathlib import Path

import pytest
from flask import Flask
from flask_login import LoginManager
from flask_wtf import CSRFProtect

from app.blueprints.bp_admin import bp_admin
from app.blueprints.bp_auth import bp_auth
from app.models import Permission, Role, RoleEnum, User, UserPermissionOverride, db
from app.permission_seed import seed_permissions_and_roles
from app.routes import bp_main


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / 'user_management.db'
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


def create_role(name, permission_names):
    role = Role(name=name, description=f'{name} role', is_system_role=False)
    db.session.add(role)
    for permission_name in permission_names:
        permission = Permission.query.filter_by(name=permission_name).one()
        role.permissions.append(permission)
    db.session.commit()
    return role


def create_user(username, email, *, roles=None, active=True, role=RoleEnum.MEMBER):
    user = User(
        username=username,
        email=email,
        first_name='Test',
        last_name='User',
        role=role,
        active=active,
    )
    db.session.add(user)
    for assigned_role in roles or []:
        user.roles.append(assigned_role)
    db.session.commit()
    return user


def test_user_details_require_users_view(client, app):
    with app.app_context():
        viewer_role = create_role('Viewer', ['users.view'])
        target_user = create_user('target-user', 'target@example.com')
        viewer = create_user('viewer-user', 'viewer@example.com', roles=[viewer_role])
        target_user_id = target_user.id
        viewer_id = viewer.id

    login_as(client, viewer_id)
    response = client.get(f'/members/user/{target_user_id}')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['user']['id'] == target_user_id
    assert payload['capabilities']['can_manage_roles'] is False
    assert payload['capabilities']['can_manage_permissions'] is False


def test_roles_can_only_be_changed_with_manage_roles(client, app):
    with app.app_context():
        admin_role = Role.query.filter_by(name='Admin').one()
        teacher_role = Role.query.filter_by(name='Teacher').one()
        target_user = create_user('target-user', 'target@example.com')
        admin = create_user('admin-user', 'admin@example.com', roles=[admin_role], role=RoleEnum.ADMIN)
        target_user_id = target_user.id
        admin_id = admin.id
        teacher_role_id = teacher_role.id

    login_as(client, admin_id)
    add_response = client.post(
        f'/members/user/{target_user_id}/roles',
        json={'action': 'add', 'role_id': teacher_role_id},
    )
    assert add_response.status_code == 200
    add_payload = add_response.get_json()
    assert [role['name'] for role in add_payload['active_roles']] == ['Teacher']

    remove_response = client.post(
        f'/members/user/{target_user_id}/roles',
        json={'action': 'remove', 'role_id': teacher_role_id},
    )
    assert remove_response.status_code == 200
    remove_payload = remove_response.get_json()
    assert remove_payload['active_roles'] == []


def test_permission_overrides_can_only_be_changed_with_manage_permissions(client, app):
    with app.app_context():
        admin_role = Role.query.filter_by(name='Admin').one()
        permission = Permission.query.filter_by(name='tickets.archive').one()
        target_user = create_user('target-user', 'target@example.com')
        admin = create_user('admin-user', 'admin@example.com', roles=[admin_role], role=RoleEnum.ADMIN)
        target_user_id = target_user.id
        admin_id = admin.id
        permission_id = permission.id

    login_as(client, admin_id)
    allow_response = client.post(
        f'/members/user/{target_user_id}/permissions',
        json={'action': 'allow', 'permission_id': permission_id, 'reason': 'Needed for testing'},
    )
    assert allow_response.status_code == 200
    allow_payload = allow_response.get_json()
    assert allow_payload['permission_sources']['tickets.archive'] == ['user_allow']
    assert allow_payload['effective_permissions'] == ['tickets.archive']

    with app.app_context():
        stored_override = UserPermissionOverride.query.filter_by(
            user_id=target_user_id,
            permission_id=permission_id,
        ).one()
        assert stored_override.allowed is True
        assert stored_override.reason == 'Needed for testing'

    deny_response = client.post(
        f'/members/user/{target_user_id}/permissions',
        json={'action': 'deny', 'permission_id': permission_id, 'reason': 'Restricted'},
    )
    assert deny_response.status_code == 200
    deny_payload = deny_response.get_json()
    assert deny_payload['permission_sources']['tickets.archive'] == ['user_deny']
    assert deny_payload['effective_permissions'] == []

    remove_response = client.post(
        f'/members/user/{target_user_id}/permissions',
        json={'action': 'remove', 'permission_id': permission_id},
    )
    assert remove_response.status_code == 200
    remove_payload = remove_response.get_json()
    assert 'tickets.archive' not in remove_payload['permission_sources']
    assert remove_payload['effective_permissions'] == []


def test_user_without_rights_gets_403(client, app):
    with app.app_context():
        target_user = create_user('target-user', 'target@example.com')
        plain_user = create_user('plain-user', 'plain@example.com')
        target_user_id = target_user.id
        plain_user_id = plain_user.id

    login_as(client, plain_user_id)
    response = client.get(f'/members/user/{target_user_id}')

    assert response.status_code == 403


def test_user_without_manage_roles_gets_403_on_role_changes(client, app):
    with app.app_context():
        plain_user = create_user('plain-user', 'plain@example.com')
        target_user = create_user('target-user', 'target@example.com')
        teacher_role = Role.query.filter_by(name='Teacher').one()
        plain_user_id = plain_user.id
        target_user_id = target_user.id
        teacher_role_id = teacher_role.id

    login_as(client, plain_user_id)
    response = client.post(
        f'/members/user/{target_user_id}/roles',
        json={'action': 'add', 'role_id': teacher_role_id},
    )

    assert response.status_code == 403


def test_user_without_manage_permissions_gets_403_on_permission_changes(client, app):
    with app.app_context():
        plain_user = create_user('plain-user', 'plain@example.com')
        target_user = create_user('target-user', 'target@example.com')
        permission = Permission.query.filter_by(name='tickets.archive').one()
        plain_user_id = plain_user.id
        target_user_id = target_user.id
        permission_id = permission.id

    login_as(client, plain_user_id)
    response = client.post(
        f'/members/user/{target_user_id}/permissions',
        json={'action': 'allow', 'permission_id': permission_id},
    )

    assert response.status_code == 403


def test_effective_permissions_show_correct_sources(client, app):
    with app.app_context():
        admin_role = Role.query.filter_by(name='Admin').one()
        support_role = create_role('Support', ['tickets.view', 'tickets.reply'])
        deny_permission = Permission.query.filter_by(name='tickets.reply').one()
        allow_permission = Permission.query.filter_by(name='tickets.archive').one()
        target_user = create_user('target-user', 'target@example.com', roles=[support_role])
        target_user.permission_overrides.append(
            UserPermissionOverride(permission=deny_permission, allowed=False, reason='Blocked')
        )
        target_user.permission_overrides.append(
            UserPermissionOverride(permission=allow_permission, allowed=True, reason='Required')
        )
        db.session.commit()
        admin = create_user('admin-user', 'admin@example.com', roles=[admin_role], role=RoleEnum.ADMIN)
        target_user_id = target_user.id
        admin_id = admin.id

    login_as(client, admin_id)
    response = client.get(f'/members/user/{target_user_id}')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['permission_sources']['tickets.view'] == ['role:Support']
    assert payload['permission_sources']['tickets.reply'] == ['role:Support', 'user_deny']
    assert payload['permission_sources']['tickets.archive'] == ['user_allow']
    assert 'tickets.reply' not in payload['effective_permissions']
    assert 'tickets.view' in payload['effective_permissions']
    assert 'tickets.archive' in payload['effective_permissions']
