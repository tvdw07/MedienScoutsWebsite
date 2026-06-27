from datetime import datetime
import os

from flask import current_app, flash, request
from werkzeug.datastructures import CombinedMultiDict, MultiDict
from werkzeug.utils import secure_filename

from app.models import TicketHistory, db


def _first_non_blank(*values):
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return value
        elif value:
            return value
    return None


def parse_optional_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def allowed_file(filename):
    allowed_extensions = {'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def save_ticket_photo(photo, first_name, last_name):
    """Save a ticket photo in the configured upload folder."""
    upload_folder = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'])
    try:
        os.makedirs(upload_folder, exist_ok=True)
    except OSError as exc:
        current_app.logger.error(f'Could not create upload folder {upload_folder}: {exc}')
        flash('Server-Fehler: Upload-Verzeichnis konnte nicht erstellt werden.', 'danger')
        return None

    if photo:
        photo.seek(0, os.SEEK_END)
        file_size = photo.tell()
        photo.seek(0)
        if file_size > 1 * 1024 * 1024:
            flash('File size exceeds the limit of 1MB.', 'danger')
            return None

        original_filename = secure_filename(photo.filename)
        if not allowed_file(original_filename):
            flash('Invalid file type.', 'danger')
            return None

        try:
            date_str = datetime.now().strftime('%d-%m-%Y')
            safe_first_name = secure_filename(first_name)
            safe_last_name = secure_filename(last_name)
            new_filename = f'{date_str}_{safe_first_name}_{safe_last_name}{os.path.splitext(original_filename)[1]}'
            file_path = os.path.join(upload_folder, new_filename)
            photo.save(file_path)
            rel_path = os.path.relpath(file_path, current_app.root_path)
            return rel_path.replace('\\', '/')
        except Exception as exc:
            current_app.logger.error(f'Error while saving ticket photo: {exc}')
            flash('Fehler beim Speichern des Fotos.', 'danger')
            return None
    return None


def log_ticket_message(ticket_type, ticket_id, message, author_type):
    history_entry = TicketHistory(
        ticket_type=ticket_type,
        ticket_id=ticket_id,
        message=message,
        author_type=author_type,
    )
    db.session.add(history_entry)
    db.session.commit()


def build_send_ticket_formdata():
    data = MultiDict(request.form)
    ticket_type = request.form.get('ticket_type')

    legacy_mappings = {
        'problem': {
            'problem_first_name': ('problem_first_name', 'first_name'),
            'problem_last_name': ('problem_last_name', 'last_name'),
            'problem_email': ('problem_email', 'email_problem'),
            'problem_class_name': ('problem_class_name', 'class'),
            'problem_serial_number': ('problem_serial_number', 'serial_number'),
            'problem_description': ('problem_description',),
            'problem_steps': ('problem_steps',),
        },
        'fortbildung': {
            'training_class_teacher': ('training_class_teacher', 'class_teacher'),
            'training_email': ('training_email', 'email_fortbildung'),
            'training_type': ('training_type',),
            'training_reason': ('training_reason',),
            'training_proposed_date': ('training_proposed_date', 'proposed_date'),
        },
        'medienberatung': {
            'media_first_name': ('media_first_name', 'first_name'),
            'media_last_name': ('media_last_name', 'last_name'),
            'media_email': ('media_email', 'email'),
            'media_class_name': ('media_class_name', 'class_name'),
            'media_topic': ('media_topic', 'topic'),
            'media_description': ('media_description', 'description'),
            'media_proposed_date': ('media_proposed_date', 'proposed_date', 'proposed_date_medienberatung'),
        },
        'sonstiges': {
            'misc_first_name': ('misc_first_name', 'first_name_sonstiges'),
            'misc_last_name': ('misc_last_name', 'last_name_sonstiges'),
            'misc_email': ('misc_email', 'email_sonstiges'),
            'misc_message': ('misc_message', 'message_sonstiges'),
        },
    }

    for target, source_keys in legacy_mappings.get(ticket_type, {}).items():
        if not data.get(target):
            value = _first_non_blank(*(request.form.get(source_key) for source_key in source_keys))
            if value is not None:
                data[target] = value

    if not data.get('problem_steps'):
        steps = [step.strip() for step in request.form.getlist('steps') if step and step.strip()]
        if steps:
            data['problem_steps'] = ', '.join(steps)

    return CombinedMultiDict([data, request.files])

