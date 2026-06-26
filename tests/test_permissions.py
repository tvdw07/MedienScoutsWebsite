from app.models import db, Permission, Role, RoleEnum, User, UserPermissionOverride


def make_user(username, email, active=True):
    return User(
        username=username,
        email=email,
        first_name='Test',
        last_name='User',
        role=RoleEnum.MEMBER,
        active=active,
    )


def test_permission_can_be_created(app):
    permission = Permission(name='tickets.view', description='View tickets')
    db.session.add(permission)
    db.session.commit()

    stored = db.session.get(Permission, permission.id)
    assert stored is not None
    assert stored.name == 'tickets.view'
    assert stored.description == 'View tickets'


def test_permission_over_role_is_effective(app):
    user = make_user('role-user', 'role-user@example.com')
    role = Role(name='editor', description='Editor role')
    permission = Permission(name='tickets.view', description='View tickets')

    role.permissions.append(permission)
    user.roles.append(role)
    db.session.add_all([user, role, permission])
    db.session.commit()

    stored_user = db.session.get(User, user.id)
    assert stored_user is not None
    assert stored_user.has_permission('tickets.view') is True
    assert stored_user.get_effective_permissions() == {'tickets.view'}
    assert stored_user.get_permission_sources() == {'tickets.view': ['role:editor']}


def test_user_can_have_multiple_roles(app):
    user = make_user('multi-role-user', 'multi-role-user@example.com')
    role_editor = Role(name='editor', description='Editor role')
    role_moderator = Role(name='moderator', description='Moderator role')

    user.roles.extend([role_editor, role_moderator])
    db.session.add_all([user, role_editor, role_moderator])
    db.session.commit()

    stored_user = db.session.get(User, user.id)
    assert stored_user is not None
    assert {role.name for role in stored_user.roles} == {'editor', 'moderator'}
    assert len(stored_user.user_roles) == 2


def test_permission_directly_allowed_is_effective(app):
    user = make_user('allow-user', 'allow-user@example.com')
    permission = Permission(name='tickets.export', description='Export tickets')

    user.permission_overrides.append(
        UserPermissionOverride(permission=permission, allowed=True)
    )
    db.session.add_all([user, permission])
    db.session.commit()

    stored_user = db.session.get(User, user.id)
    assert stored_user is not None
    assert stored_user.has_permission('tickets.export') is True
    assert stored_user.get_effective_permissions() == {'tickets.export'}
    assert stored_user.get_permission_sources() == {'tickets.export': ['user_allow']}


def test_permission_directly_denied_is_removed(app):
    user = make_user('deny-user', 'deny-user@example.com')
    permission = Permission(name='tickets.archive', description='Archive tickets')

    user.permission_overrides.append(
        UserPermissionOverride(permission=permission, allowed=False, reason='Restricted')
    )
    db.session.add_all([user, permission])
    db.session.commit()

    stored_user = db.session.get(User, user.id)
    assert stored_user is not None
    assert stored_user.has_permission('tickets.archive') is False
    assert stored_user.get_effective_permissions() == set()
    assert stored_user.get_permission_sources() == {'tickets.archive': ['user_deny']}


def test_deny_overrides_role(app):
    user = make_user('override-user', 'override-user@example.com')
    role = Role(name='editor', description='Editor role')
    permission = Permission(name='tickets.delete', description='Delete tickets')

    role.permissions.append(permission)
    user.roles.append(role)
    user.permission_overrides.append(
        UserPermissionOverride(permission=permission, allowed=False, reason='Restricted')
    )
    db.session.add_all([user, role, permission])
    db.session.commit()

    stored_user = db.session.get(User, user.id)
    assert stored_user is not None
    assert stored_user.has_permission('tickets.delete') is False
    assert 'tickets.delete' not in stored_user.get_effective_permissions()
    assert stored_user.get_permission_sources() == {
        'tickets.delete': ['role:editor', 'user_deny']
    }


def test_inactive_user_has_no_permissions(app):
    user = make_user('inactive-user', 'inactive-user@example.com', active=False)
    role = Role(name='editor', description='Editor role')
    permission = Permission(name='tickets.view', description='View tickets')

    role.permissions.append(permission)
    user.roles.append(role)
    user.permission_overrides.append(
        UserPermissionOverride(permission=permission, allowed=True)
    )
    db.session.add_all([user, role, permission])
    db.session.commit()

    stored_user = db.session.get(User, user.id)
    assert stored_user is not None
    assert stored_user.has_permission('tickets.view') is False
    assert stored_user.get_effective_permissions() == set()
    assert stored_user.get_permission_sources() == {}


def test_unknown_permission_returns_false(app):
    user = make_user('unknown-user', 'unknown-user@example.com')
    role = Role(name='editor', description='Editor role')
    permission = Permission(name='tickets.view', description='View tickets')

    role.permissions.append(permission)
    user.roles.append(role)
    db.session.add_all([user, role, permission])
    db.session.commit()

    stored_user = db.session.get(User, user.id)
    assert stored_user is not None
    assert stored_user.has_permission('tickets.manage') is False
    assert 'tickets.manage' not in stored_user.get_effective_permissions()
