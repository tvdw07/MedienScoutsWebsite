from pathlib import Path

import pytest
from flask import Flask
from flask_login import LoginManager
from flask_wtf import CSRFProtect

from app.blueprints.bp_admin import bp_admin
from app.blueprints.bp_auth import bp_auth
from app.models import Permission, ProblemTicket, Role, RoleEnum, TicketStatus, User, UserPermissionOverride, db
from app.permission_seed import seed_permissions_and_roles
from app.blueprints.main import bp_main


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / 'permission_regression.db'
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


def create_user(username, email, *, password='secret123', role=RoleEnum.MEMBER, roles=None, active=True):
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
    db.session.flush()
    for assigned_role in roles or []:
        user.roles.append(assigned_role)
    db.session.commit()
    return user.id


def create_role(name, permission_names=None, *, is_system_role=False):
    role = Role(name=name, description=f'{name} role', is_system_role=is_system_role)
    db.session.add(role)
    db.session.flush()
    for permission_name in permission_names or []:
        permission = Permission.query.filter_by(name=permission_name).one()
        role.permissions.append(permission)
    db.session.commit()
    return role


def test_complete_login_flow(client, app):
    with app.app_context():
        user_role = db.session.query(Role).filter_by(name='User').one()
        user_id = create_user('login-user', 'login@example.com', role=RoleEnum.MEMBER, roles=[user_role])

    response = client.post(
        '/login',
        data={'username': 'login-user', 'password': 'secret123'},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/')

    with app.app_context():
        stored_user = db.session.get(User, user_id)
        assert stored_user is not None
        assert stored_user.last_login is not None

    profile_response = client.get('/profile')
    assert profile_response.status_code == 200
    assert b'Assigned roles' in profile_response.data


def test_user_management_regression(client, app):
    with app.app_context():
        admin_role = db.session.query(Role).filter_by(name='Admin').one()
        target_role = db.session.query(Role).filter_by(name='Teacher').one()
        assign_permission = Permission.query.filter_by(name='tickets.archive').one()
        admin_id = create_user('admin-user', 'admin@example.com', role=RoleEnum.ADMIN, roles=[admin_role])
        target_id = create_user('target-user', 'target@example.com')
        target_role_id = target_role.id
        assign_permission_id = assign_permission.id

    login_as(client, admin_id)

    list_response = client.get('/members/administration')
    assert list_response.status_code == 200

    detail_response = client.get(f'/members/user/{target_id}')
    assert detail_response.status_code == 200

    add_role_response = client.post(
        f'/members/user/{target_id}/roles',
        json={'action': 'add', 'role_id': target_role_id},
    )
    assert add_role_response.status_code == 200
    assert [role['name'] for role in add_role_response.get_json()['active_roles']] == ['Teacher']

    allow_response = client.post(
        f'/members/user/{target_id}/permissions',
        json={'action': 'allow', 'permission_id': assign_permission_id, 'reason': 'Temporary access'},
    )
    assert allow_response.status_code == 200
    assert allow_response.get_json()['permission_sources']['tickets.archive'] == ['role:Teacher', 'user_allow']


def test_user_cannot_grant_permission_to_self_without_having_it(client, app):
    with app.app_context():
        manager_role = create_role('SelfPermissionManager', ['users.manage_permissions'])
        self_user_id = create_user('self-permission-manager', 'self-permission@example.com', roles=[manager_role])
        permission_id = Permission.query.filter_by(name='tickets.reply').one().id

    login_as(client, self_user_id)
    response = client.post(
        f'/members/user/{self_user_id}/permissions',
        json={'action': 'allow', 'permission_id': permission_id, 'reason': 'Self test'},
    )

    assert response.status_code == 400
    assert response.get_json()['error'] == 'You can only grant permissions you already have.'

    with app.app_context():
        stored_user = db.session.get(User, self_user_id)
        assert stored_user is not None
        assert stored_user.permission_overrides == []


def test_user_cannot_grant_role_to_self_with_additional_permissions(client, app):
    with app.app_context():
        manager_role = create_role('SelfRoleManager', ['users.manage_roles'])
        elevated_role = create_role('ElevatedReplyRole', ['tickets.reply'])
        self_user_id = create_user('self-role-manager', 'self-role@example.com', roles=[manager_role])
        role_id = elevated_role.id

    login_as(client, self_user_id)
    response = client.post(
        f'/members/user/{self_user_id}/roles',
        json={'action': 'add', 'role_id': role_id},
    )

    assert response.status_code == 400
    assert response.get_json()['error'] == 'You can only assign roles whose permissions you already have.'

    with app.app_context():
        stored_user = db.session.get(User, self_user_id)
        assert stored_user is not None
        assert {role.name for role in stored_user.roles} == {'SelfRoleManager'}


def test_user_cannot_grant_permission_not_effectively_owned_to_other_user(client, app):
    with app.app_context():
        manager_role = create_role('OtherPermissionManager', ['users.manage_permissions'])
        actor_id = create_user('other-permission-manager', 'other-permission@example.com', roles=[manager_role])
        target_id = create_user('permission-target', 'permission-target@example.com')
        permission_id = Permission.query.filter_by(name='tickets.reply').one().id

    login_as(client, actor_id)
    response = client.post(
        f'/members/user/{target_id}/permissions',
        json={'action': 'allow', 'permission_id': permission_id, 'reason': 'Needs access'},
    )

    assert response.status_code == 400
    assert response.get_json()['error'] == 'You can only grant permissions you already have.'

    with app.app_context():
        stored_target = db.session.get(User, target_id)
        assert stored_target is not None
        assert stored_target.permission_overrides == []


def test_user_cannot_grant_role_not_effectively_owned_to_other_user(client, app):
    with app.app_context():
        manager_role = create_role('OtherRoleManager', ['users.manage_roles'])
        elevated_role = create_role('DelegatedReplyRole', ['tickets.reply'])
        actor_id = create_user('other-role-manager', 'other-role-manager@example.com', roles=[manager_role])
        target_id = create_user('role-target', 'role-target@example.com')
        role_id = elevated_role.id

    login_as(client, actor_id)
    response = client.post(
        f'/members/user/{target_id}/roles',
        json={'action': 'add', 'role_id': role_id},
    )

    assert response.status_code == 400
    assert response.get_json()['error'] == 'You can only assign roles whose permissions you already have.'

    with app.app_context():
        stored_target = db.session.get(User, target_id)
        assert stored_target is not None
        assert stored_target.roles == []


def test_user_with_matching_effective_permissions_can_grant_allowed_roles_and_permissions(client, app):
    with app.app_context():
        delegator_role = create_role(
            'Delegator',
            ['users.manage_roles', 'users.manage_permissions', 'tickets.reply'],
        )
        grantable_role = create_role('GrantableReplyRole', ['tickets.reply'])
        actor_id = create_user('delegator', 'delegator@example.com', roles=[delegator_role])
        target_id = create_user('grant-target', 'grant-target@example.com')
        permission_id = Permission.query.filter_by(name='tickets.reply').one().id
        role_id = grantable_role.id

    login_as(client, actor_id)
    permission_response = client.post(
        f'/members/user/{target_id}/permissions',
        json={'action': 'allow', 'permission_id': permission_id, 'reason': 'Delegated access'},
    )
    assert permission_response.status_code == 200

    role_response = client.post(
        f'/members/user/{target_id}/roles',
        json={'action': 'add', 'role_id': role_id},
    )
    assert role_response.status_code == 200

    with app.app_context():
        stored_target = db.session.get(User, target_id)
        assert stored_target is not None
        assert stored_target.has_permission('tickets.reply') is True
        assert {role.name for role in stored_target.roles} == {'GrantableReplyRole'}


def test_user_cannot_remove_own_last_management_role(client, app):
    with app.app_context():
        role_manager_role = create_role('OwnRoleManager', ['users.manage_roles'])
        role_manager_id = create_user('own-role-manager', 'own-role-manager@example.com', roles=[role_manager_role])
        role_id = role_manager_role.id

    login_as(client, role_manager_id)
    role_response = client.post(
        f'/members/user/{role_manager_id}/roles',
        json={'action': 'remove', 'role_id': role_id},
    )
    assert role_response.status_code == 400
    assert role_response.get_json()['error'] == 'You cannot remove your own admin access.'

    with app.app_context():
        stored_role_manager = db.session.get(User, role_manager_id)
        assert stored_role_manager is not None
        assert {role.name for role in stored_role_manager.roles} == {'OwnRoleManager'}

def test_user_cannot_remove_own_last_management_permission(client, app):
    with app.app_context():
        permission_manager_role = create_role('OwnPermissionManager', ['users.manage_permissions'])
        permission_manager_id = create_user(
            'own-permission-manager',
            'own-permission-manager@example.com',
            roles=[permission_manager_role],
        )
        permission_id = Permission.query.filter_by(name='users.manage_permissions').one().id

    login_as(client, permission_manager_id)
    permission_response = client.post(
        f'/members/user/{permission_manager_id}/permissions',
        json={'action': 'deny', 'permission_id': permission_id, 'reason': 'Self test'},
    )
    assert permission_response.status_code == 400
    assert permission_response.get_json()['error'] == 'You cannot remove your own admin access.'

    with app.app_context():
        stored_permission_manager = db.session.get(User, permission_manager_id)
        assert stored_permission_manager is not None
        assert stored_permission_manager.has_permission('users.manage_permissions') is True


def test_user_with_account_role_but_no_assigned_roles_does_not_grant_privileges(client, app):
    with app.app_context():
        account_admin_id = create_user('account-admin', 'account-admin@example.com', role=RoleEnum.ADMIN)

    login_as(client, account_admin_id)

    admin_panel_response = client.get('/admin/panel')
    members_response = client.get('/members/administration')

    assert admin_panel_response.status_code == 403
    assert members_response.status_code == 403

    with app.app_context():
        stored_user = db.session.get(User, account_admin_id)
        assert stored_user is not None
        assert stored_user.roles == []
        assert stored_user.has_permission('admin.view') is False
        assert stored_user.has_permission('admin.view_statistics') is False


def test_admin_cannot_remove_own_admin_role(client, app):
    with app.app_context():
        admin_role = db.session.query(Role).filter_by(name='Admin').one()
        admin_id = create_user('admin-self-role', 'admin-self-role@example.com', role=RoleEnum.ADMIN, roles=[admin_role])
        admin_role_id = admin_role.id

    login_as(client, admin_id)
    response = client.post(
        f'/members/user/{admin_id}/roles',
        json={'action': 'remove', 'role_id': admin_role_id},
    )

    assert response.status_code == 400
    assert response.get_json()['error'] == 'You cannot remove your own admin access.'

    with app.app_context():
        stored_user = db.session.get(User, admin_id)
        assert {role.name for role in stored_user.roles} == {'Admin'}


def test_admin_cannot_remove_own_last_admin_permission(client, app):
    with app.app_context():
        self_admin_role = create_role('SelfAdmin', ['users.manage_permissions', 'admin.view_statistics'])
        self_admin_id = create_user(
            'self-admin-user',
            'self-admin@example.com',
            roles=[self_admin_role],
        )
        permission_id = Permission.query.filter_by(name='admin.view_statistics').one().id

    login_as(client, self_admin_id)
    response = client.post(
        f'/members/user/{self_admin_id}/permissions',
        json={'action': 'deny', 'permission_id': permission_id, 'reason': 'Self test'},
    )

    assert response.status_code == 400
    assert response.get_json()['error'] == 'You cannot remove your own admin access.'

    with app.app_context():
        stored_user = db.session.get(User, self_admin_id)
        assert stored_user is not None
        assert stored_user.has_permission('admin.view_statistics') is True


def test_role_management_regression(client, app):
    with app.app_context():
        admin_role = db.session.query(Role).filter_by(name='Admin').one()
        permission = Permission.query.filter_by(name='tickets.reply').one()
        admin_id = create_user('admin-role-user', 'admin-role@example.com', role=RoleEnum.ADMIN, roles=[admin_role])
        permission_id = permission.id

    login_as(client, admin_id)

    list_response = client.get('/roles/administration')
    assert list_response.status_code == 200

    create_response = client.post(
        '/roles',
        json={'name': 'Supporters', 'description': 'Support team role'},
    )
    assert create_response.status_code == 201
    created_role = create_response.get_json()['role']
    created_role_id = created_role['id']

    assign_response = client.post(
        f'/roles/{created_role_id}/permissions',
        json={'action': 'add', 'permission_id': permission_id},
    )
    assert assign_response.status_code == 200
    assert [item['name'] for item in assign_response.get_json()['assigned_permissions']] == ['tickets.reply']

    edit_response = client.post(
        f'/roles/{created_role_id}/edit',
        json={'name': 'Support Crew', 'description': 'Updated role'},
    )
    assert edit_response.status_code == 200
    assert edit_response.get_json()['role']['name'] == 'Support Crew'

    delete_response = client.post(f'/roles/{created_role_id}/delete', json={})
    assert delete_response.status_code == 200


def test_admin_cannot_delete_role_that_removes_own_admin_access(client, app):
    with app.app_context():
        self_admin_role = create_role('SelfAdminDelete', ['roles.delete', 'admin.view_statistics'])
        self_admin_id = create_user(
            'self-admin-delete',
            'self-admin-delete@example.com',
            roles=[self_admin_role],
        )
        role_id = self_admin_role.id

    login_as(client, self_admin_id)
    response = client.post(f'/roles/{role_id}/delete', json={})

    assert response.status_code == 400
    assert response.get_json()['error'] == 'You cannot remove your own admin access.'

    with app.app_context():
        stored_role = db.session.get(Role, role_id)
        assert stored_role is not None


def test_ticket_access_regression(client, app):
    with app.app_context():
        mediascout_role = db.session.query(Role).filter_by(name='MediaScout').one()
        user_role = db.session.query(Role).filter_by(name='User').one()
        problem_ticket = ProblemTicket(
            first_name='Ada',
            last_name='Lovelace',
            email='ada@example.com',
            class_name='9A',
            problem_description='Notebook does not boot',
            steps_taken='Pressed power',
            status_id=1,
        )
        db.session.add(problem_ticket)
        db.session.commit()
        media_user_id = create_user('media-user', 'media@example.com', roles=[mediascout_role])
        plain_user_id = create_user('plain-user', 'plain@example.com', roles=[user_role])

    login_as(client, media_user_id)
    media_response = client.get('/ticketverwaltung')
    assert media_response.status_code == 200
    assert b'Ticketverwaltung' in media_response.data

    login_as(client, plain_user_id)
    plain_response = client.get('/archiv')
    assert plain_response.status_code == 403


def test_public_ticket_links_regression(client, app, monkeypatch):
    monkeypatch.setattr('app.blueprints.main.tickets.send_ticket_link', lambda ticket: None)

    create_response = client.post(
        '/send_ticket',
        data={
            'ticket_type': 'problem',
            'problem_first_name': 'Grace',
            'problem_last_name': 'Hopper',
            'problem_email': 'grace@example.com',
            'problem_class_name': '10A',
            'problem_description': 'Projector is broken',
            'problem_steps': 'Checked cables, Restarted',
        },
    )
    assert create_response.status_code == 302

    with app.app_context():
        ticket = ProblemTicket.query.one()
        token = ticket.generate_token()

    detail_response = client.get(f'/ticket/{token}')
    assert detail_response.status_code == 200
    assert b'Ticket Details' in detail_response.data


def test_permission_deny_override_regression(client, app):
    with app.app_context():
        admin_role = db.session.query(Role).filter_by(name='Admin').one()
        admin_id = create_user('deny-admin', 'deny-admin@example.com', role=RoleEnum.ADMIN, roles=[admin_role])
        profile_permission = Permission.query.filter_by(name='profile.view').one()
        user = db.session.get(User, admin_id)
        user.permission_overrides.append(
            UserPermissionOverride(permission=profile_permission, allowed=False, reason='Testing deny')
        )
        db.session.commit()

    login_as(client, admin_id)
    response = client.get('/profile')
    assert response.status_code == 403

