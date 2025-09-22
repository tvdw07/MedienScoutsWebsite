import os
from datetime import datetime, timedelta

import re
import bleach
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from app.models import db, ProblemTicket, TrainingTicket, MiscTicket, ProblemTicketUser, TrainingTicketUser, \
    MiscTicketUser, User, RoleEnum, RankEnum, Message, TicketHistory, Privilege, UserPrivilege
from app.decorators import admin_required
from app.routes import get_date_time
from email_tools import inform_admin
import traceback

bp_admin = Blueprint('admin', __name__)


@bp_admin.route('/admin/panel')
@login_required
@admin_required
def admin_panel():
    # Calculate statistics
    six_months_ago = datetime.now() - timedelta(days=6 * 30)
    total_tickets = (
            db.session.query(ProblemTicket).filter(ProblemTicket.created_at >= six_months_ago).count() +
            db.session.query(TrainingTicket).filter(TrainingTicket.created_at >= six_months_ago).count() +
            db.session.query(MiscTicket).filter(MiscTicket.created_at >= six_months_ago).count()
    )
    solved_tickets = (
            db.session.query(ProblemTicket).filter(ProblemTicket.created_at >= six_months_ago,
                                                   ProblemTicket.status_id == 4).count() +
            db.session.query(TrainingTicket).filter(TrainingTicket.created_at >= six_months_ago,
                                                    TrainingTicket.status_id == 4).count() +
            db.session.query(MiscTicket).filter(MiscTicket.created_at >= six_months_ago,
                                                MiscTicket.status_id == 4).count()
    )

    # Aliases for subqueries
    problem_ticket_count = db.session.query(
        ProblemTicketUser.user_id,
        db.func.count(ProblemTicketUser.problem_ticket_id).label('problem_count')
    ).join(ProblemTicket, ProblemTicket.id == ProblemTicketUser.problem_ticket_id).filter(
        ProblemTicket.status_id == 4
    ).group_by(ProblemTicketUser.user_id).subquery()

    training_ticket_count = db.session.query(
        TrainingTicketUser.user_id,
        db.func.count(TrainingTicketUser.training_ticket_id).label('training_count')
    ).join(TrainingTicket, TrainingTicket.id == TrainingTicketUser.training_ticket_id).filter(
        TrainingTicket.status_id == 4
    ).group_by(TrainingTicketUser.user_id).subquery()

    misc_ticket_count = db.session.query(
        MiscTicketUser.user_id,
        db.func.count(MiscTicketUser.misc_ticket_id).label('misc_count')
    ).join(MiscTicket, MiscTicket.id == MiscTicketUser.misc_ticket_id).filter(
        MiscTicket.status_id == 4
    ).group_by(MiscTicketUser.user_id).subquery()

    # User statistics
    user_stats = db.session.query(
        User.first_name,
        User.last_name,
        db.func.coalesce(problem_ticket_count.c.problem_count, 0).label('problem_count'),
        db.func.coalesce(training_ticket_count.c.training_count, 0).label('training_count'),
        db.func.coalesce(misc_ticket_count.c.misc_count, 0).label('misc_count')
    ).outerjoin(problem_ticket_count, problem_ticket_count.c.user_id == User.id).outerjoin(
        training_ticket_count, training_ticket_count.c.user_id == User.id).outerjoin(
        misc_ticket_count, misc_ticket_count.c.user_id == User.id).all()

    return render_template('admin/admin_panel.html',
                           total_tickets=total_tickets,
                           solved_tickets=solved_tickets,
                           user_stats=user_stats)


@bp_admin.route('/admin/get_config')
@login_required
@admin_required
def get_config():
    # Calculate the project root (one directory above current_app.root_path)
    project_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
    config_path = os.path.join(project_root, 'config.ini')

    # Send Email to Admin when Config is updated
    current_app.logger.warning(f'Config accessed by {current_user.username}')
    inform_admin(
        headline='Config Accessed',
        message=f'Config accessed by {current_user.username} at {get_date_time()}. If you did not make this change please contact AKS IMMEDIATELY due to a potential security breach (config.ini accessed).',
    )

    try:
        with open(config_path, 'r') as f:
            content = f.read()
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        current_app.logger.error(f"Error reading config file: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': 'An internal error has occurred.'}), 500


@bp_admin.route('/admin/update_config', methods=['POST'])
@login_required
@admin_required
def update_config():
    project_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
    config_path = os.path.join(project_root, 'config.ini')
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    # Sanitize the content
    sanitized_content = bleach.clean(data['content'], tags=[], strip=True)

    # Remove any Python code
    python_code_pattern = re.compile(r'(?s)<\?python.*?\?>')
    sanitized_content = re.sub(python_code_pattern, '', sanitized_content)

    # Send Email to Admin when Config is updated
    current_app.logger.warning(f'Config updated by {current_user.username}')
    inform_admin(
        headline='Config Updated',
        message=f'Config updated by {current_user.username} at {get_date_time()}. If you did not make this change please contact AKS IMMEDIATELY',
    )

    try:
        with open(config_path, 'w') as f:
            f.write(sanitized_content)
        return jsonify({'success': True, 'message': 'Config updated successfully.'})
    except Exception as e:
        current_app.logger.error(f"Error updating config file: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': 'An internal error has occurred.'}), 500


@bp_admin.route('/members/administration', methods=['GET', 'POST'])
@login_required
@admin_required
def members_administration():
    if request.method == 'POST':
        if 'create_user' in request.form:
            new_user = User(
                username=request.form.get('new_username'),
                first_name=request.form.get('new_first_name'),
                last_name=request.form.get('new_last_name'),
                email=request.form.get('new_email'),
                role=request.form.get('new_role'),
                rank=request.form.get('new_rank'),
                active=True,
                active_from=datetime.now()
            )
            new_user.password_hash = ''  # Set no password for new user
            db.session.add(new_user)
            db.session.commit()
            current_app.logger.info(f'New user created: {new_user.username}')
            flash('New user created successfully.', 'success')
        else:
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user:
                if 'reset_password' in request.form:
                    user.password_hash = ''  # Reset password
                    current_app.logger.info(f'Password reset for user: {user.username}')
                    flash('Password has been reset successfully.', 'success')
                else:
                    user.username = request.form.get('username')
                    user.first_name = request.form.get('first_name')
                    user.last_name = request.form.get('last_name')
                    user.email = request.form.get('email')
                    user.role = request.form.get('role')
                    user.rank = request.form.get('rank')
                    if 'set_inactive' in request.form:
                        user.active = False
                        user.active_until = datetime.now()
                        current_app.logger.info(f'User deactivated: {user.username}')
                    elif 'set_active' in request.form:
                        user.active = True
                        user.active_until = None
                        current_app.logger.info(f'User activated: {user.username}')
                    new_password = request.form.get('new_password')
                    if new_password:
                        user.set_password(new_password)
                        current_app.logger.info(f'Password changed for user: {user.username}')
                db.session.commit()
                current_app.logger.info(f'User updated: {user.username}')
                flash('User updated successfully.', 'success')
            else:
                current_app.logger.error(f'User not found: {user_id}')
                flash('User not found.', 'danger')
        return redirect(url_for('members_administration'))

    active_users = User.query.filter_by(active=True).all()
    inactive_users = User.query.filter_by(active=False).all()
    return render_template('admin/members_administration.html', active_users=active_users,
                           inactive_users=inactive_users, roles=RoleEnum, ranks=RankEnum)


@bp_admin.route('/members/user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def user_detail(user_id):
    if request.method == 'GET':
        # Load all privileges from the database
        privileges = Privilege.query.all()
        privileges_data = [{'id': p.id, 'name': p.name} for p in privileges]

        if user_id == 0:
            # New user: return an empty structure plus privileges
            return jsonify({
                'user': {
                    'id': 0,
                    'username': '',
                    'first_name': '',
                    'last_name': '',
                    'email': '',
                    'role': '',
                    'rank': '',
                    'active': True
                },
                'user_privileges': [],
                'all_privileges': privileges_data
            })

        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        user_data = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'role': user.role.value,
            'rank': user.rank.value if user.rank else '',
            'active': user.active,
        }
        user_privileges = [up.privilege_id for up in user.user_privileges]
        return jsonify({
            'user': user_data,
            'user_privileges': user_privileges,
            'all_privileges': privileges_data
        })

    elif request.method == 'POST':
        # Save updates for an existing user
        data = request.json
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        user.username = data.get('username')
        user.first_name = data.get('first_name')
        user.last_name = data.get('last_name')
        user.email = data.get('email')
        user.role = RoleEnum(data.get('role'))
        user.rank = RankEnum(data.get('rank'))
        user.active = data.get('active', True)

        new_password = data.get('new_password')
        if new_password:
            user.set_password(new_password)

        # Update privileges: remove existing ones and add new ones
        new_privs = data.get('privileges', [])
        UserPrivilege.query.filter_by(user_id=user.id).delete()
        for priv_id in new_privs:
            user_priv = UserPrivilege(user_id=user.id, privilege_id=priv_id)
            db.session.add(user_priv)

        db.session.commit()
        flash('User updated successfully.', 'success')
        return jsonify({'message': 'User updated successfully'})


@bp_admin.route('/members/user', methods=['POST'])
@login_required
@admin_required
def create_user():
    data = request.json
    new_user = User(
        username=data.get('username'),
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
        email=data.get('email'),
        role=RoleEnum(data.get('role')),
        rank=RankEnum(data.get('rank')),
        active=True,
        active_from=datetime.now()
    )
    password = data.get('password')
    if password:
        new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    # Assign privileges if provided
    for priv_id in data.get('privileges', []):
        user_priv = UserPrivilege(user_id=new_user.id, privilege_id=priv_id)
        db.session.add(user_priv)
    db.session.commit()

    return jsonify({'message': 'User created successfully', 'user_id': new_user.id})


@bp_admin.route('/delete_message/<int:message_id>', methods=['POST'])
@login_required
@admin_required
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


# app/routes.py
@bp_admin.route('/ticket/<int:ticket_id>/delete', methods=['POST'])
@login_required
@admin_required
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
        return redirect(url_for('ticket_verwaltung'))

    if ticket:
        db.session.delete(ticket)
        TicketHistory.query.filter_by(ticket_id=ticket_id, ticket_type=ticket_type).delete()
        db.session.commit()
        flash('Ticket deleted successfully.', 'success')
    else:
        current_app.logger.error(f'Ticket not found: {ticket_id}, {ticket_type}')
        flash('Ticket not found.', 'danger')

    return redirect(url_for('ticket_verwaltung'))
