from app.models import Permission, Role, RoleEnum, RolePermission, User, UserRole, db
from app.permission_seed import STANDARD_PERMISSIONS, STANDARD_ROLE_DEFINITIONS, seed_permissions_and_roles


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


def test_seed_is_idempotent_without_backfilling_users(app):
    admin_user = User(
        username='account-admin',
        email='account-admin@example.com',
        first_name='Account',
        last_name='Admin',
        role=RoleEnum.ADMIN,
    )
    teacher_user = User(
        username='account-teacher',
        email='account-teacher@example.com',
        first_name='Account',
        last_name='Teacher',
        role=RoleEnum.TEACHER,
    )
    member_user = User(
        username='account-member',
        email='account-member@example.com',
        first_name='Account',
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
    assert first_counts['user_roles'] == 0

    stored_admin = db.session.get(User, admin_user.id)
    stored_teacher = db.session.get(User, teacher_user.id)
    stored_member = db.session.get(User, member_user.id)
    assert stored_admin is not None
    assert stored_teacher is not None
    assert stored_member is not None
    assert stored_admin.roles == []
    assert stored_teacher.roles == []
    assert stored_member.roles == []
    assert stored_admin.has_permission('admin.view') is False
    assert stored_admin.has_permission('admin.view_statistics') is False
    assert stored_admin.has_permission('admin.manage_settings') is False
