from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required
from app import db, app, ProblemTicket, TrainingTicket, MiscTicket, ProblemTicketUser, TrainingTicketUser, \
    MiscTicketUser, User
from app.decorators import admin_required
from app.models import RoleEnum, RankEnum, Message, TicketHistory
from app.routes import get_date_time

bp_admin = Blueprint('admin', __name__)


@app.route('/admin/panel')
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


@app.route('/members/administration', methods=['GET', 'POST'])
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
            app.logger.info(f'New user created: {new_user.username}')
            flash('New user created successfully.', 'success')
        else:
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user:
                if 'reset_password' in request.form:
                    user.password_hash = ''  # Reset password
                    app.logger.info(f'Password reset for user: {user.username}')
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
                        app.logger.info(f'User deactivated: {user.username}')
                    elif 'set_active' in request.form:
                        user.active = True
                        user.active_until = None
                        app.logger.info(f'User activated: {user.username}')
                    new_password = request.form.get('new_password')
                    if new_password:
                        user.set_password(new_password)
                        app.logger.info(f'Password changed for user: {user.username}')
                db.session.commit()
                app.logger.info(f'User updated: {user.username}')
                flash('User updated successfully.', 'success')
            else:
                app.logger.error(f'User not found: {user_id}')
                flash('User not found.', 'danger')
        return redirect(url_for('members_administration'))

    active_users = User.query.filter_by(active=True).all()
    inactive_users = User.query.filter_by(active=False).all()
    return render_template('admin/members_administration.html', active_users=active_users,
                           inactive_users=inactive_users, roles=RoleEnum, ranks=RankEnum)


@app.route('/delete_message/<int:message_id>', methods=['POST'])
@login_required
@admin_required
def delete_message(message_id):
    message = Message.query.get(message_id)
    if message:
        message.content = f'This Post was deleted by the Admin on {get_date_time()}'
        message.deleted = True
        db.session.commit()
        app.logger.info(f'Message deleted: {message_id}')
        return jsonify({'success': True})
    app.logger.error(f'Message not found: {message_id}')
    return jsonify({'error': 'Message not found'}), 404


# app/routes.py
@app.route('/ticket/<int:ticket_id>/delete', methods=['POST'])
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
        app.logger.error(f'Invalid ticket type: {ticket_type}')
        flash('Invalid ticket type.', 'danger')
        return redirect(url_for('ticket_verwaltung'))

    if ticket:
        db.session.delete(ticket)
        TicketHistory.query.filter_by(ticket_id=ticket_id, ticket_type=ticket_type).delete()
        db.session.commit()
        flash('Ticket deleted successfully.', 'success')
    else:
        app.logger.error(f'Ticket not found: {ticket_id}, {ticket_type}')
        flash('Ticket not found.', 'danger')

    return redirect(url_for('ticket_verwaltung'))
