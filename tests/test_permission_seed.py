from app.models import Permission, Role, RoleEnum, RolePermission, User, UserRole, db
from app.permission_seed import (
    LEGACY_ROLE_TO_STANDARD_ROLE,
    STANDARD_PERMISSIONS,
    STANDARD_ROLE_DEFINITIONS,
    seed_permissions_and_roles,
)


def test_all_expected_permissions_are_seeded(app):
    seed_permissions_and_roles()

    stored_permissions = {permission.name for permission in Permission.query.order_by(Permission.name).all()}
    assert stored_permissions == set(STANDARD_PERMISSIONS)


def test_admin_role_receives_all_permissions(app):
    seed_permissions_and_roles()

    admin_role = Role.query.filter_by(name='Admin').one()
    assert {permission.name for permission in admin_role.permissions} == set(STANDARD_PERMISSIONS)


def test_mediascout_receives_no_admin_permissions(app):
    seed_permissions_and_roles()

    mediascout_role = Role.query.filter_by(name='MediaScout').one()
    mediascout_permissions = {permission.name for permission in mediascout_role.permissions}

    assert 'admin.view' not in mediascout_permissions
    assert 'admin.view_statistics' not in mediascout_permissions
    assert 'admin.manage_settings' not in mediascout_permissions


def test_existing_admin_users_are_backfilled_and_seed_is_idempotent(app):
    admin_user = User(
        username='legacy-admin',
        email='legacy-admin@example.com',
        first_name='Legacy',
        last_name='Admin',
        role=RoleEnum.ADMIN,
    )
    teacher_user = User(
        username='legacy-teacher',
        email='legacy-teacher@example.com',
        first_name='Legacy',
        last_name='Teacher',
        role=RoleEnum.TEACHER,
    )
    member_user = User(
        username='legacy-member',
        email='legacy-member@example.com',
        first_name='Legacy',
        last_name='Member',
        role=RoleEnum.MEMBER,
    )
    db.session.add_all([admin_user, teacher_user, member_user])
    db.session.commit()

    seed_permissions_and_roles()
    first_counts = {
        'permissions': Permission.query.count(),
        'roles': Role.query.count(),
        'role_permissions': RolePermission.query.count(),
        'user_roles': UserRole.query.count(),
    }

    seed_permissions_and_roles()
    second_counts = {
        'permissions': Permission.query.count(),
        'roles': Role.query.count(),
        'role_permissions': RolePermission.query.count(),
        'user_roles': UserRole.query.count(),
    }

    assert first_counts == second_counts
    assert first_counts['permissions'] == len(STANDARD_PERMISSIONS)
    assert first_counts['roles'] == len(STANDARD_ROLE_DEFINITIONS)
    assert first_counts['role_permissions'] == sum(
        len(definition['permissions']) for definition in STANDARD_ROLE_DEFINITIONS.values()
    )
    assert first_counts['user_roles'] == len(LEGACY_ROLE_TO_STANDARD_ROLE)

    stored_admin = db.session.get(User, admin_user.id)
    stored_teacher = db.session.get(User, teacher_user.id)
    stored_member = db.session.get(User, member_user.id)
    assert stored_admin is not None
    assert stored_teacher is not None
    assert stored_member is not None
    assert {role.name for role in stored_admin.roles} == {'Admin'}
    assert {role.name for role in stored_teacher.roles} == {'Teacher'}
    assert {role.name for role in stored_member.roles} == {'User'}
    assert stored_admin.has_permission('admin.view') is True
    assert stored_admin.has_permission('admin.view_statistics') is True
    assert stored_admin.has_permission('admin.manage_settings') is True
    assert stored_admin.get_effective_permissions() == set(STANDARD_PERMISSIONS)
