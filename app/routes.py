"""Compatibility wrapper for the main blueprint and email helper hooks."""

from email_tools import (
    notify_admin,
    notify_client,
    notify_user_about_ticket_change,
    send_reset_email,
    send_ticket_link,
)

from app.blueprints.main import bp_main

__all__ = [
    'bp_main',
    'notify_admin',
    'notify_client',
    'notify_user_about_ticket_change',
    'send_reset_email',
    'send_ticket_link',
]

