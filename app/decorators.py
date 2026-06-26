from functools import wraps

from werkzeug.routing import BuildError
from flask import abort, current_app, flash, redirect, request, url_for
from flask_login import current_user

from app import ProblemTicketUser, TrainingTicketUser, MiscTicketUser


def _login_redirect():
    login_manager = getattr(current_app, 'login_manager', None)
    login_view = getattr(login_manager, 'login_view', None)
    if login_view:
        try:
            return redirect(url_for(login_view, next=request.url))
        except BuildError:
            pass
    return redirect('/login')


def _normalize_permissions(required_permissions):
    if isinstance(required_permissions, str):
        return (required_permissions,)
    return tuple(required_permissions)


def _permission_guard(required_permissions, require_all):
    normalized_permissions = _normalize_permissions(required_permissions)

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return _login_redirect()

            checks = (current_user.has_permission(permission) for permission in normalized_permissions)
            allowed = all(checks) if require_all else any(checks)
            if not allowed:
                abort(403)

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def permission_required(permission_name):
    return _permission_guard(permission_name, require_all=True)


def any_permission_required(required_permissions):
    return _permission_guard(required_permissions, require_all=False)


def all_permissions_required(required_permissions):
    return _permission_guard(required_permissions, require_all=True)


# Decorator to restrict access to admin users
def admin_required(f):
    return permission_required('admin.view')(f)


# Decorator to restrict access to teacher users
def teacher_required(f):
    return permission_required('tickets.assign')(f)


# Decorator to restrict access to ticket owners or admins
def ticket_owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return _login_redirect()

        if current_user.has_permission('tickets.view_all'):
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
            return redirect(url_for('main.ticket_verwaltung'))

        return f(*args, **kwargs)

    return decorated_function
