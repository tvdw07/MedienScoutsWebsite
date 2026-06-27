import app.routes as legacy_routes
from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

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
    db,
)

from . import bp_main
from .utils import build_send_ticket_formdata, log_ticket_message, parse_optional_datetime, save_ticket_photo

TICKET_CONFIG = {
    'problem': {
        'model': ProblemTicket,
        'association': ProblemTicketUser,
        'association_field': 'problem_ticket_id',
        'description_attr': 'problem_description',
    },
    'training': {
        'model': TrainingTicket,
        'association': TrainingTicketUser,
        'association_field': 'training_ticket_id',
        'description_attr': 'training_reason',
    },
    'misc': {
        'model': MiscTicket,
        'association': MiscTicketUser,
        'association_field': 'misc_ticket_id',
        'description_attr': 'message',
    },
    'medienberatung': {
        'model': MediaConsultingTicket,
        'association': MediaConsultingTicketUser,
        'association_field': 'media_consulting_ticket_id',
        'description_attr': None,
    },
}


def _get_ticket_config(ticket_type):
    return TICKET_CONFIG.get(ticket_type)


def _load_ticket(ticket_type, ticket_id):
    ticket_config = _get_ticket_config(ticket_type)
    if not ticket_config:
        return None
    return ticket_config['model'].query.get(ticket_id)


def _decorate_ticket(ticket, ticket_type):
    ticket.type = ticket_type
    description_attr = TICKET_CONFIG[ticket_type]['description_attr']
    if description_attr:
        ticket.description = getattr(ticket, description_attr)


def _create_ticket_user(ticket_type, ticket_id, user_id):
    ticket_config = _get_ticket_config(ticket_type)
    if not ticket_config:
        return None

    association_kwargs = {
        ticket_config['association_field']: ticket_id,
        'user_id': user_id,
    }
    return ticket_config['association'](**association_kwargs)


def _load_open_tickets(ticket_type):
    ticket_config = _get_ticket_config(ticket_type)
    if not ticket_config:
        return []

    tickets = ticket_config['model'].query.filter_by(status_id=1).all()
    for ticket in tickets:
        _decorate_ticket(ticket, ticket_type)
    return tickets


def _load_user_tickets(ticket_type, user_id):
    ticket_config = _get_ticket_config(ticket_type)
    if not ticket_config:
        return []

    model = ticket_config['model']
    association = ticket_config['association']
    association_field = ticket_config['association_field']

    tickets = model.query.join(association).filter(
        association.user_id == user_id,
        model.status_id != 4,
    ).all()
    for ticket in tickets:
        _decorate_ticket(ticket, ticket_type)
    return tickets


@bp_main.route('/ticketverwaltung')
@any_permission_required(['tickets.view', 'tickets.view_all'])
def ticket_verwaltung():
    """Overview of open tickets and the current user's tickets."""
    can_view_all_tickets = current_user.has_permission('tickets.view_all')

    if can_view_all_tickets:
        open_problem_tickets = _load_open_tickets('problem')
        open_training_tickets = _load_open_tickets('training')
        open_misc_tickets = _load_open_tickets('misc')
        open_media_consulting_tickets = _load_open_tickets('medienberatung')
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
    total_open_tickets = (
        len(open_problem_tickets) + len(open_training_tickets) + len(open_misc_tickets) + len(open_media_consulting_tickets)
        if can_view_all_tickets
        else 0
    )

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
    if ticket_type not in TICKET_CONFIG:
        flash('Ungultiger Ticket-Typ.', 'danger')
        return redirect(url_for('main.ticket_verwaltung'))

    if not ticket:
        flash('Ticket nicht gefunden.', 'danger')
        return redirect(url_for('main.ticket_verwaltung'))

    ticket_history = TicketHistory.query.filter_by(ticket_type=ticket_type, ticket_id=ticket_id).order_by(
        TicketHistory.created_at
    ).all()
    response_form = TicketResponseForm()
    return render_template(
        'tickets/ticket_details.html',
        ticket=ticket,
        ticket_type=ticket_type,
        ticket_history=ticket_history,
        response_form=response_form,
        response_form_action=url_for('main.submit_response', ticket_id=ticket.id),
    )


@bp_main.route('/ticket/<int:ticket_id>/claim', methods=['POST'])
@permission_required('tickets.claim')
def claim_ticket(ticket_id):
    """A user claims a ticket."""
    user_id = current_user.id
    ticket_type = request.form.get('ticket_type')
    ticket_config = _get_ticket_config(ticket_type)
    if not ticket_config:
        current_app.logger.error(f'Invalid ticket type: {ticket_type}')
        flash('Ungultiger Ticket-Typ.', 'danger')
        return redirect(url_for('main.ticket_verwaltung'))

    ticket = ticket_config['model'].query.get(ticket_id)
    if not ticket:
        flash('Ticket nicht gefunden.', 'danger')
        return redirect(url_for('main.ticket_verwaltung'))

    try:
        ticket_user = _create_ticket_user(ticket_type, ticket_id, user_id)
        ticket.status_id = 2
        db.session.add(ticket_user)
        db.session.commit()
        flash('Ticket erfolgreich ubernommen.', 'success')
    except Exception as exc:
        db.session.rollback()
        flash('Fehler beim Ubernehmen des Tickets.', 'danger')
        current_app.logger.error(f'Fehler beim Ubernehmen des Tickets: {exc}')

    return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))


@bp_main.route('/ticket/<int:ticket_id>/request_help', methods=['POST'])
@permission_required('tickets.reply')
@ticket_owner_required
def request_help(ticket_id):
    """Request help for a specific ticket."""
    ticket_type = request.form.get('ticket_type')
    ticket = _load_ticket(ticket_type, ticket_id)
    if ticket_type not in TICKET_CONFIG or not ticket:
        flash('Invalid ticket type.', 'danger')
        return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))

    legacy_routes.notify_admin(ticket, ticket_type, 'Help is requested for the following ticket:')
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

    legacy_routes.notify_client(ticket, response_message)

    flash(f'Response has been submitted for ticket ID: {ticket_id}', 'info')
    return redirect(url_for('main.ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))


@bp_main.route('/ticket/<int:ticket_id>/mark_solved', methods=['POST'])
@permission_required('tickets.close')
@ticket_owner_required
def mark_ticket_solved(ticket_id):
    """Mark a specific ticket as solved."""
    ticket_type = request.form.get('ticket_type')
    ticket = _load_ticket(ticket_type, ticket_id)

    if ticket_type not in TICKET_CONFIG:
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
                photo_path = save_ticket_photo(photo, form.problem_first_name.data, form.problem_last_name.data)
                if photo and photo_path is None:
                    return render_template('tickets/ticket.html', form=form)
                ticket = ProblemTicket(
                    first_name=form.problem_first_name.data,
                    last_name=form.problem_last_name.data,
                    email=form.problem_email.data,
                    class_name=form.problem_class_name.data,
                    serial_number=form.problem_serial_number.data or None,
                    problem_description=form.problem_description.data,
                    steps_taken=', '.join(steps_taken),
                    photo=photo_path,
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

            legacy_routes.send_ticket_link(ticket)

            flash(f'Ticket submitted successfully! Type: {ticket_type}', 'success')
            return redirect(url_for('main.home'))
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
            legacy_routes.notify_user_about_ticket_change(ticket, response_message, ticket_type)
            return redirect(url_for('main.view_ticket', token=token))

        flash('Please enter a response message.', 'danger')

    ticket_history = TicketHistory.query.filter_by(ticket_type=ticket_type, ticket_id=ticket.id).order_by(
        TicketHistory.created_at
    ).all()

    return render_template(
        'tickets/view_ticket.html',
        ticket=ticket,
        token=token,
        ticket_history=ticket_history,
        response_form=response_form,
        response_form_action=url_for('main.view_ticket', token=token),
    )

