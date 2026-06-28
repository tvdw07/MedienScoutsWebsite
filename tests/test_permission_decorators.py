import pytest
from flask import Flask
from flask_login import LoginManager

from app.decorators import admin_required, permission_required
from app.models import db, Permission, Role, RoleEnum, User, UserPermissionOverride


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / 'decorators.db'

    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{database_path.as_posix()}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY='test-secret-key',
        SECURITY_PASSWORD_SALT='test-security-salt',
        APP_BASE_URL='https://example.com',
        WTF_CSRF_ENABLED=False,
    )

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.session_protection = None
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.route('/login')
    def login():
        return 'login'

    @app.route('/protected')
    @permission_required('tickets.view')
    def protected():
        return 'protected'

    @app.route('/admin-only')
    @admin_required
    def admin_only():
        return 'admin'

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login_as(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True


def create_user(username, email, *, active=True, role=RoleEnum.MEMBER):
    user = User(
        username=username,
        email=email,
        first_name='Test',
        last_name='User',
        role=role,
        active=active,
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_anonymous_access_is_redirected_to_login(client):
    response = client.get('/protected')

    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_user_without_permission_gets_403(client):
    user = create_user('no-permission', 'no-permission@example.com')
    login_as(client, user)

    response = client.get('/protected')

    assert response.status_code == 403


def test_user_with_permission_is_allowed(client):
    user = create_user('allowed-user', 'allowed-user@example.com')
    permission = Permission(name='tickets.view', description='View tickets')
    user.permission_overrides.append(UserPermissionOverride(permission=permission, allowed=True))
    db.session.add(permission)
    db.session.commit()

    login_as(client, user)
    response = client.get('/protected')

    assert response.status_code == 200
    assert response.data == b'protected'


def test_admin_with_role_is_allowed(client):
    admin_permission = Permission(name='admin.view', description='View admin area')
    admin_role = Role(name='Admin', description='Admin role', is_system_role=True)
    admin_role.permissions.append(admin_permission)
    user = create_user('admin-user', 'admin-user@example.com')
    user.roles.append(admin_role)
    db.session.add_all([admin_permission, admin_role])
    db.session.commit()

    login_as(client, user)
    response = client.get('/admin-only')

    assert response.status_code == 200
    assert response.data == b'admin'


def test_deny_override_blocks_admin_role(client):
    admin_permission = Permission(name='admin.view', description='View admin area')
    admin_role = Role(name='Admin', description='Admin role', is_system_role=True)
    admin_role.permissions.append(admin_permission)
    user = create_user('denied-admin', 'denied-admin@example.com')
    user.roles.append(admin_role)
    user.permission_overrides.append(
        UserPermissionOverride(permission=admin_permission, allowed=False, reason='Restricted')
    )
    db.session.add_all([admin_permission, admin_role])
    db.session.commit()

    login_as(client, user)
    response = client.get('/admin-only')

    assert response.status_code == 403
