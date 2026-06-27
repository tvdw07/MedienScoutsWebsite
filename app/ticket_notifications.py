from datetime import datetime

from app.models import TicketAssignmentNotification, db
from app.ticket_assignments import get_ticket_label


def build_ticket_assignment_message(ticket_type, ticket_id, assigned_by_name=None):
    ticket_label = get_ticket_label(ticket_type)
    if assigned_by_name:
        return f'Dir wurde das {ticket_label}-Ticket #{ticket_id} von {assigned_by_name} zugewiesen.'
    return f'Dir wurde das {ticket_label}-Ticket #{ticket_id} zugewiesen.'


def get_unread_ticket_assignment_notifications(user_id):
    return (
        TicketAssignmentNotification.query.filter_by(user_id=user_id, read_at=None)
        .order_by(TicketAssignmentNotification.created_at.asc(), TicketAssignmentNotification.id.asc())
        .all()
    )


def create_ticket_assignment_notification(user, ticket_type, ticket_id, assigned_by_name=None):
    if not user:
        return None

    TicketAssignmentNotification.query.filter_by(
        user_id=user.id,
        ticket_type=ticket_type,
        ticket_id=ticket_id,
        read_at=None,
    ).delete(synchronize_session=False)

    notification = TicketAssignmentNotification(
        user_id=user.id,
        ticket_type=ticket_type,
        ticket_id=ticket_id,
        message=build_ticket_assignment_message(ticket_type, ticket_id, assigned_by_name=assigned_by_name),
    )
    db.session.add(notification)
    return notification


def mark_ticket_assignment_notifications_read(user_id, ticket_type, ticket_id):
    notifications = TicketAssignmentNotification.query.filter_by(
        user_id=user_id,
        ticket_type=ticket_type,
        ticket_id=ticket_id,
        read_at=None,
    ).all()
    if not notifications:
        return 0

    now = datetime.now()
    for notification in notifications:
        notification.read_at = now
    return len(notifications)


def mark_ticket_assignment_notification_read(notification_id, user_id):
    notification = db.session.get(TicketAssignmentNotification, notification_id)
    if not notification or notification.user_id != user_id:
        return None

    if notification.read_at is None:
        notification.read_at = datetime.now()
    return notification

