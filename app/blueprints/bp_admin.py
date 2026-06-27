from datetime import datetime, timedelta

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from app.decorators import permission_required
from app.models import (
    db,
    Message,
    MiscTicket,
    MiscTicketUser,
    Permission,
    ProblemTicket,
    ProblemTicketUser,
    RankEnum,
    Role,
    RoleEnum,
    TicketHistory,
    TrainingTicket,
    TrainingTicketUser,
    User,
    UserPermissionOverride,
)
from app.routes import get_date_time

bp_admin = Blueprint('admin', __name__)

LEGACY_ROLE_TO_STANDARD_ROLE_NAME = {
    RoleEnum.ADMIN.value: 'Admin',
    RoleEnum.TEACHER.value: 'Teacher',
    RoleEnum.MEMBER.value: 'User',
}

ADMIN_ACCESS_PERMISSIONS = {
    'admin.view',
    'admin.view_statistics',
    'admin.manage_settings',
}


def _to_iso(value):
    return value.isoformat() if value else None


def _serialize_role(role):
    return {
        'id': role.id,
        'name': role.name,
        'description': role.description,
        'is_system_role': role.is_system_role,
    }


def _serialize_permission(permission, source_values, is_effective):
    return {
        'id': permission.id,
        'name': permission.name,
        'description': permission.description,
        'sources': list(source_values),
        'effective': is_effective,
        'denied': 'user_deny' in source_values,
        'has_override': 'user_allow' in source_values or 'user_deny' in source_values,
    }


def _all_permission_names():
    return {permission.name for permission in Permission.query.all()}


def _role_has_all_permissions(role):
    return {permission.name for permission in role.permissions} == _all_permission_names()


def _resolve_role_payload_value(value):
    if value is None:
        return None

    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        return db.session.get(Role, int(value))

    role_name = str(value).strip()
    if not role_name:
        return None

    return Role.query.filter(db.func.lower(Role.name) == role_name.lower()).one_or_none()


def _effective_permissions_from_state(roles, overrides, active=True):
    if not active:
        return set()

    sources = {}
    for role in roles:
        if not role:
            continue

        role_source = f'role:{role.name}'
        for permission in role.permissions:
            if not permission or not permission.name:
                continue
            sources.setdefault(permission.name, set()).add(role_source)

    for override in overrides:
        permission = override.permission
        if not permission or not permission.name:
            continue
        sources.setdefault(permission.name, set()).add('user_allow' if override.allowed else 'user_deny')

    effective_permissions = set()
    for permission_name, source_values in sources.items():
        if 'user_deny' in source_values:
            continue
        if any(source.startswith('role:') for source in source_values) or 'user_allow' in source_values:
            effective_permissions.add(permission_name)

    return effective_permissions


def _has_admin_access_from_state(roles, overrides, active=True):
    return bool(_effective_permissions_from_state(roles, overrides, active) & ADMIN_ACCESS_PERMISSIONS)


def _has_admin_access(user):
    return _has_admin_access_from_state(user.roles, user.permission_overrides, user.active)


def _build_user_detail_payload(user):
    permissions = Permission.query.order_by(Permission.name).all()
    all_roles = Role.query.order_by(Role.name).all()

    if user is None:
        active_roles = []
        available_roles = all_roles
        permission_sources = {}
        effective_permissions = set()
        user_data = {
            'id': 0,
            'username': '',
            'first_name': '',
            'last_name': '',
            'full_name': '',
            'email': '',
            'role': '',
            'rank': '',
            'active': True,
            'active_from': None,
            'active_until': None,
            'last_login': None,
        }
    else:
        active_roles = sorted(user.roles, key=lambda role: role.name.lower())
        active_role_ids = {role.id for role in active_roles}
        available_roles = [role for role in all_roles if role.id not in active_role_ids]
        permission_sources = user.get_permission_sources()
        effective_permissions = user.get_effective_permissions()
        user_data = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': f'{user.first_name} {user.last_name}'.strip() or user.username,
            'email': user.email,
            'role': user.role.value if user.role else '',
            'rank': user.rank.value if user.rank else '',
            'active': user.active,
            'active_from': _to_iso(user.active_from),
            'active_until': _to_iso(user.active_until),
            'last_login': _to_iso(user.last_login),
        }

    permission_rows = []
    for permission in permissions:
        source_values = permission_sources.get(permission.name, [])
        permission_rows.append(
            _serialize_permission(permission, source_values, permission.name in effective_permissions)
        )

    return {
        'user': user_data,
        'active_roles': [_serialize_role(role) for role in active_roles],
        'available_roles': [_serialize_role(role) for role in available_roles],
        'permissions': permission_rows,
        'effective_permissions': sorted(effective_permissions),
        'permission_sources': permission_sources,
        'capabilities': {
            'can_manage_roles': current_user.has_permission('users.manage_roles'),
            'can_manage_permissions': current_user.has_permission('users.manage_permissions'),
            'can_create_users': current_user.has_permission('users.create'),
        },
    }


def _serialize_role_permission(permission, assigned=False):
    return {
        'id': permission.id,
        'name': permission.name,
        'description': permission.description,
        'assigned': assigned,
    }


def _build_role_detail_payload(role):
    all_permissions = Permission.query.order_by(Permission.name).all()

    if role is None:
        assigned_permissions = []
        available_permissions = all_permissions
        role_data = {
            'id': 0,
            'name': '',
            'description': '',
            'is_system_role': False,
            'permission_count': 0,
            'user_count': 0,
            'is_admin_role': False,
        }
    else:
        assigned_permissions = sorted(role.permissions, key=lambda permission: permission.name.lower())
        assigned_permission_ids = {permission.id for permission in assigned_permissions}
        available_permissions = [
            permission for permission in all_permissions if permission.id not in assigned_permission_ids
        ]
        role_data = {
            'id': role.id,
            'name': role.name,
            'description': role.description or '',
            'is_system_role': role.is_system_role,
            'permission_count': len(assigned_permissions),
            'user_count': len(role.users),
            'is_admin_role': role.is_system_role and _role_has_all_permissions(role),
        }

    assigned_permission_ids = {permission.id for permission in assigned_permissions}

    return {
        'role': role_data,
        'assigned_permissions': [_serialize_role_permission(permission, True) for permission in assigned_permissions],
        'available_permissions': [
            _serialize_role_permission(permission, False) for permission in available_permissions
        ],
        'permissions': [
            _serialize_role_permission(permission, permission.id in assigned_permission_ids)
            for permission in all_permissions
        ],
        'capabilities': {
            'can_create': current_user.has_permission('roles.create'),
            'can_edit': current_user.has_permission('roles.edit'),
            'can_delete': current_user.has_permission('roles.delete'),
            'can_assign_permissions': current_user.has_permission('roles.assign_permissions'),
        },
    }


@bp_admin.route('/admin/panel')
@permission_required('admin.view_statistics')
def admin_panel():
    six_months_ago = datetime.now() - timedelta(days=6 * 30)
    total_tickets = (
        db.session.query(ProblemTicket).filter(ProblemTicket.created_at >= six_months_ago).count()
        + db.session.query(TrainingTicket).filter(TrainingTicket.created_at >= six_months_ago).count()
        + db.session.query(MiscTicket).filter(MiscTicket.created_at >= six_months_ago).count()
    )
    solved_tickets = (
        db.session.query(ProblemTicket)
        .filter(ProblemTicket.created_at >= six_months_ago, ProblemTicket.status_id == 4)
        .count()
        + db.session.query(TrainingTicket)
        .filter(TrainingTicket.created_at >= six_months_ago, TrainingTicket.status_id == 4)
        .count()
        + db.session.query(MiscTicket)
        .filter(MiscTicket.created_at >= six_months_ago, MiscTicket.status_id == 4)
        .count()
    )

    problem_ticket_count = db.session.query(
        ProblemTicketUser.user_id,
        db.func.count(ProblemTicketUser.problem_ticket_id).label('problem_count'),
    ).join(ProblemTicket, ProblemTicket.id == ProblemTicketUser.problem_ticket_id).filter(
        ProblemTicket.status_id == 4
    ).group_by(ProblemTicketUser.user_id).subquery()

    training_ticket_count = db.session.query(
        TrainingTicketUser.user_id,
        db.func.count(TrainingTicketUser.training_ticket_id).label('training_count'),
    ).join(TrainingTicket, TrainingTicket.id == TrainingTicketUser.training_ticket_id).filter(
        TrainingTicket.status_id == 4
    ).group_by(TrainingTicketUser.user_id).subquery()

    misc_ticket_count = db.session.query(
        MiscTicketUser.user_id,
        db.func.count(MiscTicketUser.misc_ticket_id).label('misc_count'),
    ).join(MiscTicket, MiscTicket.id == MiscTicketUser.misc_ticket_id).filter(
        MiscTicket.status_id == 4
    ).group_by(MiscTicketUser.user_id).subquery()

    user_stats = db.session.query(
        User.first_name,
        User.last_name,
        db.func.coalesce(problem_ticket_count.c.problem_count, 0).label('problem_count'),
        db.func.coalesce(training_ticket_count.c.training_count, 0).label('training_count'),
        db.func.coalesce(misc_ticket_count.c.misc_count, 0).label('misc_count'),
    ).outerjoin(problem_ticket_count, problem_ticket_count.c.user_id == User.id).outerjoin(
        training_ticket_count, training_ticket_count.c.user_id == User.id
    ).outerjoin(
        misc_ticket_count, misc_ticket_count.c.user_id == User.id
    ).all()

    return render_template(
        'admin/admin_panel.html',
        total_tickets=total_tickets,
        solved_tickets=solved_tickets,
        user_stats=user_stats,
    )


@bp_admin.route('/members/administration')
@permission_required('users.view')
def members_administration():
    active_users = User.query.filter_by(active=True).order_by(User.last_name, User.first_name, User.username).all()
    inactive_users = User.query.filter_by(active=False).order_by(User.last_name, User.first_name, User.username).all()
    return render_template(
        'admin/members_administration.html',
        active_users=active_users,
        inactive_users=inactive_users,
        can_create_users=current_user.has_permission('users.create'),
    )


@bp_admin.route('/members/user/<int:user_id>', methods=['GET'])
@permission_required('users.view')
def user_detail(user_id):
    if user_id == 0:
        return jsonify(_build_user_detail_payload(None))

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify(_build_user_detail_payload(user))


@bp_admin.route('/members/user/<int:user_id>/roles', methods=['POST'])
@permission_required('users.manage_roles')
def update_user_roles(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True) or {}
    action = data.get('action')
    role_id = data.get('role_id')

    if action not in {'add', 'remove'}:
        return jsonify({'error': 'Invalid action'}), 400
    if role_id is None:
        return jsonify({'error': 'role_id is required'}), 400

    role = db.session.get(Role, int(role_id))
    if not role:
        return jsonify({'error': 'Role not found'}), 404

    self_admin_access = user.id == current_user.id and _has_admin_access(user)
    changed = False
    if action == 'add' and role not in user.roles:
        user.roles.append(role)
        changed = True
    elif action == 'remove' and role in user.roles:
        user.roles.remove(role)
        changed = True

    if changed and self_admin_access and not _has_admin_access(user):
        db.session.rollback()
        return jsonify({'error': 'You cannot remove your own admin access.'}), 400

    if changed:
        db.session.commit()

    payload = _build_user_detail_payload(user)
    payload['message'] = f"Role {role.name} {'added' if action == 'add' else 'removed'}."
    return jsonify(payload)


@bp_admin.route('/members/user/<int:user_id>/permissions', methods=['POST'])
@permission_required('users.manage_permissions')
def update_user_permissions(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True) or {}
    action = data.get('action')
    permission_id = data.get('permission_id')
    reason = data.get('reason') or None

    if action not in {'allow', 'deny', 'remove'}:
        return jsonify({'error': 'Invalid action'}), 400
    if permission_id is None:
        return jsonify({'error': 'permission_id is required'}), 400

    permission = db.session.get(Permission, int(permission_id))
    if not permission:
        return jsonify({'error': 'Permission not found'}), 404

    self_admin_access = user.id == current_user.id and _has_admin_access(user)
    existing_override = next(
        (override for override in user.permission_overrides if override.permission_id == permission.id),
        None,
    )

    changed = False
    if action in {'allow', 'deny'}:
        allowed = action == 'allow'
        if existing_override:
            if existing_override.allowed != allowed or existing_override.reason != reason:
                existing_override.allowed = allowed
                existing_override.reason = reason
                changed = True
        else:
            user.permission_overrides.append(
                UserPermissionOverride(permission=permission, allowed=allowed, reason=reason)
            )
            changed = True
    elif existing_override:
        db.session.delete(existing_override)
        changed = True

    if changed and self_admin_access and not _has_admin_access(user):
        db.session.rollback()
        return jsonify({'error': 'You cannot remove your own admin access.'}), 400

    if changed:
        db.session.commit()

    payload = _build_user_detail_payload(user)
    if action == 'allow':
        payload['message'] = f'Permission {permission.name} allowed.'
    elif action == 'deny':
        payload['message'] = f'Permission {permission.name} denied.'
    else:
        payload['message'] = f'Permission override for {permission.name} removed.'
    return jsonify(payload)


@bp_admin.route('/members/user', methods=['POST'])
@permission_required('users.create')
def create_user():
    data = request.get_json(silent=True) or {}

    username = str(data.get('username') or '').strip()
    first_name = str(data.get('first_name') or username).strip()
    last_name = str(data.get('last_name') or username).strip()
    email = str(data.get('email') or '').strip()

    if not username or not email:
        return jsonify({'error': 'username and email are required'}), 400

    duplicate_username = User.query.filter(db.func.lower(User.username) == username.lower()).one_or_none()
    if duplicate_username:
        return jsonify({'error': 'Username already exists'}), 400

    duplicate_email = User.query.filter(db.func.lower(User.email) == email.lower()).one_or_none()
    if duplicate_email:
        return jsonify({'error': 'Email already exists'}), 400

    role_value = data.get('role') or RoleEnum.MEMBER.value
    rank_value = data.get('rank') or RankEnum.KEIN.value

    try:
        role_enum = RoleEnum(role_value)
    except ValueError:
        role_enum = RoleEnum.MEMBER

    try:
        rank_enum = RankEnum(rank_value)
    except ValueError:
        rank_enum = RankEnum.KEIN

    new_user = User(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        role=role_enum,
        rank=rank_enum,
        active=True,
        active_from=datetime.now(),
    )

    password = data.get('password')
    if password:
        new_user.set_password(password)
    else:
        new_user.password_hash = ''

    db.session.add(new_user)

    requested_roles = data.get('role_ids') or data.get('roles') or []
    if isinstance(requested_roles, (int, str)):
        requested_roles = [requested_roles]

    if requested_roles:
        for role_value in requested_roles:
            role = _resolve_role_payload_value(role_value)
            if role and not any(existing_role.id == role.id for existing_role in new_user.roles):
                new_user.roles.append(role)
    else:
        standard_role_name = LEGACY_ROLE_TO_STANDARD_ROLE_NAME.get(role_enum.value)
        if standard_role_name:
            standard_role = Role.query.filter_by(name=standard_role_name).one_or_none()
            if standard_role:
                new_user.roles.append(standard_role)

    for permission_value in data.get('permission_ids') or data.get('privileges') or []:
        permission = None
        if isinstance(permission_value, int) or (
            isinstance(permission_value, str) and permission_value.isdigit()
        ):
            permission = db.session.get(Permission, int(permission_value))
        else:
            permission = Permission.query.filter_by(name=str(permission_value)).one_or_none()

        if permission and not any(override.permission_id == permission.id for override in new_user.permission_overrides):
            new_user.permission_overrides.append(
                UserPermissionOverride(permission=permission, allowed=True)
            )

    db.session.commit()

    payload = _build_user_detail_payload(new_user)
    payload['message'] = 'User created successfully.'
    return jsonify(payload), 201


@bp_admin.route('/roles/administration')
@permission_required('roles.view')
def roles_administration():
    roles = Role.query.order_by(Role.name).all()
    return render_template(
        'admin/roles_administration.html',
        roles=roles,
        can_create_role=current_user.has_permission('roles.create'),
        can_edit_role=current_user.has_permission('roles.edit'),
        can_delete_role=current_user.has_permission('roles.delete'),
        can_assign_permissions=current_user.has_permission('roles.assign_permissions'),
    )


@bp_admin.route('/roles/<int:role_id>', methods=['GET'])
@permission_required('roles.view')
def role_detail(role_id):
    if role_id == 0:
        return jsonify(_build_role_detail_payload(None))

    role = db.session.get(Role, role_id)
    if not role:
        return jsonify({'error': 'Role not found'}), 404

    return jsonify(_build_role_detail_payload(role))


@bp_admin.route('/roles', methods=['POST'])
@permission_required('roles.create')
def create_role():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()

    if not name:
        return jsonify({'error': 'Role name is required'}), 400

    existing_role = Role.query.filter(db.func.lower(Role.name) == name.lower()).one_or_none()
    if existing_role:
        return jsonify({'error': 'Role already exists'}), 400

    new_role = Role(name=name, description=description or None, is_system_role=False)
    db.session.add(new_role)
    db.session.commit()

    payload = _build_role_detail_payload(new_role)
    payload['message'] = 'Role created successfully.'
    return jsonify(payload), 201


@bp_admin.route('/roles/<int:role_id>/edit', methods=['POST'])
@permission_required('roles.edit')
def edit_role(role_id):
    role = db.session.get(Role, role_id)
    if not role:
        return jsonify({'error': 'Role not found'}), 404

    data = request.get_json(silent=True) or {}
    raw_name = data.get('name')
    raw_description = data.get('description')

    if raw_name is not None:
        new_name = raw_name.strip()
        if not new_name:
            return jsonify({'error': 'Role name is required'}), 400

        if role.is_system_role and new_name != role.name:
            return jsonify({'error': 'System roles cannot be renamed'}), 400

        if new_name.lower() != role.name.lower():
            duplicate = Role.query.filter(
                db.func.lower(Role.name) == new_name.lower(),
                Role.id != role.id,
            ).one_or_none()
            if duplicate:
                return jsonify({'error': 'Role already exists'}), 400
            role.name = new_name

    if raw_description is not None:
        role.description = raw_description.strip()

    db.session.commit()

    payload = _build_role_detail_payload(role)
    payload['message'] = 'Role updated successfully.'
    return jsonify(payload)


@bp_admin.route('/roles/<int:role_id>/delete', methods=['POST'])
@permission_required('roles.delete')
def delete_role(role_id):
    role = db.session.get(Role, role_id)
    if not role:
        return jsonify({'error': 'Role not found'}), 404

    if role.is_system_role:
        return jsonify({'error': 'System roles cannot be deleted'}), 400

    if current_user.is_authenticated and any(user.id == current_user.id for user in role.users):
        future_roles = [assigned_role for assigned_role in current_user.roles if assigned_role.id != role.id]
        if _has_admin_access(current_user) and not _has_admin_access_from_state(
            future_roles,
            current_user.permission_overrides,
            current_user.active,
        ):
            return jsonify({'error': 'You cannot remove your own admin access.'}), 400

    db.session.delete(role)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Role deleted successfully.', 'role_id': role_id})


@bp_admin.route('/roles/<int:role_id>/permissions', methods=['POST'])
@permission_required('roles.assign_permissions')
def update_role_permissions(role_id):
    role = db.session.get(Role, role_id)
    if not role:
        return jsonify({'error': 'Role not found'}), 404

    data = request.get_json(silent=True) or {}
    action = data.get('action')
    permission_id = data.get('permission_id')

    if action not in {'add', 'remove'}:
        return jsonify({'error': 'Invalid action'}), 400
    if permission_id is None:
        return jsonify({'error': 'permission_id is required'}), 400

    permission = db.session.get(Permission, int(permission_id))
    if not permission:
        return jsonify({'error': 'Permission not found'}), 404

    current_permission_ids = {existing_permission.id for existing_permission in role.permissions}
    self_admin_access = current_user.is_authenticated and any(user.id == current_user.id for user in role.users)

    if role.is_system_role and _role_has_all_permissions(role):
        future_permission_ids = set(current_permission_ids)
        if action == 'add':
            future_permission_ids.add(permission.id)
        else:
            future_permission_ids.discard(permission.id)

        all_permission_ids = {existing_permission.id for existing_permission in Permission.query.all()}
        if future_permission_ids != all_permission_ids:
            return jsonify({'error': 'Admin role must retain all permissions'}), 400

    changed = False
    if action == 'add' and permission not in role.permissions:
        role.permissions.append(permission)
        changed = True
    elif action == 'remove' and permission in role.permissions:
        role.permissions.remove(permission)
        changed = True

    if changed and self_admin_access and not _has_admin_access(current_user):
        db.session.rollback()
        return jsonify({'error': 'You cannot remove your own admin access.'}), 400

    if changed:
        db.session.commit()

    payload = _build_role_detail_payload(role)
    if action == 'add':
        payload['message'] = f'Permission {permission.name} added to role.'
    else:
        payload['message'] = f'Permission {permission.name} removed from role.'
    return jsonify(payload)


@bp_admin.route('/delete_message/<int:message_id>', methods=['POST'])
@permission_required('admin.manage_settings')
def delete_message(message_id):
    message = Message.query.get(message_id)
    if message:
        message.content = f'This Post was deleted by the Admin on {get_date_time()}'
        message.deleted = True
        db.session.commit()
        current_app.logger.info(f'Message deleted: {message_id}')
        return jsonify({'success': True})

    current_app.logger.error(f'Message not found: {message_id}')
    return jsonify({'error': 'Message not found'}), 404


@bp_admin.route('/ticket/<int:ticket_id>/delete', methods=['POST'])
@permission_required('tickets.delete')
def delete_ticket(ticket_id):
    ticket_type = request.form.get('ticket_type')
    if ticket_type == 'problem':
        ticket = ProblemTicket.query.get(ticket_id)
        ProblemTicketUser.query.filter_by(problem_ticket_id=ticket_id).delete()
    elif ticket_type == 'training':
        ticket = TrainingTicket.query.get(ticket_id)
        TrainingTicketUser.query.filter_by(training_ticket_id=ticket_id).delete()
    elif ticket_type == 'misc':
        ticket = MiscTicket.query.get(ticket_id)
        MiscTicketUser.query.filter_by(misc_ticket_id=ticket_id).delete()
    else:
        current_app.logger.error(f'Invalid ticket type: {ticket_type}')
        flash('Invalid ticket type.', 'danger')
        return redirect(url_for('main.ticket_verwaltung'))

    if ticket:
        db.session.delete(ticket)
        TicketHistory.query.filter_by(ticket_id=ticket_id, ticket_type=ticket_type).delete()
        db.session.commit()
        flash('Ticket deleted successfully.', 'success')
    else:
        current_app.logger.error(f'Ticket not found: {ticket_id}, {ticket_type}')
        flash('Ticket not found.', 'danger')

    return redirect(url_for('main.ticket_verwaltung'))
