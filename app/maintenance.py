from __future__ import annotations

import atexit
import os
from datetime import datetime, timedelta
from pathlib import Path

import portalocker
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select, update

from .models import (
    MediaConsultingTicket,
    MediaConsultingTicketUser,
    MiscTicket,
    MiscTicketUser,
    ProblemTicket,
    ProblemTicketUser,
    TicketHistory,
    TrainingTicket,
    TrainingTicketUser,
    User,
    db,
)
from .upload_utils import PROFILE_PICTURE_FOLDER, TICKET_ATTACHMENT_FOLDER, get_upload_folder, normalize_stored_filename

TICKET_RETENTION_DAYS = 5 * 365
UPLOAD_RETENTION_DAYS = 0.5 * 365
LOG_RETENTION_DAYS = 7
SCHEDULER_LOCK_FILENAME = 'maintenance.lock'


def _delete_files(upload_folder, filenames, logger):
    deleted = 0
    for filename in {normalize_stored_filename(name) for name in filenames if name}:
        if not filename:
            continue
        file_path = os.path.join(upload_folder, filename)
        if not os.path.exists(file_path):
            continue
        try:
            os.remove(file_path)
            deleted += 1
            logger.info('Deleted old upload: %s', filename)
        except OSError as exc:
            logger.warning('Failed to delete upload %s: %s', file_path, exc)
    return deleted


def _cleanup_profile_pictures(upload_threshold, logger):
    upload_folder = get_upload_folder(PROFILE_PICTURE_FOLDER)
    rows = db.session.execute(
        select(User.id, User.profile_picture, User.profile_picture_uploaded_at).where(User.profile_picture.isnot(None))
    ).all()

    user_ids = []
    filenames = []

    for row in rows:
        stored_filename = normalize_stored_filename(row.profile_picture)
        if not stored_filename:
            continue

        is_expired = False
        if row.profile_picture_uploaded_at is not None:
            is_expired = row.profile_picture_uploaded_at < upload_threshold
        else:
            file_path = os.path.join(upload_folder, stored_filename)
            if os.path.exists(file_path):
                is_expired = datetime.fromtimestamp(os.path.getmtime(file_path)) < upload_threshold

        if is_expired:
            user_ids.append(row.id)
            filenames.append(stored_filename)

    if user_ids:
        db.session.execute(
            update(User)
            .where(User.id.in_(user_ids))
            .values(
                profile_picture=None,
                profile_picture_original_name=None,
                profile_picture_uploaded_at=None,
            )
        )

    return upload_folder, filenames


def _cleanup_problem_ticket_attachments(upload_threshold, logger):
    upload_folder = get_upload_folder(TICKET_ATTACHMENT_FOLDER)
    rows = db.session.execute(
        select(ProblemTicket.id, ProblemTicket.photo, ProblemTicket.photo_original_name)
        .where(ProblemTicket.created_at < upload_threshold)
        .where(ProblemTicket.photo.isnot(None))
    ).all()

    ticket_ids = []
    filenames = []

    for row in rows:
        stored_filename = normalize_stored_filename(row.photo)
        ticket_ids.append(row.id)
        if stored_filename:
            filenames.append(stored_filename)

    if ticket_ids:
        db.session.execute(
            update(ProblemTicket)
            .where(ProblemTicket.id.in_(ticket_ids))
            .values(photo=None, photo_original_name=None)
        )

    return upload_folder, filenames


def _cleanup_expired_ticket_rows(ticket_threshold):
    cleanup_config = [
        ('problem', ProblemTicket, ProblemTicketUser, 'problem_ticket_id'),
        ('training', TrainingTicket, TrainingTicketUser, 'training_ticket_id'),
        ('misc', MiscTicket, MiscTicketUser, 'misc_ticket_id'),
        ('medienberatung', MediaConsultingTicket, MediaConsultingTicketUser, 'media_consulting_ticket_id'),
    ]

    deleted_ticket_count = 0
    for ticket_type, ticket_model, association_model, association_field_name in cleanup_config:
        ticket_ids = db.session.scalars(
            select(ticket_model.id).where(ticket_model.created_at < ticket_threshold)
        ).all()
        if not ticket_ids:
            continue

        association_field = getattr(association_model, association_field_name)
        association_model.query.filter(association_field.in_(ticket_ids)).delete(synchronize_session=False)
        TicketHistory.query.filter(
            TicketHistory.ticket_type == ticket_type,
            TicketHistory.ticket_id.in_(ticket_ids),
        ).delete(synchronize_session=False)
        ticket_model.query.filter(ticket_model.id.in_(ticket_ids)).delete(synchronize_session=False)
        deleted_ticket_count += len(ticket_ids)

    return deleted_ticket_count


def _cleanup_rotated_log_backups(log_file_path, log_threshold, logger):
    log_path = Path(log_file_path)
    if not log_path.exists():
        return 0

    deleted = 0
    for candidate in log_path.parent.glob(f'{log_path.name}.*'):
        if candidate.name == log_path.name or not candidate.is_file():
            continue
        try:
            if datetime.fromtimestamp(candidate.stat().st_mtime) >= log_threshold:
                continue
            candidate.unlink()
            deleted += 1
            logger.info('Deleted old log backup: %s', candidate.name)
        except OSError as exc:
            logger.warning('Failed to delete log backup %s: %s', candidate, exc)
    return deleted


def run_maintenance_cleanup(app, now=None, *, log_file_path='logs/app.log'):
    now = now or datetime.now()

    with app.app_context():
        ticket_threshold = now - timedelta(days=TICKET_RETENTION_DAYS)
        upload_threshold = now - timedelta(days=UPLOAD_RETENTION_DAYS)
        log_threshold = now - timedelta(days=LOG_RETENTION_DAYS)

        deleted_upload_files = []
        deleted_ticket_upload_files = []
        db_changed = False

        upload_folder, profile_picture_files = _cleanup_profile_pictures(upload_threshold, app.logger)
        if profile_picture_files:
            db_changed = True
            deleted_upload_files.append((upload_folder, profile_picture_files))

        upload_folder, problem_ticket_files = _cleanup_problem_ticket_attachments(upload_threshold, app.logger)
        if problem_ticket_files:
            db_changed = True
            deleted_ticket_upload_files.append((upload_folder, problem_ticket_files))

        deleted_ticket_rows = _cleanup_expired_ticket_rows(ticket_threshold)
        if deleted_ticket_rows:
            db_changed = True

        if db_changed:
            db.session.commit()

        deleted_files = 0
        for upload_folder, filenames in deleted_upload_files + deleted_ticket_upload_files:
            deleted_files += _delete_files(upload_folder, filenames, app.logger)

        deleted_log_backups = _cleanup_rotated_log_backups(log_file_path, log_threshold, app.logger)

        if deleted_ticket_rows:
            app.logger.info('Deleted %s old tickets', deleted_ticket_rows)
        if deleted_files:
            app.logger.info('Deleted %s old uploads', deleted_files)
        if deleted_log_backups:
            app.logger.info('Deleted %s old log backups', deleted_log_backups)

        return {
            'old_tickets_deleted': deleted_ticket_rows,
            'uploads_deleted': deleted_files,
            'log_backups_deleted': deleted_log_backups,
        }


def _shutdown_maintenance_scheduler(app):
    scheduler = app.extensions.pop('maintenance_scheduler', None)
    scheduler_lock = app.extensions.pop('maintenance_scheduler_lock', None)

    if scheduler:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass

    if scheduler_lock:
        try:
            scheduler_lock.release()
        except Exception:
            try:
                scheduler_lock.close()
            except Exception:
                pass


def start_maintenance_scheduler(app):
    if app.extensions.get('maintenance_scheduler'):
        return app.extensions['maintenance_scheduler']

    lock_folder = Path(app.instance_path)
    lock_folder.mkdir(parents=True, exist_ok=True)
    lock_path = lock_folder / SCHEDULER_LOCK_FILENAME

    scheduler_lock = portalocker.Lock(str(lock_path), mode='a', timeout=0)
    try:
        scheduler_lock.acquire()
    except portalocker.exceptions.LockException:
        app.logger.info('Maintenance scheduler already running in another process')
        return None

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=run_maintenance_cleanup,
        args=[app],
        trigger='interval',
        days=1,
        id='maintenance_cleanup',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()

    app.extensions['maintenance_scheduler'] = scheduler
    app.extensions['maintenance_scheduler_lock'] = scheduler_lock
    atexit.register(lambda: _shutdown_maintenance_scheduler(app))
    return scheduler
