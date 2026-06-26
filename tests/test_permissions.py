from app.models import (
    db,
    Permission,
    Role,
    User,
    UserPermissionOverride,
    RoleEnum,
)


def test_permission_can_be_created(app):
    permission = Permission(name='tickets.view', description='View tickets')
    db.session.add(permission)
    db.session.commit()

    stored = db.session.get(Permission, permission.id)
    assert stored is not None
    assert stored.name == 'tickets.view'
    assert stored.description == 'View tickets'


def test_role_can_contain_permissions(app):
    role = Role(name='support', description='Support team')
    permission = Permission(name='tickets.view', description='View tickets')

    role.permissions.append(permission)
    db.session.add_all([role, permission])
    db.session.commit()

    stored_role = db.session.get(Role, role.id)
    assert stored_role is not None
    assert {perm.name for perm in stored_role.permissions} == {'tickets.view'}
    assert len(stored_role.role_permissions) == 1
    assert stored_role.role_permissions[0].permission_id == permission.id


def test_user_can_have_multiple_roles(app):
    user = User(
        username='member-1',
        email='member-1@example.com',
        first_name='Member',
        last_name='One',
        role=RoleEnum.MEMBER,
    )
    role_editor = Role(name='editor', description='Editor role')
    role_moderator = Role(name='moderator', description='Moderator role')

    user.roles.extend([role_editor, role_moderator])
    db.session.add_all([user, role_editor, role_moderator])
    db.session.commit()

    stored_user = db.session.get(User, user.id)
    assert stored_user is not None
    assert {role.name for role in stored_user.roles} == {'editor', 'moderator'}
    assert len(stored_user.user_roles) == 2


def test_user_permission_override_can_allow_and_deny(app):
    user = User(
        username='member-2',
        email='member-2@example.com',
        first_name='Member',
        last_name='Two',
        role=RoleEnum.MEMBER,
    )
    allow_permission = Permission(name='tickets.view', description='View tickets')
    deny_permission = Permission(name='tickets.delete', description='Delete tickets')

    allow_override = UserPermissionOverride(permission=allow_permission, allowed=True)
    deny_override = UserPermissionOverride(
        permission=deny_permission,
        allowed=False,
        reason='Restricted for this account',
    )

    user.permission_overrides.extend([allow_override, deny_override])
    db.session.add_all([user, allow_permission, deny_permission])
    db.session.commit()

    stored_user = db.session.get(User, user.id)
    assert stored_user is not None
    assert stored_user.has_permission('tickets.view') is True
    assert stored_user.has_permission('tickets.delete') is False

    overrides = {override.permission.name: override for override in stored_user.permission_overrides}
    assert overrides['tickets.view'].allowed is True
    assert overrides['tickets.delete'].allowed is False
    assert overrides['tickets.delete'].reason == 'Restricted for this account'
