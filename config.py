# config.py
import os
import os.path
from datetime import timedelta

from url_utils import normalize_base_url


def _load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return value


def _env_bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_text(*names, default=''):
    for name in names:
        value = os.environ.get(name)
        if value is None:
            continue
        value = value.strip()
        if value:
            return value
    return default


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
_load_env_file(os.path.join(BASE_DIR, '.env'))
APP_ENV = os.environ.get('APP_ENV', os.environ.get('FLASK_ENV', 'development')).lower()
IS_PRODUCTION = APP_ENV == 'production'


def _default_database_uri():
    database_url = os.environ.get('SQLALCHEMY_DATABASE_URI') or os.environ.get('DATABASE_URL')
    if database_url:
        if database_url.startswith('postgres://'):
            return database_url.replace('postgres://', 'postgresql+psycopg2://', 1)
        return database_url

    postgres_user = os.environ.get('POSTGRES_USER', 'medienscouts')
    postgres_password = os.environ.get('POSTGRES_PASSWORD', 'medienscouts')
    postgres_host = os.environ.get('POSTGRES_HOST', 'localhost')
    postgres_port = os.environ.get('POSTGRES_PORT', '5432')
    postgres_db = os.environ.get('POSTGRES_DB', 'medienscouts')
    return (
        f'postgresql+psycopg2://{postgres_user}:{postgres_password}'
        f'@{postgres_host}:{postgres_port}/{postgres_db}'
    )


SQLALCHEMY_DATABASE_URI = _default_database_uri()
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_pre_ping': True,
}

RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'redis://localhost:6379/1')

PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
WTF_CSRF_ENABLED = True
UPLOAD_ROOT = os.environ.get('UPLOAD_ROOT', 'uploads')
PROFILE_PICTURE_FOLDER = os.environ.get('PROFILE_PICTURE_FOLDER', 'profile_pictures')
TICKET_ATTACHMENT_FOLDER = os.environ.get('TICKET_ATTACHMENT_FOLDER', 'tickets')
MAX_PROFILE_IMAGE_SIZE = int(os.environ.get('MAX_PROFILE_IMAGE_SIZE', 2 * 1024 * 1024))
MAX_TICKET_ATTACHMENT_SIZE = int(os.environ.get('MAX_TICKET_ATTACHMENT_SIZE', 5 * 1024 * 1024))
MAX_CONTENT_LENGTH = int(
    os.environ.get(
        'MAX_CONTENT_LENGTH',
        max(MAX_PROFILE_IMAGE_SIZE, MAX_TICKET_ATTACHMENT_SIZE) + 1024 * 1024,
    )
)

SECRET_KEY = _required_env('SECRET_KEY')
SECURITY_PASSWORD_SALT = _required_env('SECURITY_PASSWORD_SALT')
TICKET_TOKEN_MAX_AGE_SECONDS = int(os.environ.get('TICKET_TOKEN_MAX_AGE_SECONDS', 30 * 24 * 60 * 60))
APP_BASE_URL = normalize_base_url(_required_env('APP_BASE_URL'))

PASSWORD_POLICY = {
    'min_length': 8,
    'require_uppercase': True,
    'require_lowercase': True,
    'require_digit': True,
    'require_special': True
}

FORCE_HTTPS = _env_bool('FORCE_HTTPS', IS_PRODUCTION)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = _env_bool('SESSION_COOKIE_SECURE', IS_PRODUCTION)
SESSION_COOKIE_SAMESITE = 'Strict'

LEGAL_OPERATOR_NAME = _env_text('LEGAL_OPERATOR_NAME')
LEGAL_ORGANIZATION_NAME = _env_text('LEGAL_ORGANIZATION_NAME')
LEGAL_REPRESENTATIVE_NAME = _env_text('LEGAL_REPRESENTATIVE_NAME')
LEGAL_STREET = _env_text('LEGAL_STREET')
LEGAL_HOUSE_NUMBER = _env_text('LEGAL_HOUSE_NUMBER')
LEGAL_POSTAL_CODE = _env_text('LEGAL_POSTAL_CODE')
LEGAL_CITY = _env_text('LEGAL_CITY')
LEGAL_COUNTRY = _env_text('LEGAL_COUNTRY')
LEGAL_PHONE = _env_text('LEGAL_PHONE')
LEGAL_EMAIL = _env_text('LEGAL_EMAIL')
LEGAL_WEBSITE = _env_text('LEGAL_WEBSITE')
LEGAL_VAT_ID = _env_text('LEGAL_VAT_ID')
LEGAL_EDITORIAL_RESPONSIBLE_NAME = _env_text('LEGAL_EDITORIAL_RESPONSIBLE_NAME')
LEGAL_EDITORIAL_RESPONSIBLE_EMAIL = _env_text('LEGAL_EDITORIAL_RESPONSIBLE_EMAIL')
LEGAL_PRIVACY_CONTACT_NAME = _env_text('LEGAL_PRIVACY_CONTACT_NAME')
LEGAL_PRIVACY_CONTACT_EMAIL = _env_text('LEGAL_PRIVACY_CONTACT_EMAIL')
LEGAL_SUPPORT_EMAIL = _env_text('LEGAL_SUPPORT_EMAIL')
LEGAL_GITHUB_REPOSITORY = _env_text('LEGAL_GITHUB_REPOSITORY', default='https://github.com/tvdw07/MedienScoutsWebsite')
LEGAL_VERSION = _env_text('LEGAL_VERSION')
LEGAL_BUILD_NUMBER = _env_text('LEGAL_BUILD_NUMBER')
LEGAL_LAWFUL_BASIS_TEXT = _env_text(
    'LEGAL_LAWFUL_BASIS_TEXT',
    default='Soweit keine speziellere Rechtsgrundlage genannt wird, erfolgt die Verarbeitung auf Grundlage von Art. 6 Abs. 1 lit. b, c und f DSGVO.',
)
LEGAL_STORAGE_DURATION_TEXT = _env_text(
    'LEGAL_STORAGE_DURATION_TEXT',
    default='Personenbezogene Daten werden nur so lange gespeichert, wie es für den jeweiligen Zweck erforderlich ist oder gesetzliche Aufbewahrungspflichten bestehen.',
)
