import os
import subprocess
from app import create_app
from flask_migrate import upgrade
from app.models import db, User
from werkzeug.security import generate_password_hash

# Setze FLASK_APP für subprocess-Aufrufe
os.environ['FLASK_APP'] = 'wsgi.py'  # oder dein passender Entry-Point

app = create_app()

with app.app_context():
    # Migrationsverzeichnis anlegen, falls nicht vorhanden
    if not os.path.exists('migrations'):
        subprocess.run(['flask', 'db', 'init'], check=True)
        print("Migrations-Verzeichnis wurde erstellt.")

    # Schritt 1: Bestehende Migrationen anwenden
    upgrade()
    print("Vorhandene Migrationen wurden angewendet.")

    # Schritt 2: Neue Migration erzeugen (falls nötig)
    try:
        subprocess.run(['flask', 'db', 'migrate', '-m', 'Automatische Migration'], check=True)
        print("Neue Migration wurde erstellt.")
    except subprocess.CalledProcessError as e:
        print("❌ Fehler beim Erstellen der Migration – möglicherweise ist keine Änderung vorhanden oder DB nicht aktuell.")
        print(e)

    # Schritt 3: Migration anwenden (sicherstellen, dass alles aktuell ist)
    upgrade()
    print("Datenbank ist aktuell.")

    # Schritt 4: Admin-User anlegen, falls nicht vorhanden
    admin_user = User.query.filter_by(role='ADMIN').first()
    if not admin_user:
        passwordhash = generate_password_hash('admin')
        admin = User(
            username='admin',
            password_hash=passwordhash,
            first_name='Admin',
            last_name='User',
            role='ADMIN',
            email='admin@example.com'
        )
        db.session.add(admin)
        db.session.commit()
        print('✅ Admin-User mit Standard-Zugangsdaten wurde angelegt!')
    else:
        print('ℹ️ Admin-User existiert bereits.')
