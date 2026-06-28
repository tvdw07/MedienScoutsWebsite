from pathlib import Path
import re

import pytest
from flask import Flask
from flask_login import LoginManager
from flask_wtf import CSRFProtect

from app.blueprints.bp_admin import bp_admin
from app.blueprints.bp_auth import bp_auth
from app.models import Permission, Role, RoleEnum, User, db
from app.permission_seed import seed_permissions_and_roles
from app.blueprints.main import bp_main


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / 'role_management.db'
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
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login_as(client, user):
    user_id = user if isinstance(user, int) else user.id
    with client.application.app_context():
        resolved_user = db.session.get(User, user_id)
    with client.session_transaction() as session:
        session['_user_id'] = resolved_user.get_id()
        session['_fresh'] = True


def create_role(name, permission_names, *, is_system_role=False):
    role = Role(name=name, description=f'{name} role', is_system_role=is_system_role)
    db.session.add(role)
    db.session.flush()
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
    db.session.flush()
    for assigned_role in roles or []:
        user.roles.append(assigned_role)
    db.session.commit()
    return user


def test_roles_list_requires_roles_view(client, app):
    with app.app_context():
        viewer_role = create_role('RoleViewer', ['roles.view'])
        viewer = create_user('role-viewer', 'viewer@example.com', roles=[viewer_role])
        viewer_id = viewer.id

    login_as(client, viewer_id)
    response = client.get('/roles/administration')

    assert response.status_code == 200
    assert b'Role Management' in response.data


def test_role_create_button_submits_the_modal_form(client, app):
    with app.app_context():
        creator_role = create_role('RoleCreator', ['roles.view', 'roles.create'])
        creator = create_user('role-creator', 'creator@example.com', roles=[creator_role])
        creator_id = creator.id

    login_as(client, creator_id)
    response = client.get('/roles/administration')

    assert response.status_code == 200
    assert re.search(
        rb'<button\b(?=[^>]*id="saveRoleBtn")(?=[^>]*type="submit")(?=[^>]*form="roleForm")[^>]*>',
        response.data,
    )


def test_role_create_requires_roles_create(client, app):
    with app.app_context():
        creator_role = create_role('RoleCreator', ['roles.create'])
        creator = create_user('role-creator', 'creator@example.com', roles=[creator_role])
        creator_id = creator.id

    login_as(client, creator_id)
    response = client.post(
        '/roles',
        json={'name': 'Support', 'description': 'Support team'},
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload['role']['name'] == 'Support'
    assert payload['role']['description'] == 'Support team'

    with app.app_context():
        created_role = db.session.query(Role).filter_by(name='Support').one()
        assert created_role.is_system_role is False


def test_role_edit_requires_roles_edit(client, app):
    with app.app_context():
        editor_role = create_role('RoleEditor', ['roles.edit'])
        target_role = create_role('SupportTeam', ['tickets.view'])
        editor = create_user('role-editor', 'editor@example.com', roles=[editor_role])
        editor_id = editor.id
        target_role_id = target_role.id

    login_as(client, editor_id)
    response = client.post(
        f'/roles/{target_role_id}/edit',
        json={'name': 'Support Plus', 'description': 'Updated description'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['role']['name'] == 'Support Plus'
    assert payload['role']['description'] == 'Updated description'

    with app.app_context():
        stored_role = db.session.get(Role, target_role_id)
        assert stored_role.name == 'Support Plus'
        assert stored_role.description == 'Updated description'


def test_system_role_cannot_be_deleted(client, app):
    with app.app_context():
        delete_role = create_role('RoleDestroyer', ['roles.delete'])
        system_role = db.session.query(Role).filter_by(name='Teacher').one()
        destroyer = create_user('role-destroyer', 'destroyer@example.com', roles=[delete_role])
        destroyer_id = destroyer.id
        system_role_id = system_role.id

    login_as(client, destroyer_id)
    response = client.post(f'/roles/{system_role_id}/delete', json={})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['error'] == 'System roles cannot be deleted'

    with app.app_context():
        assert db.session.get(Role, system_role_id) is not None


def test_permission_assignment_works(client, app):
    with app.app_context():
        assigner_role = create_role('RoleAssigner', ['roles.assign_permissions', 'tickets.reply'])
        target_role = create_role('SupportTeam', ['tickets.view'])
        assigner = create_user('role-assigner', 'assigner@example.com', roles=[assigner_role])
        assigner_id = assigner.id
        target_role_id = target_role.id
        permission_id = db.session.query(Permission).filter_by(name='tickets.reply').one().id

    login_as(client, assigner_id)
    add_response = client.post(
        f'/roles/{target_role_id}/permissions',
        json={'action': 'add', 'permission_id': permission_id},
    )
    assert add_response.status_code == 200
    add_payload = add_response.get_json()
    assert 'tickets.reply' in [permission['name'] for permission in add_payload['assigned_permissions']]

    remove_response = client.post(
        f'/roles/{target_role_id}/permissions',
        json={'action': 'remove', 'permission_id': permission_id},
    )
    assert remove_response.status_code == 200
    remove_payload = remove_response.get_json()
    assert 'tickets.reply' not in [permission['name'] for permission in remove_payload['assigned_permissions']]

    with app.app_context():
        stored_role = db.session.get(Role, target_role_id)
        assert {permission.name for permission in stored_role.permissions} == {'tickets.view'}


def test_admin_cannot_accidentally_strip_own_admin_rights(client, app):
    with app.app_context():
        admin_role = db.session.query(Role).filter_by(name='Admin').one()
        admin_user = create_user(
            'admin-user',
            'admin@example.com',
            roles=[admin_role],
            role=RoleEnum.ADMIN,
        )
        admin_user_id = admin_user.id
        admin_role_id = admin_role.id
        protected_permission_id = db.session.query(Permission).filter_by(name='admin.view').one().id
        before_permission_names = {permission.name for permission in admin_role.permissions}

    login_as(client, admin_user_id)
    response = client.post(
        f'/roles/{admin_role_id}/permissions',
        json={'action': 'remove', 'permission_id': protected_permission_id},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['error'] == 'Admin role must retain all permissions'

    with app.app_context():
        stored_role = db.session.get(Role, admin_role_id)
        after_permission_names = {permission.name for permission in stored_role.permissions}
        assert after_permission_names == before_permission_names

