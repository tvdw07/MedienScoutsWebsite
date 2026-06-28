import os
import sys

from app import create_app
from app.models import Role, RoleEnum, TicketStatus, User, db
from app.permission_seed import seed_permissions_and_roles


app = create_app()


def _seed_ticket_statuses():
    status_values = {
        1: 'Open',
        2: 'In Progress',
        3: 'Waiting',
        4: 'Solved',
    }

    for status_id, status_name in status_values.items():
        status = db.session.get(TicketStatus, status_id)
        if status is None:
            db.session.add(TicketStatus(id=status_id, status=status_name))
        else:
            status.status = status_name


def _bootstrap_admin_user():
    admin_password = os.environ.get('ADMIN_PASSWORD')
    if not admin_password:
        print('No ADMIN_PASSWORD configured. Skipping bootstrap admin user.')
        return

    username = os.environ.get('ADMIN_USERNAME', 'admin').strip()
    email = os.environ.get('ADMIN_EMAIL', 'admin@example.com').strip()
    first_name = os.environ.get('ADMIN_FIRST_NAME', 'Admin').strip()
    last_name = os.environ.get('ADMIN_LAST_NAME', 'User').strip()

    admin_role = Role.query.filter_by(name='Admin').one()
    admin_user = User.query.filter_by(username=username).one_or_none()
    if admin_user is None:
        admin_user = User(
            username=username,
            first_name=first_name,
            last_name=last_name,
            role=RoleEnum.ADMIN,
            email=email,
        )
        admin_user.set_password(admin_password)
        admin_user.roles.append(admin_role)
        db.session.add(admin_user)
    else:
        admin_user.first_name = first_name
        admin_user.last_name = last_name
        admin_user.email = email
        if admin_role not in admin_user.roles:
            admin_user.roles.append(admin_role)
        if not admin_user.password_hash:
            admin_user.set_password(admin_password)


with app.app_context():
    if '--reset' in sys.argv:
        db.drop_all()
    db.create_all()
    seed_permissions_and_roles()
    _seed_ticket_statuses()
    _bootstrap_admin_user()
    db.session.commit()
    print('Database initialized from the current schema.')
