from app.models import (
    MediaConsultingTicket,
    MediaConsultingTicketUser,
    MiscTicket,
    MiscTicketUser,
    ProblemTicket,
    ProblemTicketUser,
    TrainingTicket,
    TrainingTicketUser,
    db,
)

TICKET_TYPE_LABELS = {
    'problem': 'Problem',
    'training': 'Fortbildung',
    'misc': 'Sonstiges',
    'medienberatung': 'Medienberatung',
}

TICKET_ASSIGNMENT_CONFIG = {
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

TICKET_OVERVIEW_BADGE_CLASSES = {
    'problem': 'bg-danger',
    'training': 'bg-warning text-dark',
    'misc': 'bg-info text-dark',
    'medienberatung': 'bg-primary',
}

TICKET_STATUS_LABELS = {
    1: 'Offen',
    2: 'In Bearbeitung',
    3: 'Wartend',
    4: 'Archiviert',
}

TICKET_STATUS_BADGE_CLASSES = {
    1: 'bg-success',
    2: 'bg-warning text-dark',
    3: 'bg-info text-dark',
    4: 'bg-secondary',
}


def get_ticket_assignment_config(ticket_type):
    return TICKET_ASSIGNMENT_CONFIG.get(ticket_type)


def get_ticket_model(ticket_type):
    ticket_config = get_ticket_assignment_config(ticket_type)
    return ticket_config['model'] if ticket_config else None


def get_ticket_association_model(ticket_type):
    ticket_config = get_ticket_assignment_config(ticket_type)
    return ticket_config['association'] if ticket_config else None


def get_ticket_association_field(ticket_type):
    ticket_config = get_ticket_assignment_config(ticket_type)
    return ticket_config['association_field'] if ticket_config else None


def get_ticket_label(ticket_type):
    return TICKET_TYPE_LABELS.get(ticket_type, 'Ticket')


def _get_ticket_admin_name(ticket_type, ticket):
    if ticket_type == 'training':
        return ticket.class_teacher
    return f'{ticket.first_name} {ticket.last_name}'.strip()


def _get_ticket_admin_summary(ticket_type, ticket):
    if ticket_type == 'problem':
        return ticket.problem_description
    if ticket_type == 'training':
        return ticket.training_reason or ticket.training_type
    if ticket_type == 'misc':
        return ticket.message
    if ticket_type == 'medienberatung':
        parts = [ticket.topic, ticket.description]
        return ' - '.join(part for part in parts if part)
    return ''


def decorate_ticket(ticket, ticket_type):
    ticket.type = ticket_type
    ticket.ticket_label = get_ticket_label(ticket_type)
    ticket.ticket_badge_class = TICKET_OVERVIEW_BADGE_CLASSES.get(ticket_type, 'bg-secondary')
    ticket.ticket_name = _get_ticket_admin_name(ticket_type, ticket)
    ticket.ticket_summary = _get_ticket_admin_summary(ticket_type, ticket)
    ticket.status_label = TICKET_STATUS_LABELS.get(ticket.status_id, 'Unbekannt')
    ticket.status_badge_class = TICKET_STATUS_BADGE_CLASSES.get(ticket.status_id, 'bg-secondary')

    ticket_config = get_ticket_assignment_config(ticket_type)
    description_attr = ticket_config['description_attr'] if ticket_config else None
    if description_attr:
        ticket.description = getattr(ticket, description_attr)
    return ticket


def _load_ticket_collection(ticket_type, query):
    tickets = query.all()
    for ticket in tickets:
        decorate_ticket(ticket, ticket_type)
    return sorted(tickets, key=lambda ticket: (ticket.created_at, ticket.id), reverse=True)


def get_open_tickets(ticket_type):
    ticket_config = get_ticket_assignment_config(ticket_type)
    if not ticket_config:
        return []

    return _load_ticket_collection(ticket_type, ticket_config['model'].query.filter_by(status_id=1))


def get_open_tickets_by_type():
    return {ticket_type: get_open_tickets(ticket_type) for ticket_type in TICKET_ASSIGNMENT_CONFIG}


def get_all_open_tickets():
    tickets = []
    for ticket_type in TICKET_ASSIGNMENT_CONFIG:
        tickets.extend(get_open_tickets(ticket_type))
    return sorted(tickets, key=lambda ticket: (ticket.created_at, ticket.id), reverse=True)


def get_non_archived_tickets(ticket_type):
    ticket_config = get_ticket_assignment_config(ticket_type)
    if not ticket_config:
        return []

    return _load_ticket_collection(ticket_type, ticket_config['model'].query.filter(ticket_config['model'].status_id != 4))


def get_non_archived_tickets_by_type():
    return {ticket_type: get_non_archived_tickets(ticket_type) for ticket_type in TICKET_ASSIGNMENT_CONFIG}


def get_all_non_archived_tickets():
    tickets = []
    for ticket_type in TICKET_ASSIGNMENT_CONFIG:
        tickets.extend(get_non_archived_tickets(ticket_type))
    return sorted(tickets, key=lambda ticket: (ticket.created_at, ticket.id), reverse=True)


def count_open_tickets(ticket_type=None):
    if ticket_type:
        ticket_config = get_ticket_assignment_config(ticket_type)
        if not ticket_config:
            return 0
        return ticket_config['model'].query.filter_by(status_id=1).count()

    return sum(count_open_tickets(current_ticket_type) for current_ticket_type in TICKET_ASSIGNMENT_CONFIG)


def count_non_archived_tickets(ticket_type=None):
    if ticket_type:
        ticket_config = get_ticket_assignment_config(ticket_type)
        if not ticket_config:
            return 0
        return ticket_config['model'].query.filter(ticket_config['model'].status_id != 4).count()

    return sum(count_non_archived_tickets(current_ticket_type) for current_ticket_type in TICKET_ASSIGNMENT_CONFIG)


def get_current_ticket_assignee(ticket_type, ticket_id):
    ticket_config = get_ticket_assignment_config(ticket_type)
    if not ticket_config:
        return None

    association = ticket_config['association']
    association_field = ticket_config['association_field']
    ticket_user = (
        association.query.filter(getattr(association, association_field) == ticket_id)
        .order_by(association.assigned_at.desc(), association.ticket_user_id.desc())
        .first()
    )
    return ticket_user.user if ticket_user else None


def clear_ticket_assignments(ticket_type, ticket_id):
    ticket_config = get_ticket_assignment_config(ticket_type)
    if not ticket_config:
        return 0

    association = ticket_config['association']
    association_field = ticket_config['association_field']
    return association.query.filter(getattr(association, association_field) == ticket_id).delete(
        synchronize_session=False
    )


def set_ticket_assignee(ticket_type, ticket_id, user):
    clear_ticket_assignments(ticket_type, ticket_id)

    if user is None:
        return None

    ticket_config = get_ticket_assignment_config(ticket_type)
    if not ticket_config:
        return None

    association = ticket_config['association']
    association_field = ticket_config['association_field']
    ticket_user = association(**{association_field: ticket_id, 'user_id': user.id})
    db.session.add(ticket_user)
    return ticket_user
