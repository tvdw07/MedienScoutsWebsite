from functools import wraps
from flask import redirect, url_for, flash, request
from flask_login import current_user

from app import ProblemTicketUser, TrainingTicketUser, MiscTicketUser


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:  # Access is_admin as a property
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_teacher:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def ticket_owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_admin:
            return f(*args, **kwargs)

        ticket_id = kwargs.get('ticket_id')
        ticket_type = request.form.get('ticket_type') or request.args.get('ticket_type')

        if ticket_type == 'problem':
            ticket_user = ProblemTicketUser.query.filter_by(problem_ticket_id=ticket_id, user_id=current_user.id).first()
        elif ticket_type == 'training':
            ticket_user = TrainingTicketUser.query.filter_by(training_ticket_id=ticket_id, user_id=current_user.id).first()
        elif ticket_type == 'misc':
            ticket_user = MiscTicketUser.query.filter_by(misc_ticket_id=ticket_id, user_id=current_user.id).first()
        else:
            ticket_user = None

        if not ticket_user:
            flash('You do not have permission to access this ticket.', 'danger')
            return redirect(url_for('ticket_verwaltung'))

        return f(*args, **kwargs)
    return decorated_function