import os

from flask import abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user
from werkzeug.exceptions import HTTPException

from app.decorators import any_permission_required, permission_required, ticket_owner_required
from app.forms import SendTicketForm, TicketResponseForm
from app.models import (
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
from app.ticket_assignments import (
    clear_ticket_assignments,
    count_open_tickets,
    decorate_ticket,
    get_current_ticket_assignee,
    get_open_tickets_by_type,
    get_ticket_assignment_config,
    get_ticket_model,
    set_ticket_assignee,
)
from app.ticket_notifications import (
    create_ticket_assignment_notification,
    mark_ticket_assignment_notifications_read,
)
from app.upload_utils import (
    TICKET_ATTACHMENT_FOLDER,
    UploadValidationError,
    get_upload_folder,
    normalize_stored_filename,
)
from email_tools import (
    notify_admin,
    notify_client,
    notify_user_about_ticket_assignment,
    notify_user_about_ticket_change,
    send_ticket_link,
)

from . import bp_main
from .utils import build_send_ticket_formdata, log_ticket_message, parse_optional_datetime, save_ticket_photo


def _get_ticket_config(ticket_type):
    return get_ticket_assignment_config(ticket_type)


def _load_ticket(ticket_type, ticket_id):
    ticket_model = get_ticket_model(ticket_type)
    if not ticket_model:
        return None
    return db.session.get(ticket_model, ticket_id)


def _load_problem_ticket_attachment(ticket):
    if not ticket:
        return None, None

    photo_filename = normalize_stored_filename(ticket.photo)
    if not photo_filename:
        return None, None

    upload_folder = get_upload_folder(current_app.config.get('TICKET_ATTACHMENT_FOLDER', TICKET_ATTACHMENT_FOLDER))
    file_path = os.path.join(upload_folder, photo_filename)
    if not os.path.exists(file_path):
        return None, None

    return upload_folder, photo_filename


def _send_problem_ticket_attachment(upload_folder, photo_filename):
    response = send_from_directory(upload_folder, photo_filename, max_age=0)
    response.cache_control.no_cache = True
    response.cache_control.no_store = True
    response.cache_control.private = True
    response.headers['Pragma'] = 'no-cache'
    return response


def _user_display_name(user):
    if not user:
        return None
    full_name = f'{user.first_name} {user.last_name}'.strip()
    return full_name or user.username


def _load_user_tickets(ticket_type, user_id):
    ticket_config = _get_ticket_config(ticket_type)
    if not ticket_config:
        return []

    model = ticket_config['model']
    association = ticket_config['association']

    tickets = model.query.join(association).filter(
        association.user_id == user_id,
        model.status_id != 4,
    ).all()
    for ticket in tickets:
        decorate_ticket(ticket, ticket_type)
    return tickets


def _apply_ticket_assignment(ticket_type, ticket, assignee_user, actor_user):
    old_assignee = get_current_ticket_assignee(ticket_type, ticket.id)
    actor_name = _user_display_name(actor_user)
    new_assignee_name = _user_display_name(assignee_user)
    old_assignee_name = _user_display_name(old_assignee)

    if old_assignee and assignee_user and old_assignee.id == assignee_user.id and ticket.status_id == 2:
        return False, f'Ticket ist bereits {new_assignee_name} zugewiesen.'
    if not old_assignee and assignee_user is None and ticket.status_id == 1:
        return False, 'Ticket ist bereits unzugewiesen.'

    if old_assignee and assignee_user and old_assignee.id != assignee_user.id:
        mark_ticket_assignment_notifications_read(old_assignee.id, ticket_type, ticket.id)
    elif old_assignee and assignee_user is None:
        mark_ticket_assignment_notifications_read(old_assignee.id, ticket_type, ticket.id)

    if assignee_user is None:
        clear_ticket_assignments(ticket_type, ticket.id)
        ticket.status_id = 1
        history_message = (
            f'Ticketzuweisung von {old_assignee_name} aufgehoben.'
            if old_assignee_name
            else 'Ticketzuweisung aufgehoben.'
        )
        flash_message = 'Ticketzuweisung aufgehoben.'
    else:
        set_ticket_assignee(ticket_type, ticket.id, assignee_user)
        ticket.status_id = 2
        if old_assignee_name and old_assignee.id != assignee_user.id:
            history_message = f'Ticket von {old_assignee_name} zu {new_assignee_name} neu zugewiesen.'
        else:
            history_message = f'Ticket an {new_assignee_name} zugewiesen.'
        flash_message = f'Ticket an {new_assignee_name} zugewiesen.'

    db.session.commit()

    if assignee_user:
        create_ticket_assignment_notification(
            assignee_user,
            ticket_type,
            ticket.id,
            assigned_by_name=actor_name,
        )
        db.session.commit()
        notify_user_about_ticket_assignment(
            ticket,
            ticket_type,
            assignee_user,
            assigned_by_name=actor_name,
        )

    log_ticket_message(ticket_type, ticket.id, history_message, actor_name)
    return True, flash_message


@bp_main.route('/ticketverwaltung')
@any_permission_required(['tickets.view', 'tickets.view_all'])
def ticket_verwaltung():
    """Overview of open tickets and the current user's tickets."""
    can_view_all_tickets = current_user.has_permission('tickets.view_all')

    if can_view_all_tickets:
        open_tickets_by_type = get_open_tickets_by_type()
        open_problem_tickets = open_tickets_by_type['problem']
        open_training_tickets = open_tickets_by_type['training']
        open_misc_tickets = open_tickets_by_type['misc']
        open_media_consulting_tickets = open_tickets_by_type['medienberatung']
    else:
        open_problem_tickets = []
        open_training_tickets = []
        open_misc_tickets = []
        open_media_consulting_tickets = []

    my_problem_tickets = _load_user_tickets('problem', current_user.id)
    my_training_tickets = _load_user_tickets('training', current_user.id)
    my_misc_tickets = _load_user_tickets('misc', current_user.id)
    my_media_consulting_tickets = _load_user_tickets('medienberatung', current_user.id)

    my_tickets = my_problem_tickets + my_training_tickets + my_misc_tickets + my_media_consulting_tickets
    total_open_tickets = count_open_tickets() if can_view_all_tickets else 0

    return render_template(
        'tickets/ticketverwaltung.html',
        open_problem_tickets=open_problem_tickets,
        open_training_tickets=open_training_tickets,
        open_misc_tickets=open_misc_tickets,
        open_media_consulting_tickets=open_media_consulting_tickets,
        my_tickets=my_tickets,
        total_open_tickets=total_open_tickets,
        can_view_all_tickets=can_view_all_tickets,
    )


@bp_main.route('/ticket/<string:ticket_type>/<int:ticket_id>/details')
@any_permission_required(['tickets.view', 'tickets.view_all'])
@ticket_owner_required
def ticket_details(ticket_type, ticket_id):
    """Display the details of a specific ticket."""
    ticket = _load_ticket(ticket_type, ticket_id)
    ticket_config = _get_ticket_config(ticket_type)
    if not ticket_config:
        flash('Ungultiger Ticket-Typ.', 'danger')
        return redirect(url_for('main.ticket_verwaltung'))

    if not ticket:
        flash('Ticket nicht gefunden.', 'danger')
        return redirect(url_for('main.ticket_verwaltung'))

    assigned_user = get_current_ticket_assignee(ticket_type, ticket_id)
    assigned_user_name = _user_display_name(assigned_user)
    assignable_users = []
    can_assign_ticket = current_user.has_permission('tickets.assign') and ticket.status_id != 4
    if can_assign_ticket:
        assignable_users = User.query.filter_by(active=True).order_by(User.last_name, User.first_name, User.username).all()

    attachment_url = None
    attachment_label = None
    if ticket_type == 'problem' and ticket.photo:
        attachment_url = url_for('main.ticket_attachment', ticket_type=ticket_type, ticket_id=ticket.id)
        attachment_label = ticket.photo_original_name or 'Hochgeladenes Bild'

    ticket_history = TicketHistory.query.filter_by(ticket_type=ticket_type, ticket_id=ticket_id).order_by(
        TicketHistory.created_at
    ).all()
    response_form = TicketResponseForm()
    return render_template(
        'tickets/ticket_details.html',
        ticket=ticket,
        ticket_type=ticket_type,
        assigned_user=assigned_user,
        assigned_user_name=assigned_user_name,
        assignable_users=assignable_users,
        can_assign_ticket=can_assign_ticket,
        ticket_history=ticket_history,
        response_form=response_form,
        response_form_action=url_for('main.submit_response', ticket_id=ticket.id),
        attachment_url=attachment_url,
        attachment_label=attachment_label,
    )


@bp_main.route('/ticket/<int:ticket_id>/claim', methods=['POST'])
@permission_required('tickets.claim')
def claim_ticket(ticket_id):
    """A user claims a ticket."""
    ticket_type = request.form.get('ticket_type')
    ticket = _load_ticket(ticket_type, ticket_id)
    if not _get_ticket_config(ticket_type):
        current_app.logger.error(f'Invalid ticket type: {ticket_type}')
        flash('Ungultiger Ticket-Typ.', 'danger')
        return redirect(url_for('main.ticket_verwaltung'))

    if not ticket:
        flash('Ticket nicht gefunden.', 'danger')
        return redirect(url_for('main.ticket_verwaltung'))

    if ticket.status_id != 1:
        flash('Ticket kann nicht mehr übernommen werden.', 'danger')
        return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))

    try:
        changed, flash_message = _apply_ticket_assignment(ticket_type, ticket, current_user, current_user)
        if changed:
            flash('Ticket erfolgreich ubernommen.', 'success')
        else:
            flash(flash_message, 'info')
    except Exception as exc:
        db.session.rollback()
        flash('Fehler beim Ubernehmen des Tickets.', 'danger')
        current_app.logger.error(f'Fehler beim Ubernehmen des Tickets: {exc}')

    return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))


@bp_main.route('/ticket/<int:ticket_id>/assign', methods=['POST'])
@permission_required('tickets.assign')
@ticket_owner_required
def assign_ticket(ticket_id):
    ticket_type = request.form.get('ticket_type')
    ticket = _load_ticket(ticket_type, ticket_id)
    if not _get_ticket_config(ticket_type):
        flash('Ungultiger Ticket-Typ.', 'danger')
        return redirect(url_for('main.ticket_verwaltung'))

    if not ticket:
        flash('Ticket nicht gefunden.', 'danger')
        return redirect(url_for('main.ticket_verwaltung'))

    if ticket.status_id == 4:
        flash('Ticket kann nicht mehr zugewiesen werden.', 'danger')
        return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))

    assignee_value = (request.form.get('assignee_id') or '').strip()
    assignee = None
    if assignee_value:
        if not assignee_value.isdigit():
            flash('Ungultige Benutzerzuweisung.', 'danger')
            return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))
        assignee = db.session.get(User, int(assignee_value))
        if not assignee or not assignee.active:
            flash('Der gewahlte Benutzer ist nicht aktiv oder existiert nicht.', 'danger')
            return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))

    try:
        changed, flash_message = _apply_ticket_assignment(ticket_type, ticket, assignee, current_user)
        flash(flash_message, 'success' if changed else 'info')
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Fehler beim Zuweisen des Tickets: {exc}')
        flash('Fehler beim Zuweisen des Tickets.', 'danger')

    return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))


@bp_main.route('/ticket/<int:ticket_id>/request_help', methods=['POST'])
@permission_required('tickets.reply')
@ticket_owner_required
def request_help(ticket_id):
    """Request help for a specific ticket."""
    ticket_type = request.form.get('ticket_type')
    ticket = _load_ticket(ticket_type, ticket_id)
    if not _get_ticket_config(ticket_type) or not ticket:
        flash('Invalid ticket type.', 'danger')
        return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))

    notify_admin(ticket, ticket_type, 'Help is requested for the following ticket:')
    flash(f'Help request has been sent for ticket ID: {ticket_id}', 'info')
    return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))


@bp_main.route('/ticket/<int:ticket_id>/submit_response', methods=['POST'])
@permission_required('tickets.reply')
@ticket_owner_required
def submit_response(ticket_id):
    """Submit a response for a specific ticket."""
    ticket_type = request.form.get('ticket_type')
    response_form = TicketResponseForm()
    if not ticket_type:
        flash('Ticket type is required.', 'danger')
        return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))

    if not response_form.validate_on_submit():
        flash('Please enter a response message.', 'danger')
        return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))

    ticket = _load_ticket(ticket_type, ticket_id)
    if not ticket:
        flash('Ticket not found.', 'danger')
        return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))

    if ticket.status_id == 4 or ticket.status_id == 1:
        flash('Ticket is already solved.', 'danger')
        return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))

    author_type = 'MedienScout: ' + current_user.first_name + ' ' + current_user.last_name
    response_message = response_form.response_message.data
    log_ticket_message(ticket_type, ticket_id, response_message, author_type)

    ticket.status_id = 3
    db.session.commit()

    notify_client(ticket, response_message)

    flash(f'Response has been submitted for ticket ID: {ticket_id}', 'info')
    return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))


@bp_main.route('/ticket/<int:ticket_id>/mark_solved', methods=['POST'])
@permission_required('tickets.close')
@ticket_owner_required
def mark_ticket_solved(ticket_id):
    """Mark a specific ticket as solved."""
    ticket_type = request.form.get('ticket_type')
    ticket = _load_ticket(ticket_type, ticket_id)

    if not _get_ticket_config(ticket_type):
        flash('Invalid ticket type.', 'danger')
        return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))

    if ticket:
        ticket.status_id = 4
        db.session.commit()
        flash('Ticket marked as solved.', 'success')
    else:
        current_app.logger.error(f'Ticket not found: {ticket_id}, {ticket_type}')
        flash('Ticket not found.', 'danger')

    return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))


@bp_main.route('/send_ticket', methods=['GET', 'POST'])
def send_ticket():
    """Handle submission of different ticket types."""
    form = SendTicketForm(formdata=build_send_ticket_formdata() if request.method == 'POST' else None)
    if request.method == 'GET' and not form.ticket_type.data:
        form.ticket_type.data = 'problem'

    if request.method == 'POST':
        if not form.validate():
            flash('Please fill in all the required fields.', 'danger')
            return render_template('tickets/ticket.html', form=form)

        ticket_type = form.ticket_type.data

        try:
            if ticket_type == 'problem':
                steps_taken = [step.strip() for step in (form.problem_steps.data or '').split(',') if step.strip()]
                if not steps_taken:
                    flash('Please fill in all the required fields.', 'danger')
                    return render_template('tickets/ticket.html', form=form)
                photo = form.photo.data
                photo_filename = None
                photo_original_name = None
                if photo:
                    try:
                        photo_filename, photo_original_name = save_ticket_photo(photo)
                    except UploadValidationError as exc:
                        current_app.logger.warning('Ticket image upload rejected: %s', exc)
                        flash(exc.message, 'danger')
                        if exc.status_code == 413:
                            abort(413)
                        return render_template('tickets/ticket.html', form=form), exc.status_code
                ticket = ProblemTicket(
                    first_name=form.problem_first_name.data,
                    last_name=form.problem_last_name.data,
                    email=form.problem_email.data,
                    class_name=form.problem_class_name.data,
                    serial_number=form.problem_serial_number.data or None,
                    problem_description=form.problem_description.data,
                    steps_taken=', '.join(steps_taken),
                    photo=photo_filename,
                    photo_original_name=photo_original_name,
                    status_id=1,
                )
                current_app.logger.info('Problem ticket submitted')
            elif ticket_type == 'fortbildung':
                proposed_date = parse_optional_datetime(form.training_proposed_date.data)
                if form.training_proposed_date.data and proposed_date is None:
                    flash('Please provide a valid proposed date.', 'danger')
                    return render_template('tickets/ticket.html', form=form)
                ticket = TrainingTicket(
                    class_teacher=form.training_class_teacher.data,
                    email=form.training_email.data,
                    training_type=form.training_type.data,
                    training_reason=form.training_reason.data,
                    proposed_date=proposed_date,
                    status_id=1,
                )
                current_app.logger.info('Training ticket submitted')
            elif ticket_type == 'medienberatung':
                proposed_date = parse_optional_datetime(form.media_proposed_date.data)
                if form.media_proposed_date.data and proposed_date is None:
                    flash('Please provide a valid proposed date.', 'danger')
                    return render_template('tickets/ticket.html', form=form)
                ticket = MediaConsultingTicket(
                    first_name=form.media_first_name.data,
                    last_name=form.media_last_name.data,
                    email=form.media_email.data,
                    class_name=form.media_class_name.data,
                    topic=form.media_topic.data,
                    description=form.media_description.data,
                    proposed_date=proposed_date,
                    status_id=1,
                )
                current_app.logger.info('Media consulting ticket submitted')
            else:
                ticket = MiscTicket(
                    first_name=form.misc_first_name.data,
                    last_name=form.misc_last_name.data,
                    email=form.misc_email.data,
                    message=form.misc_message.data,
                    status_id=1,
                )
                current_app.logger.info('Misc ticket submitted')

            db.session.add(ticket)
            db.session.commit()

            send_ticket_link(ticket)

            flash(f'Ticket submitted successfully! Type: {ticket_type}', 'success')
            return redirect(url_for('main.home'))
        except HTTPException:
            raise
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f'Error while submitting ticket: {exc}')
            flash('An error occurred while submitting the ticket.', 'danger')
            return render_template('tickets/ticket.html', form=form)

    return render_template('tickets/ticket.html', form=form)


@bp_main.route('/ticket/<token>', methods=['GET', 'POST'])
def view_ticket(token):
    """Display a ticket by token and allow responses."""
    ticket = None
    ticket_type = None
    for TicketModel, type_name in [
        (ProblemTicket, 'problem'),
        (TrainingTicket, 'training'),
        (MiscTicket, 'misc'),
        (MediaConsultingTicket, 'medienberatung'),
    ]:
        ticket = TicketModel.verify_token(token)
        if ticket:
            ticket_type = type_name
            break

    if not ticket:
        current_app.logger.error('Invalid or expired ticket token')
        flash('Invalid or expired token', 'danger')
        return redirect(url_for('main.home'))

    response_form = TicketResponseForm()
    attachment_url = None
    attachment_label = None
    if ticket_type == 'problem' and ticket.photo:
        attachment_url = url_for('main.ticket_attachment_public', token=token)
        attachment_label = ticket.photo_original_name or 'Hochgeladenes Bild'

    if request.method == 'POST':
        if response_form.validate_on_submit():
            response_message = response_form.response_message.data
            if ticket_type == 'problem':
                author_type = ticket.first_name + ' ' + ticket.last_name
            elif ticket_type == 'training':
                author_type = ticket.class_teacher
            else:
                author_type = ticket.first_name + ' ' + ticket.last_name

            log_ticket_message(ticket_type, ticket.id, response_message, author_type)
            flash('Your response has been submitted.', 'success')
            notify_user_about_ticket_change(ticket, response_message, ticket_type)
            return redirect(url_for('main.view_ticket', token=token))

        flash('Please enter a response message.', 'danger')

    ticket_history = TicketHistory.query.filter_by(ticket_type=ticket_type, ticket_id=ticket.id).order_by(
        TicketHistory.created_at
    ).all()

    return render_template(
        'tickets/view_ticket.html',
        ticket=ticket,
        ticket_type=ticket_type,
        token=token,
        ticket_history=ticket_history,
        response_form=response_form,
        response_form_action=url_for('main.view_ticket', token=token),
        attachment_url=attachment_url,
        attachment_label=attachment_label,
    )


@bp_main.route('/ticket/<string:token>/attachment')
def ticket_attachment_public(token):
    ticket = ProblemTicket.verify_token(token)
    if not ticket:
        abort(404)

    upload_folder, photo_filename = _load_problem_ticket_attachment(ticket)
    if not upload_folder or not photo_filename:
        abort(404)

    return _send_problem_ticket_attachment(upload_folder, photo_filename)


@bp_main.route('/ticket/<string:ticket_type>/<int:ticket_id>/attachment')
@any_permission_required(['tickets.view', 'tickets.view_all'])
@ticket_owner_required
def ticket_attachment(ticket_type, ticket_id):
    ticket = _load_ticket(ticket_type, ticket_id)
    if ticket_type != 'problem' or not ticket:
        abort(404)

    upload_folder, photo_filename = _load_problem_ticket_attachment(ticket)
    if not upload_folder or not photo_filename:
        abort(404)

    return _send_problem_ticket_attachment(upload_folder, photo_filename)
