import os
from datetime import datetime, timedelta

import pytest
from PIL import Image

from app.maintenance import run_maintenance_cleanup
from app.models import MediaConsultingTicket, MiscTicket, ProblemTicket, TicketHistory, TrainingTicket, User, db
from tests.helpers import create_test_app


@pytest.fixture()
def app(tmp_path):
    app = create_test_app(tmp_path, csrf_enabled=False, database_name='maintenance_regression.db')
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def _write_test_image(path, format='PNG'):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (1, 1), (255, 0, 0)).save(path, format=format)


@pytest.mark.parametrize(
    'model_cls',
    [ProblemTicket, TrainingTicket, MiscTicket, MediaConsultingTicket, TicketHistory],
)
def test_created_at_defaults_are_callable(model_cls):
    default = model_cls.__table__.c.created_at.default

    assert default is not None
    assert not default.is_scalar
    assert callable(default.arg)


def test_cleanup_uses_profile_picture_timestamp_over_file_mtime(app, tmp_path):
    now = datetime(2026, 6, 28, 12, 0, 0)
    profile_filename = 'legacy-profile.png'
    upload_dir = tmp_path / 'instance' / 'uploads' / 'profile_pictures'
    upload_path = upload_dir / profile_filename
    old_timestamp = now - timedelta(days=200)
    recent_timestamp = now - timedelta(days=1)

    with app.app_context():
        user = User(
            username='profile-cleanup',
            email='profile-cleanup@example.com',
            first_name='Profile',
            last_name='Cleanup',
            active=True,
            profile_picture=profile_filename,
            profile_picture_original_name='legacy-profile.png',
            profile_picture_uploaded_at=old_timestamp,
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _write_test_image(upload_path, 'PNG')
    os.utime(upload_path, (recent_timestamp.timestamp(), recent_timestamp.timestamp()))

    log_file = tmp_path / 'logs' / 'app.log'
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text('active log\n', encoding='utf-8')

    run_maintenance_cleanup(app, now=now, log_file_path=str(log_file))

    with app.app_context():
        stored_user = db.session.get(User, user_id)
        assert stored_user.profile_picture is None
        assert stored_user.profile_picture_original_name is None
        assert stored_user.profile_picture_uploaded_at is None

    assert not upload_path.exists()


def test_cleanup_uses_created_at_over_file_mtime_for_problem_ticket_attachments(app, tmp_path):
    now = datetime(2026, 6, 28, 12, 0, 0)
    attachment_filename = 'legacy-ticket.jpg'
    upload_dir = tmp_path / 'instance' / 'uploads' / 'tickets'
    upload_path = upload_dir / attachment_filename
    old_created_at = now - timedelta(days=5 * 365 + 1)
    recent_timestamp = now - timedelta(days=1)

    with app.app_context():
        ticket = ProblemTicket(
            first_name='Ada',
            last_name='Lovelace',
            email='ada@example.com',
            class_name='9A',
            problem_description='Broken device',
            steps_taken='restarted',
            photo=attachment_filename,
            photo_original_name='legacy-ticket.jpg',
            created_at=old_created_at,
            status_id=1,
        )
        db.session.add(ticket)
        db.session.commit()
        ticket_id = ticket.id

    _write_test_image(upload_path, 'JPEG')
    os.utime(upload_path, (recent_timestamp.timestamp(), recent_timestamp.timestamp()))

    log_file = tmp_path / 'logs' / 'app.log'
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text('active log\n', encoding='utf-8')

    run_maintenance_cleanup(app, now=now, log_file_path=str(log_file))

    with app.app_context():
        assert db.session.get(ProblemTicket, ticket_id) is None

    assert not upload_path.exists()


def test_cleanup_deletes_rotated_log_backups_without_touching_active_log(app, tmp_path):
    now = datetime(2026, 6, 28, 12, 0, 0)
    log_dir = tmp_path / 'logs'
    active_log = log_dir / 'app.log'
    old_backup = log_dir / 'app.log.1'
    recent_backup = log_dir / 'app.log.2'

    log_dir.mkdir(parents=True, exist_ok=True)
    active_log.write_text('active-log\n', encoding='utf-8')
    old_backup.write_text('old-backup\n', encoding='utf-8')
    recent_backup.write_text('recent-backup\n', encoding='utf-8')

    old_backup_time = now - timedelta(days=8)
    recent_backup_time = now - timedelta(days=1)
    os.utime(old_backup, (old_backup_time.timestamp(), old_backup_time.timestamp()))
    os.utime(recent_backup, (recent_backup_time.timestamp(), recent_backup_time.timestamp()))

    original_active_log = active_log.read_text(encoding='utf-8')

    run_maintenance_cleanup(app, now=now, log_file_path=str(active_log))

    assert active_log.read_text(encoding='utf-8') == original_active_log
    assert not old_backup.exists()
    assert recent_backup.exists()
