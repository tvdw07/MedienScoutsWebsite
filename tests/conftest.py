import pytest
from flask import Flask

from app.models import db


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / 'test.db'

    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{database_path.as_posix()}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY='test-secret-key',
        SECURITY_PASSWORD_SALT='test-security-salt',
        APP_BASE_URL='https://example.com',
    )

    db.init_app(app)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
