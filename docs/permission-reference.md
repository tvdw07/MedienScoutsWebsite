# Permission Reference

This document lists every standard permission defined in `app/permission_seed.py` and what it currently allows in the codebase.

**Status legend**

* **Active** – Currently enforced by a route, helper, or template condition.
* **Reserved** – Defined in the permission seed but not currently enforced.

## Tickets

| Permission         | Status     | Description                                                                                                                                                                                                 |
| ------------------ | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tickets.view`     | ✅ Active   | Allows access to `GET /ticketverwaltung` and ticket detail pages for owned tickets. The navigation entry is visible with this permission. Ownership is still required unless `tickets.view_all` is granted. |
| `tickets.view_all` | ✅ Active   | Allows viewing all open tickets and all ticket detail pages. Bypasses the ownership check in `ticket_owner_required`.                                                                                       |
| `tickets.create`   | ⏳ Reserved | Currently unused. The public `GET/POST /send_ticket` endpoint is still accessible without this permission.                                                                                                  |
| `tickets.claim`    | ✅ Active   | Allows claiming an open ticket via `POST /ticket/<ticket_id>/claim`.                                                                                                                                        |
| `tickets.assign`   | ✅ Active   | Allows assigning, reassigning, or removing ticket assignments via `POST /ticket/<ticket_id>/assign`. Also displays the assignment UI on non-archived tickets.                                               |
| `tickets.reply`    | ✅ Active   | Allows responding to tickets via `POST /ticket/<ticket_id>/request_help` and `POST /ticket/<ticket_id>/submit_response`.                                                                                    |
| `tickets.close`    | ✅ Active   | Allows marking a ticket as solved via `POST /ticket/<ticket_id>/mark_solved`.                                                                                                                               |
| `tickets.delete`   | ✅ Active   | Allows deleting solved tickets from both the ticket detail page and the admin delete endpoint.                                                                                                              |
| `tickets.archive`  | ✅ Active   | Allows access to `GET /archiv`.                                                                                                                                                                             |

---

## Users

| Permission                 | Status     | Description                                                                                                                             |
| -------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `users.view`               | ✅ Active   | Allows access to `GET /members/administration` and `GET /members/user/<user_id>`. Displays the user management entry in the admin menu. |
| `users.create`             | ✅ Active   | Allows creating new users via `POST /members/user`.                                                                                     |
| `users.edit`               | ⏳ Reserved | Defined but currently not enforced by any route.                                                                                        |
| `users.deactivate`         | ✅ Active   | Allows changing a user's active state via `POST /members/user/<user_id>/status`.                                                        |
| `users.delete`             | ⏳ Reserved | Defined but currently unused.                                                                                                           |
| `users.manage_roles`       | ✅ Active   | Allows adding and removing user roles via `POST /members/user/<user_id>/roles`.                                                         |
| `users.manage_permissions` | ✅ Active   | Allows managing user permission overrides (allow/deny/remove) via `POST /members/user/<user_id>/permissions`.                           |

---

## Roles

| Permission                 | Status   | Description                                                                                                                    |
| -------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `roles.view`               | ✅ Active | Allows access to `GET /roles/administration` and `GET /roles/<role_id>`. Displays the role management entry in the admin menu. |
| `roles.create`             | ✅ Active | Allows creating new roles via `POST /roles`.                                                                                   |
| `roles.edit`               | ✅ Active | Allows editing role names and descriptions via `POST /roles/<role_id>/edit`.                                                   |
| `roles.delete`             | ✅ Active | Allows deleting non-system roles via `POST /roles/<role_id>/delete`.                                                           |
| `roles.assign_permissions` | ✅ Active | Allows assigning and removing permissions from roles via `POST /roles/<role_id>/permissions`.                                  |

---

## Admin

| Permission              | Status     | Description                                                                                                                             |
| ----------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `admin.view`            | ⏳ Reserved | Generic admin permission. Not currently checked directly, but used internally by `admin_required` and intended for future admin routes. |
| `admin.view_statistics` | ✅ Active   | Allows access to `GET /admin/panel` and `GET /tickets/administration`. Also exposes the admin section in the navigation bar.            |
| `admin.manage_settings` | ⏳ Reserved | Defined but currently unused.                                                                                                           |

---

## Profile

| Permission     | Status   | Description                                                                                                                                     |
| -------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `profile.view` | ✅ Active | Allows access to `GET /profile` and `GET /profile_picture/<first_name>_<last_name>`. Displays the profile entry in the navigation bar.          |
| `profile.edit` | ✅ Active | Allows editing profile information, uploading/removing profile images, and sending password reset emails via `POST /send_password_reset_email`. |
