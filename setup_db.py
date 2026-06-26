import os
import subprocess

from app import create_app
from app.models import db, TicketStatus, User
from flask_migrate import upgrade


os.environ['FLASK_APP'] = 'wsgi.py'

app = create_app()

with app.app_context():
    if not os.path.exists('migrations'):
        subprocess.run(['flask', 'db', 'init'], check=True)
        print('Migrations-Verzeichnis wurde erstellt.')

    upgrade()
    print('Vorhandene Migrationen wurden angewendet.')

    try:
        subprocess.run(['flask', 'db', 'migrate', '-m', 'Automatische Migration'], check=True)
        print('Neue Migration wurde erstellt.')
    except subprocess.CalledProcessError as e:
        print('Fehler beim Erstellen der Migration - moeglicherweise ist keine Aenderung vorhanden oder DB nicht aktuell.')
        print(e)

    upgrade()
    print('Datenbank ist aktuell.')

    status_values = {
        1: 'Offen',
        2: 'In Bearbeitung',
        3: 'Rueckmeldung gesendet',
        4: 'Geloest',
    }
    for status_id, status_name in status_values.items():
        status = db.session.get(TicketStatus, status_id)
        if status:
            status.status = status_name
        else:
            db.session.add(TicketStatus(id=status_id, status=status_name))
    db.session.commit()
    print('Ticket-Statuswerte sind angelegt.')

    admin_user = User.query.filter_by(role='ADMIN').first()
    if not admin_user:
        admin_password = os.environ.get('ADMIN_PASSWORD')
        if admin_password:
            admin = User(
                username=os.environ.get('ADMIN_USERNAME', 'admin'),
                first_name=os.environ.get('ADMIN_FIRST_NAME', 'Admin'),
                last_name=os.environ.get('ADMIN_LAST_NAME', 'User'),
                role='ADMIN',
                email=os.environ.get('ADMIN_EMAIL', 'admin@example.com')
            )
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            print('Initialer Admin-User wurde aus Umgebungsvariablen angelegt.')
        else:
            print('Kein Admin-User vorhanden. Setze ADMIN_PASSWORD in .env, um einen initialen Admin anzulegen.')
    else:
        print('Admin-User existiert bereits.')
