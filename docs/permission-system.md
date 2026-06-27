# Permission System

The application uses permissions as the source of truth for access control.
Roles exist only to group permissions. Users can inherit permissions through one
or more roles and can also get direct overrides.

## Permission Definition

All permissions are defined centrally in `app/permission_seed.py` in
`STANDARD_PERMISSIONS`. The seed process creates missing permission records and
keeps the data idempotent.

Example permissions:

- `tickets.view`
- `users.manage_roles`
- `roles.assign_permissions`
- `profile.edit`

## Roles

Roles group permissions through the `RolePermission` association table.

Standard roles:

- `Admin` - full access to all permissions
- `Teacher` - broad ticket handling permissions
- `MediaScout` - ticket handling permissions without admin rights
- `User` - minimal profile permissions

## User Overrides

Users can receive direct permission overrides through
`UserPermissionOverride`.

- `allowed=True` adds the permission
- `allowed=False` removes the permission explicitly
- `reason` is optional and is kept for auditability

Denies always win over role grants and direct allows.

## Protecting Routes

Use `@permission_required("permission.name")` on routes that require a single
permission.

Optional helpers:

- `@any_permission_required([...])`
- `@all_permissions_required([...])`

Behavior:

- anonymous users are redirected to login
- authenticated users without the permission get `403`
- users with the permission may access the route

Admin-facing mutation routes also enforce self-protection: a user cannot remove
the last admin-related permission source from their own account or from a role
they currently use to obtain admin access.

In this repository the protected routes live in:

- `app/blueprints/main/pages.py`
- `app/blueprints/main/tickets.py`
- `app/blueprints/main/account.py`
- `app/blueprints/bp_admin.py`

## Effective Permissions

User permissions are resolved with:

1. permissions inherited from roles
2. direct allows from `UserPermissionOverride`
3. direct denies from `UserPermissionOverride`

The public helpers on `User` are:

- `user.has_permission("permission.name")`
- `user.get_effective_permissions()`
- `user.get_permission_sources()`

These helpers are used throughout the UI and the protected routes.
