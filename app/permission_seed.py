from app.models import (
    db,
    Permission,
    Role,
)


STANDARD_PERMISSIONS = (
    'tickets.view',
    'tickets.view_all',
    'tickets.create',
    'tickets.claim',
    'tickets.assign',
    'tickets.reply',
    'tickets.close',
    'tickets.delete',
    'tickets.archive',
    'users.view',
    'users.create',
    'users.edit',
    'users.deactivate',
    'users.delete',
    'users.manage_roles',
    'users.manage_permissions',
    'roles.view',
    'roles.create',
    'roles.edit',
    'roles.delete',
    'roles.assign_permissions',
    'admin.view',
    'admin.view_statistics',
    'admin.manage_settings',
    'profile.view',
    'profile.edit',
)

STANDARD_ROLE_DEFINITIONS = {
    'Admin': {
        'description': 'Full system administration role',
        'is_system_role': True,
        'permissions': STANDARD_PERMISSIONS,
    },
    'Teacher': {
        'description': 'Staff role with ticket handling rights',
        'is_system_role': True,
        'permissions': (
            'tickets.view',
            'tickets.view_all',
            'tickets.create',
            'tickets.claim',
            'tickets.assign',
            'tickets.reply',
            'tickets.close',
            'tickets.archive',
            'profile.view',
            'profile.edit',
        ),
    },
    'MediaScout': {
        'description': 'Support role with ticket handling rights',
        'is_system_role': True,
        'permissions': (
            'tickets.view',
            'tickets.view_all',
            'tickets.create',
            'tickets.claim',
            'tickets.reply',
            'tickets.close',
            'profile.view',
            'profile.edit',
        ),
    },
    'User': {
        'description': 'Standard user role',
        'is_system_role': True,
        'permissions': (
            'profile.view',
            'profile.edit',
        ),
    },
}

def seed_permissions_and_roles(session=None, commit=True):
    session = session or db.session

    permissions_by_name = {}
    for permission_name in STANDARD_PERMISSIONS:
        permission = session.query(Permission).filter_by(name=permission_name).one_or_none()
        if permission is None:
            permission = Permission(name=permission_name)
            session.add(permission)
        permissions_by_name[permission_name] = permission

    session.flush()

    roles_by_name = {}
    for role_name, definition in STANDARD_ROLE_DEFINITIONS.items():
        role = session.query(Role).filter_by(name=role_name).one_or_none()
        if role is None:
            role = Role(
                name=role_name,
                description=definition['description'],
                is_system_role=definition['is_system_role'],
            )
            session.add(role)
        else:
            role.description = definition['description']
            role.is_system_role = definition['is_system_role']
        roles_by_name[role_name] = role

    session.flush()

    for role_name, definition in STANDARD_ROLE_DEFINITIONS.items():
        role = roles_by_name[role_name]
        existing_permission_names = {permission.name for permission in role.permissions}
        for permission_name in definition['permissions']:
            if permission_name in existing_permission_names:
                continue
            role.permissions.append(permissions_by_name[permission_name])
            existing_permission_names.add(permission_name)

    if commit:
        session.commit()
