from pathlib import Path

from flask import Flask
from flask_login import LoginManager
from flask_wtf import CSRFProtect

from app.blueprints.bp_admin import bp_admin
from app.blueprints.bp_auth import bp_auth
from app.models import User, db
from app.permission_seed import seed_permissions_and_roles
from app.routes import bp_main


def _create_test_app(tmp_path):
    database_path = tmp_path / 'legal_pages.db'
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

    return app


def test_legal_pages_use_env_config_values(tmp_path):
    app = _create_test_app(tmp_path)

    with app.app_context():
        app.config.update(
            IMPRINT_RESPONSIBLE_NAME='Imprint Person',
            IMPRINT_RESPONSIBLE_EMAIL='imprint@example.com',
            PRIVACY_RESPONSIBLE_NAME='Privacy Person',
            PRIVACY_RESPONSIBLE_EMAIL='privacy@example.com',
            IMPRINT_DEVELOPMENT_TEXT='Development text from config',
        )

    client = app.test_client()

    impressum_response = client.get('/impressum')
    impressum_html = impressum_response.get_data(as_text=True)
    assert impressum_response.status_code == 200
    assert 'Imprint Person' in impressum_html
    assert 'imprint@example.com' in impressum_html
    assert 'Development text from config' in impressum_html

    privacy_response = client.get('/privacy_policy')
    privacy_html = privacy_response.get_data(as_text=True)
    assert privacy_response.status_code == 200
    assert 'Privacy Person' in privacy_html
    assert 'privacy@example.com' in privacy_html
