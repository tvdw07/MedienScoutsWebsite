# Project Structure

The application is organized around blueprints instead of one large route module.

## Main Blueprint

The `main` blueprint is split by concern:

- `app/blueprints/main/pages.py` for the start page, members page, legal pages, and archive
- `app/blueprints/main/tickets.py` for ticket creation and ticket workflow actions
- `app/blueprints/main/account.py` for profile, logout, and password reset actions
- `app/blueprints/main/utils.py` for shared ticket helpers

## Other Blueprints

- `app/blueprints/bp_auth.py` for login and password reset flows
- `app/blueprints/bp_admin.py` for administration views and JSON APIs

## Compatibility Layer

`app/routes.py` now only re-exports the main blueprint and email helper hooks for older imports and tests.
New code should import the blueprint from `app.blueprints.main`.

