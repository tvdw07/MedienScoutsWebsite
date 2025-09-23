from app import create_app
from flask_migrate import upgrade
from app.models import db, User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    upgrade()
    print("Datenbank wurde erfolgreich eingerichtet und Migrationen angewendet.")

    # Admin-User anlegen, falls nicht vorhanden
    admin_user = User.query.filter_by(role='ADMIN').first()
    if not admin_user:
        passwordhash = generate_password_hash('admin')
        admin = User(
            username='admin',
            password_hash=passwordhash,
            first_name='Admin',
            last_name='User',
            role='ADMIN',
            email='admin@example.'
        )
        db.session.add(admin)
        db.session.commit()
        print('Admin-User mit Standard-Zugangsdaten wurde angelegt!')
    else:
        print('Admin-User existiert bereits.')
