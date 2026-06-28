import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from app.models import User, db


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / 'password_hashing.db'
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


def test_set_password_uses_argon2_hash(app):
    with app.app_context():
        user = User(
            username='argon2-user',
            email='argon2-user@example.com',
            first_name='Test',
            last_name='User',
        )
        user.set_password('Secret123!')
        db.session.add(user)
        db.session.commit()

        assert user.password_hash.startswith('$argon2')
        assert user.check_password('Secret123!') is True
        assert user.check_password('wrong-password') is False


def test_old_password_hash_is_rejected(app):
    with app.app_context():
        user = User(
            username='old-user',
            email='old-user@example.com',
            first_name='Test',
            last_name='User',
        )
        old_hash = generate_password_hash('Secret123!')
        user.password_hash = old_hash
        db.session.add(user)
        db.session.commit()

        assert user.check_password('Secret123!') is False
        db.session.commit()

        stored_user = db.session.get(User, user.id)
        assert stored_user is not None
        assert stored_user.password_hash == old_hash
