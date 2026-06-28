import os

from flask import abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required, logout_user

from app.decorators import permission_required
from app.forms import EditProfileForm
from app.models import User, db
from email_tools import send_reset_email
from app.upload_utils import (
    PROFILE_PICTURE_FOLDER,
    UploadValidationError,
    delete_stored_upload,
    get_upload_folder,
    normalize_stored_filename,
    save_profile_picture,
)
from app.ticket_notifications import mark_ticket_assignment_notification_read

from . import bp_main


@bp_main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.home'))


@bp_main.route('/profile', methods=['GET', 'POST'])
@permission_required('profile.view')
def profile():
    form = EditProfileForm(obj=current_user)
    assigned_roles = sorted(current_user.roles, key=lambda role: role.name.lower())

    if form.validate_on_submit():
        if not current_user.has_permission('profile.edit'):
            abort(403)

        if form.delete_image.data:
            previous_picture = current_user.profile_picture
            current_user.profile_picture = None
            current_user.profile_picture_original_name = None
            try:
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                current_app.logger.error(f'Error while deleting profile picture: {exc}')
                flash('Profile picture could not be deleted.', 'danger')
                return redirect(url_for('main.profile'))
            delete_stored_upload(
                current_app.config.get('PROFILE_PICTURE_FOLDER', PROFILE_PICTURE_FOLDER),
                previous_picture,
            )
            flash('Profile picture deleted successfully.', 'success')
            return redirect(url_for('main.profile'))

        new_first_name = form.first_name.data
        new_last_name = form.last_name.data
        new_email = form.email.data
        previous_picture = current_user.profile_picture
        new_picture = None
        new_original_name = None

        if form.profile_image.data:
            try:
                new_picture, new_original_name = save_profile_picture(form.profile_image.data)
            except UploadValidationError as exc:
                current_app.logger.warning('Profile image upload rejected for user_id=%s: %s', current_user.id, exc)
                flash(exc.message, 'danger')
                if exc.status_code == 413:
                    abort(413)
                return render_template(
                    'pages/profile.html',
                    form=form,
                    assigned_roles=assigned_roles,
                ), exc.status_code

        current_user.first_name = new_first_name
        current_user.last_name = new_last_name
        current_user.email = new_email
        if new_picture is not None:
            current_user.profile_picture = new_picture
            current_user.profile_picture_original_name = new_original_name

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            if new_picture:
                delete_stored_upload(
                    current_app.config.get('PROFILE_PICTURE_FOLDER', PROFILE_PICTURE_FOLDER),
                    new_picture,
                )
            current_app.logger.error(f'Error while updating profile: {exc}')
            flash('Profile could not be updated.', 'danger')
            return redirect(url_for('main.profile'))

        if previous_picture and previous_picture != current_user.profile_picture:
            delete_stored_upload(
                current_app.config.get('PROFILE_PICTURE_FOLDER', PROFILE_PICTURE_FOLDER),
                previous_picture,
            )

        flash('Profile updated successfully.', 'success')
        return redirect(url_for('main.profile'))

    return render_template(
        'pages/profile.html',
        form=form,
        assigned_roles=assigned_roles,
    )


@bp_main.route('/profile_picture/<int:user_id>')
@login_required
def profile_picture(user_id):
    if current_user.id == user_id:
        if not current_user.has_permission('profile.view'):
            abort(403)
    elif not current_user.has_permission('users.view'):
        abort(403)

    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    photo_filename = normalize_stored_filename(user.profile_picture)
    if not photo_filename:
        current_app.logger.info('No profile picture stored; using default image.')
        return send_from_directory(current_app.static_folder, 'images/default_profile.png')

    upload_folder = get_upload_folder(current_app.config.get('PROFILE_PICTURE_FOLDER', PROFILE_PICTURE_FOLDER))
    file_path = os.path.join(upload_folder, photo_filename)

    if os.path.exists(file_path):
        current_app.logger.info('Profile picture found, serving the file.')
        return send_from_directory(upload_folder, photo_filename)

    current_app.logger.info('Profile picture not found, serving default image.')
    return send_from_directory(current_app.static_folder, 'images/default_profile.png')


@bp_main.route('/send_password_reset_email', methods=['POST'])
@permission_required('profile.edit')
def send_password_reset_email():
    """Send a password reset email to the current user."""
    user = current_user
    if user:
        send_reset_email(user)
        flash('Password reset instructions have been sent to your email.', 'info')
    else:
        flash('User not found.', 'danger')
    return redirect(url_for('main.profile'))


@bp_main.route('/ticket-assignment-notifications/<int:notification_id>/dismiss', methods=['POST'])
@login_required
def dismiss_ticket_assignment_notification(notification_id):
    notification = mark_ticket_assignment_notification_read(notification_id, current_user.id)
    if not notification:
        flash('Notification not found.', 'danger')
        return redirect(request.referrer or url_for('main.home'))

    db.session.commit()
    return redirect(request.referrer or url_for('main.home'))
