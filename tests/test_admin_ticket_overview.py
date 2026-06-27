from datetime import datetime

import pytest

from app.models import (
    MediaConsultingTicket,
    MiscTicket,
    ProblemTicket,
    ProblemTicketUser,
    Role,
    RoleEnum,
    TrainingTicket,
    User,
    db,
)
from tests.helpers import create_test_app, login_as


@pytest.fixture()
def app(tmp_path):
    return create_test_app(tmp_path, database_name='admin_ticket_overview.db')


@pytest.fixture()
def client(app):
    return app.test_client()


def create_admin_user():
    admin_role = Role.query.filter_by(name='Admin').one()
    user = User(
        username='admin-user',
        email='admin@example.com',
        first_name='Admin',
        last_name='User',
        role=RoleEnum.ADMIN,
        active=True,
    )
    db.session.add(user)
    db.session.flush()
    user.roles.append(admin_role)
    db.session.commit()
    return user.id


def create_worker_user():
    user = User(
        username='worker-user',
        email='worker@example.com',
        first_name='Worker',
        last_name='Bee',
        role=RoleEnum.MEMBER,
        active=True,
    )
    db.session.add(user)
    db.session.commit()
    return user.id


def test_admin_panel_exposes_ticket_overview_link(client, app):
    with app.app_context():
        admin_id = create_admin_user()

    login_as(client, admin_id)
    response = client.get('/admin/panel')

    assert response.status_code == 200
    assert b'href="/tickets/administration"' in response.data
    assert b'Tickets ansehen' in response.data


def test_admin_ticket_overview_lists_all_non_archived_tickets(client, app):
    with app.app_context():
        admin_id = create_admin_user()
        worker_id = create_worker_user()

        open_problem_ticket = ProblemTicket(
            first_name='Ada',
            last_name='Lovelace',
            email='ada@example.com',
            class_name='10A',
            problem_description='PC startet nicht',
            status_id=1,
        )
        in_progress_training_ticket = TrainingTicket(
            class_teacher='Prof. Turing',
            email='turing@example.com',
            training_type='Workshop',
            training_reason='Digitale Medien',
            proposed_date=datetime(2026, 6, 27, 12, 30),
            status_id=2,
        )
        waiting_misc_ticket = MiscTicket(
            first_name='Max',
            last_name='Mustermann',
            email='max@example.com',
            message='Wird angezeigt',
            status_id=3,
        )
        solved_misc_ticket = MiscTicket(
            first_name='Max',
            last_name='Mustermann',
            email='max@example.com',
            message='Wird nicht angezeigt',
            status_id=4,
        )
        open_media_ticket = MediaConsultingTicket(
            first_name='Marie',
            last_name='Curie',
            email='marie@example.com',
            class_name='9B',
            topic='Social Media',
            description='Workshop planen',
            status_id=1,
        )
        db.session.add_all(
            [
                open_problem_ticket,
                in_progress_training_ticket,
                waiting_misc_ticket,
                solved_misc_ticket,
                open_media_ticket,
            ]
        )
        db.session.commit()
        db.session.add(ProblemTicketUser(problem_ticket_id=open_problem_ticket.id, user_id=worker_id))
        db.session.commit()

    login_as(client, admin_id)
    response = client.get('/tickets/administration')

    assert response.status_code == 200
    assert b'Anzahl nicht archivierter Tickets: 4' in response.data
    assert b'PC startet nicht' in response.data
    assert b'Prof. Turing' in response.data
    assert b'Wird angezeigt' in response.data
    assert b'Social Media' in response.data
    assert b'Worker Bee' in response.data
    assert b'worker-user' in response.data
    assert b'Wird nicht angezeigt' not in response.data
    assert b'Solved' not in response.data
