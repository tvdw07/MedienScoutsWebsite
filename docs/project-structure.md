# Project Structure

The application is organized around blueprints instead of one large route module.

## Main Blueprint

The `main` blueprint is split by concern:

- `app/blueprints/main/pages.py` for the start page, members page, legal pages, and archive
- `app/blueprints/main/tickets.py` for ticket creation and ticket workflow actions
- `app/blueprints/main/account.py` for profile, logout, and password reset actions
- `app/blueprints/main/utils.py` for shared ticket helpers
- `app/ticket_assignments.py` for ticket ownership helpers and ticket overview data
- `app/ticket_notifications.py` for unread assignment notifications

## Other Blueprints

- `app/blueprints/bp_auth.py` for login and password reset flows
- `app/blueprints/bp_admin.py` for administration views, the ticket overview, and JSON APIs
