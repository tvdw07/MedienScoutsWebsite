from pathlib import Path

from flask import Flask
from flask_login import LoginManager
from flask_wtf import CSRFProtect

from app.blueprints.bp_admin import bp_admin
from app.blueprints.bp_auth import bp_auth
from app.legal import build_legal_context
from app.models import User, db
from app.permission_seed import seed_permissions_and_roles
from app.blueprints.main import bp_main


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

    return app


def test_legal_context_separates_operator_and_software_credit():
    context = build_legal_context(
        {
            'LEGAL_OPERATOR_NAME': 'Beispielschule',
            'LEGAL_ORGANIZATION_NAME': 'Beispielschule Nord',
            'LEGAL_REPRESENTATIVE_NAME': 'Max Mustermann',
            'LEGAL_STREET': 'Musterweg',
            'LEGAL_HOUSE_NUMBER': '12',
            'LEGAL_POSTAL_CODE': '12345',
            'LEGAL_CITY': 'Musterstadt',
            'LEGAL_COUNTRY': 'Deutschland',
            'LEGAL_PHONE': '+49 123 456789',
            'LEGAL_EMAIL': 'info@example.org',
            'LEGAL_WEBSITE': 'example.org',
            'LEGAL_PRIVACY_CONTACT_NAME': 'Datenschutzstelle',
            'LEGAL_PRIVACY_CONTACT_EMAIL': 'privacy@example.org',
        },
    )

    assert context['imprint']['operator']['name'] == 'Beispielschule'
    assert context['privacy']['controller']['organization_name'] == 'Beispielschule Nord'
    assert context['privacy']['data_protection_contact']['name'] == 'Datenschutzstelle'
    assert context['software']['developer_name'] == 'Tim von der Weppen'
    assert context['software']['repository_url'].startswith('https://github.com/')


def test_legal_pages_render_configured_values(tmp_path):
    app = _create_test_app(tmp_path)

    with app.app_context():
        app.config.update(
            LEGAL_OPERATOR_NAME='Beispielschule',
            LEGAL_ORGANIZATION_NAME='Beispielschule Nord',
            LEGAL_REPRESENTATIVE_NAME='Max Mustermann',
            LEGAL_STREET='Musterweg',
            LEGAL_HOUSE_NUMBER='12',
            LEGAL_POSTAL_CODE='12345',
            LEGAL_CITY='Musterstadt',
            LEGAL_COUNTRY='Deutschland',
            LEGAL_PHONE='+49 123 456789',
            LEGAL_EMAIL='info@example.org',
            LEGAL_WEBSITE='example.org',
            LEGAL_VAT_ID='DE123456789',
            LEGAL_EDITORIAL_RESPONSIBLE_NAME='Redaktion Beispiel',
            LEGAL_EDITORIAL_RESPONSIBLE_EMAIL='redaktion@example.org',
            LEGAL_PRIVACY_CONTACT_NAME='Datenschutzstelle',
            LEGAL_PRIVACY_CONTACT_EMAIL='privacy@example.org',
            LEGAL_SUPPORT_EMAIL='support@example.org',
            LEGAL_GITHUB_REPOSITORY='https://github.com/example/medien-scouts',
            LEGAL_VERSION='2.1.0',
            LEGAL_BUILD_NUMBER='4711',
            LEGAL_LAWFUL_BASIS_TEXT='Rechtsgrundlage wird von der Betreiberkonfiguration vorgegeben.',
            LEGAL_STORAGE_DURATION_TEXT='Speicherdauer wird vom Betreiber je nach Installation festgelegt.',
        )

    client = app.test_client()

    impressum_response = client.get('/impressum')
    impressum_html = impressum_response.get_data(as_text=True)
    assert impressum_response.status_code == 200
    assert 'Beispielschule' in impressum_html
    assert 'Beispielschule Nord' in impressum_html
    assert 'Max Mustermann' in impressum_html
    assert 'Musterweg 12' in impressum_html
    assert '12345 Musterstadt' in impressum_html
    assert 'Deutschland' in impressum_html
    assert '+49 123 456789' in impressum_html
    assert 'info@example.org' in impressum_html
    assert 'example.org' in impressum_html
    assert 'DE123456789' in impressum_html
    assert 'Redaktion Beispiel' in impressum_html
    assert 'redaktion@example.org' in impressum_html
    assert 'support@example.org' in impressum_html
    assert '2.1.0' in impressum_html
    assert 'Build 4711' in impressum_html
    assert 'Tim von der Weppen' in impressum_html
    assert 'tim.vonderweppen@web.de' not in impressum_html
    assert 'Forum' not in impressum_html

    privacy_response = client.get('/privacy_policy')
    privacy_html = privacy_response.get_data(as_text=True)
    assert privacy_response.status_code == 200
    assert 'Beispielschule' in privacy_html
    assert 'Datenschutzkontakt' in privacy_html
    assert 'Datenschutzstelle' in privacy_html
    assert 'privacy@example.org' in privacy_html
    assert 'Rechtsgrundlage wird von der Betreiberkonfiguration vorgegeben.' in privacy_html
    assert 'Speicherdauer wird vom Betreiber je nach Installation festgelegt.' in privacy_html
    assert 'tim.vonderweppen@web.de' not in privacy_html
    assert 'Forum' not in privacy_html


def test_missing_optional_legal_values_do_not_break_pages(tmp_path):
    app = _create_test_app(tmp_path)

    with app.app_context():
        app.config.update(
            LEGAL_OPERATOR_NAME='Schule am Park',
            LEGAL_ORGANIZATION_NAME='Schule am Park e. V.',
            LEGAL_REPRESENTATIVE_NAME='Erika Beispiel',
            LEGAL_STREET='Parkweg',
            LEGAL_HOUSE_NUMBER='7',
            LEGAL_POSTAL_CODE='54321',
            LEGAL_CITY='Beispielort',
            LEGAL_COUNTRY='Deutschland',
            LEGAL_EMAIL='kontakt@example.org',
            LEGAL_PRIVACY_CONTACT_NAME='Datenschutz',
            LEGAL_PRIVACY_CONTACT_EMAIL='privacy@example.org',
        )

    client = app.test_client()

    impressum_response = client.get('/impressum')
    privacy_response = client.get('/privacy_policy')

    assert impressum_response.status_code == 200
    assert privacy_response.status_code == 200

    impressum_html = impressum_response.get_data(as_text=True)
    privacy_html = privacy_response.get_data(as_text=True)

    assert 'Umsatzsteuer-ID' not in impressum_html
    assert 'Verantwortlich für journalistisch-redaktionelle Inhalte' not in impressum_html
    assert 'Support-E-Mail' not in impressum_html
    assert 'Version' not in impressum_html
    assert 'Build ' not in impressum_html
    assert 'Tim von der Weppen' in impressum_html

