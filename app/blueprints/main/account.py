import os
from urllib.parse import unquote

from PIL import Image
from flask import abort, current_app, flash, redirect, render_template, send_from_directory, url_for
from flask_login import current_user, login_required, logout_user
from werkzeug.utils import secure_filename

import app.routes as legacy_routes
from app.decorators import permission_required
from app.forms import EditProfileForm
from app.models import db

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

        upload_folder = os.path.join(current_app.root_path, current_app.config['USER_PROFILES'])
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        upload_folder_real = os.path.realpath(upload_folder)

        if form.profile_image.data:
            original_filename = secure_filename(form.profile_image.data.filename)
            safe_first_name = secure_filename(current_user.first_name)
            safe_last_name = secure_filename(current_user.last_name)
            new_filename = f'{safe_first_name}_{safe_last_name}{os.path.splitext(original_filename)[1]}'
            new_filename = new_filename.replace(' ', '_')

            full_path = os.path.normpath(os.path.join(upload_folder, new_filename))
            full_path_real = os.path.realpath(full_path)
            if os.path.commonpath([upload_folder_real, full_path_real]) != upload_folder_real:
                current_app.logger.error('Invalid profile image upload path')
                flash('Error saving profile image due to invalid file path.', 'danger')
                return redirect(url_for('main.profile'))

            try:
                form.profile_image.data.save(full_path)
            except Exception as exc:
                current_app.logger.error(f'Error saving profile image: {exc}')
                flash('Error saving profile image.', 'danger')
                return redirect(url_for('main.profile'))

            try:
                with Image.open(full_path) as img:
                    img.thumbnail((800, 800))
                    img.save(full_path)
            except Exception as exc:
                current_app.logger.error(f'Error processing image: {exc}')
                flash('Error processing profile image.', 'danger')
                return redirect(url_for('main.profile'))

            current_user.profile_picture = new_filename

        if form.delete_image.data:
            first_name = secure_filename(current_user.first_name)
            last_name = secure_filename(current_user.last_name)

            first_name_decoded = unquote(first_name).replace('_', ' ').strip()
            last_name_decoded = unquote(last_name).replace('_', ' ').strip()
            full_name = f'{first_name_decoded} {last_name_decoded}'
            current_full_name = f'{current_user.first_name.strip()} {current_user.last_name.strip()}'

            if full_name != current_full_name:
                flash('You are not allowed to access this profile picture.', 'danger')
                current_app.logger.warning(f'Unauthorized profile image access attempt by user_id={current_user.id}')
                return redirect(url_for('main.profile'))

            safe_first = secure_filename(current_user.first_name)
            safe_last = secure_filename(current_user.last_name)
            upload_folder = os.path.join(current_app.root_path, current_app.config['USER_PROFILES'])
            upload_folder_real = os.path.realpath(upload_folder)

            photo_filename = None
            for ext in ['.png', '.jpg', '.jpeg']:
                filename = f'{safe_first}_{safe_last}{ext}'
                file_path = os.path.normpath(os.path.join(upload_folder, filename))
                file_path_real = os.path.realpath(file_path)
                if os.path.exists(file_path_real):
                    photo_filename = filename
                    break

            if not photo_filename:
                flash('Profile picture not found.', 'danger')
                current_app.logger.info('Profile picture not found')
                return redirect(url_for('main.profile'))

            if os.path.commonpath([upload_folder_real, file_path_real]) != upload_folder_real:
                flash('Invalid file path.', 'danger')
                current_app.logger.warning(f'Invalid profile image path access attempt by user_id={current_user.id}')
                return redirect(url_for('main.profile'))

            current_app.logger.info('Profile picture found, deleting the file.')
            os.remove(file_path_real)
            return redirect(url_for('main.profile'))

        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('main.profile'))

    return render_template(
        'pages/profile.html',
        form=form,
        assigned_roles=assigned_roles,
    )


@bp_main.route('/profile_picture/<first_name>_<last_name>')
@permission_required('profile.view')
def profile_picture(first_name, last_name):
    first_name_decoded = unquote(first_name).replace('_', ' ').strip()
    last_name_decoded = unquote(last_name).replace('_', ' ').strip()
    full_name = f'{first_name_decoded} {last_name_decoded}'
    current_full_name = f'{current_user.first_name.strip()} {current_user.last_name.strip()}'

    if full_name != current_full_name:
        flash('You are not allowed to access this profile picture.', 'danger')
        current_app.logger.warning(f'Unauthorized profile image access attempt by user_id={current_user.id}')
        return redirect(url_for('main.profile'))

    photo_filename = getattr(current_user, 'photo', None)
    if not photo_filename:
        safe_first = secure_filename(current_user.first_name)
        safe_last = secure_filename(current_user.last_name)
        for ext in ['.png', '.jpg', '.jpeg']:
            photo_filename = f'{safe_first}_{safe_last}{ext}'
            file_path = os.path.join(current_app.root_path, current_app.config['USER_PROFILES'], photo_filename)
            if os.path.exists(file_path):
                break
        else:
            photo_filename = None

    if not photo_filename:
        current_app.logger.info('No photo stored in DB; using default profile image.')
        return send_from_directory(current_app.static_folder, 'images/default_profile.png')

    upload_folder = os.path.join(current_app.root_path, current_app.config['USER_PROFILES'])
    upload_folder_real = os.path.realpath(upload_folder)
    file_path = os.path.normpath(os.path.join(upload_folder, photo_filename))
    file_path_real = os.path.realpath(file_path)

    if os.path.commonpath([upload_folder_real, file_path_real]) != upload_folder_real:
        flash('Invalid file path.', 'danger')
        current_app.logger.warning(f'Invalid profile image path access attempt by user_id={current_user.id}')
        return redirect(url_for('main.profile'))

    if os.path.exists(file_path_real):
        current_app.logger.info('Profile picture found, serving the file.')
        return send_from_directory(upload_folder_real, photo_filename)

    current_app.logger.info('Profile picture not found, serving default image.')
    return send_from_directory(current_app.static_folder, 'images/default_profile.png')


@bp_main.route('/send_password_reset_email', methods=['POST'])
@permission_required('profile.edit')
def send_password_reset_email():
    """Send a password reset email to the current user."""
    user = current_user
    if user:
        legacy_routes.send_reset_email(user)
        flash('Password reset instructions have been sent to your email.', 'info')
    else:
        flash('User not found.', 'danger')
    return redirect(url_for('main.profile'))

