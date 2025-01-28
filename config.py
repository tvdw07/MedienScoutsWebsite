# config.py
import os.path
from datetime import timedelta

MYSQL_HOST = 'DB_HOST'
MYSQL_USER = 'DB_USER'
MYSQL_PASSWORD = 'DB_PASSWORD'
MYSQL_DB = 'DB_NAME'
SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# config.py
PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)  # Set session timeout to 30 minutes
WTF_CSRF_ENABLED = True  # Enable CSRF protection
UPLOAD_FOLDER = os.path.join('static/uploads')  # Folder for file uploads
USER_PROFILES = os.path.join('static/uploads/profiles')  # Folder for user profile photos

# Secret key for generating tokens
SECRET_KEY = 'YOUR_SECRET_KEY'
SECURITY_PASSWORD_SALT = 'YOUR_PASSWORD_SALT'

PASSWORD_POLICY = {
    'min_length': 8,
    'require_uppercase': True,
    'require_lowercase': True,
    'require_digit': True,
    'require_special': True
}

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = 'Strict'
