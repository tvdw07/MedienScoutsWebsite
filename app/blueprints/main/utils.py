from datetime import datetime

from flask import request
from werkzeug.datastructures import CombinedMultiDict

from app.models import TicketHistory, db
from app.upload_utils import save_ticket_attachment


def parse_optional_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def save_ticket_photo(photo):
    if not photo:
        return None, None
    return save_ticket_attachment(photo)


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
    data = request.form.copy()

    if not data.get('problem_steps'):
        steps = [step.strip() for step in request.form.getlist('steps') if step and step.strip()]
        if steps:
            data['problem_steps'] = ', '.join(steps)

    return CombinedMultiDict([data, request.files])
