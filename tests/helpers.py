import re
from pathlib import Path

from flask import Flask
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from sqlalchemy import inspect

from app.blueprints.bp_admin import bp_admin
from app.blueprints.bp_auth import bp_auth
from app.models import TicketStatus, User, db
from app.permission_seed import seed_permissions_and_roles
from app.blueprints.main import bp_main


DEFAULT_PASSWORD_POLICY = {
    'min_length': 8,
    'require_uppercase': True,
    'require_lowercase': True,
    'require_digit': True,
    'require_special': True,
}


def create_test_app(tmp_path, *, csrf_enabled=False, database_name='regression.db'):
    database_path = tmp_path / database_name
    templates_path = Path(__file__).resolve().parents[1] / 'app' / 'templates'

    app = Flask(__name__, template_folder=str(templates_path))
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{database_path.as_posix()}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY='test-secret-key',
        SECURITY_PASSWORD_SALT='test-security-salt',
        APP_BASE_URL='https://example.com',
        WTF_CSRF_ENABLED=csrf_enabled,
        TICKET_TOKEN_MAX_AGE_SECONDS=3600,
        MAX_CONTENT_LENGTH=6 * 1024 * 1024,
        MAX_PROFILE_IMAGE_SIZE=2 * 1024 * 1024,
        MAX_TICKET_ATTACHMENT_SIZE=5 * 1024 * 1024,
        UPLOAD_ROOT=str(tmp_path / 'instance' / 'uploads'),
        PROFILE_PICTURE_FOLDER='profile_pictures',
        TICKET_ATTACHMENT_FOLDER='tickets',
        PASSWORD_POLICY=DEFAULT_PASSWORD_POLICY.copy(),
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

    return app


def login_as(client, user):
    if isinstance(user, int):
        user_id = user
    else:
        state = inspect(user)
        user_id = state.identity[0] if state.identity else user.id
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True


def extract_csrf_token(html):
    if isinstance(html, bytes):
        html = html.decode('utf-8')

    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    if not match:
        match = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', html)
    if not match:
        raise AssertionError('CSRF token not found in response HTML.')

    return match.group(1)

