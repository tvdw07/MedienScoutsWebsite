# config.py
import os
import os.path
from datetime import timedelta


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
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join('static/uploads'))
USER_PROFILES = os.environ.get('USER_PROFILES', os.path.join('static/uploads/profiles'))

SECRET_KEY = _required_env('SECRET_KEY')
SECURITY_PASSWORD_SALT = _required_env('SECURITY_PASSWORD_SALT')
TICKET_TOKEN_MAX_AGE_SECONDS = int(os.environ.get('TICKET_TOKEN_MAX_AGE_SECONDS', 30 * 24 * 60 * 60))

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
