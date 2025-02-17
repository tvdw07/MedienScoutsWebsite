from functools import wraps
from flask import redirect, url_for, flash, request
from flask_login import current_user

from app import ProblemTicketUser, TrainingTicketUser, MiscTicketUser


# Decorator to restrict access to admin users
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:  # Check if the current user is an admin
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)

    return decorated_function


# Decorator to restrict access to teacher users
def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_teacher:  # Check if the current user is a teacher
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)

    return decorated_function


# Decorator to restrict access to ticket owners or admins
def ticket_owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_admin:  # Admins have access to all tickets
            return f(*args, **kwargs)

        ticket_id = kwargs.get('ticket_id')
        ticket_type = request.form.get('ticket_type') or request.args.get('ticket_type')

        # Determine the ticket type and check if the current user is the owner
        if ticket_type == 'problem':
            ticket_user = ProblemTicketUser.query.filter_by(problem_ticket_id=ticket_id, user_id=current_user.id).first()
        elif ticket_type == 'training':
            ticket_user = TrainingTicketUser.query.filter_by(training_ticket_id=ticket_id, user_id=current_user.id).first()
        elif ticket_type == 'misc':
            ticket_user = MiscTicketUser.query.filter_by(misc_ticket_id=ticket_id, user_id=current_user.id).first()
        else:
            ticket_user = None

        if not ticket_user:  # If the user is not the owner, deny access
            flash('You do not have permission to access this ticket.', 'danger')
            return redirect(url_for('ticket_verwaltung'))

        return f(*args, **kwargs)

    return decorated_function
