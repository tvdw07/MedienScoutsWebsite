from datetime import datetime
from flask import Blueprint, session, request, flash, redirect, url_for, render_template, current_app
from flask_login import login_user
from app import app, User, db
from app.forms import LoginForm, PasswordResetForm, PasswordResetRequestForm
from app.routes import is_safe_url
from email_tools import send_reset_email

bp_auth = Blueprint('auth', __name__)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    next_page = session.get('next') or request.args.get('next')

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if user.password_hash is None or user.password_hash == '':
                send_reset_email(user)
                flash('Your password is not set. A password reset email has been sent to you.', 'info')
                return redirect(url_for('login'))
            if user.check_password(form.password.data):
                if not user.active:
                    app.logger.warning(f'Inactive user tried to log in: {user.username}')
                    flash('Your account is inactive. Please contact the administrator.', 'danger')
                    return redirect(url_for('login'))
                login_user(user)
                user.last_login = datetime.now()  # Update last_login
                db.session.commit()
                flash('Logged in successfully.', 'success')
                app.logger.info(f'User logged in: {user.username}')

                if next_page:
                    from urllib.parse import urlparse
                    next_page = next_page.replace('\\', '')
                    if not urlparse(next_page).netloc and not urlparse(next_page).scheme:
                        print(f'Next Page: {next_page}')
                        session.pop('next', None)  # Clear the 'next' after login
                        return redirect(next_page)
                    else:
                        return redirect(url_for('home'))
                else:
                    return redirect(url_for('home'))
        flash('Invalid username or password', 'danger')
        app.logger.warning(f'Invalid login attempt for user: {form.username.data}')

    return render_template('auth/login.html', form=form)


@app.route('/request_password_reset', methods=['GET', 'POST'])
def request_password_reset():
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_reset_email(user)
        flash('Password reset instructions have been sent to your email.', 'info')
        return redirect(url_for('login'))
    return render_template('auth/request_password_reset.html', form=form)


def verify_reset_token(token, user_id):
    return User.validate_reset_password_token(token, user_id)


@app.route('/reset_password/<token>/<int:user_id>', methods=['GET', 'POST'])
def reset_password(token, user_id):
    user = User.query.get(user_id)
    if not user or not user.validate_reset_password_token(token, user_id):
        flash('The reset link is invalid or has expired.', 'danger')
        app.logger.warning(f'Invalid or expired reset link: {token}')
        return redirect(url_for('request_password_reset'))

    form = PasswordResetForm()
    password_policy = current_app.config['PASSWORD_POLICY']

    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset!', 'success')
        app.logger.info(f'Password reset for user: {user.username}')
        return redirect(url_for('login'))
    elif request.method == 'POST':
        flash('Password requirements are not met. Please ensure your password meets all the criteria.', 'danger')
        app.logger.warning(f'Password reset failed for user: {user.username}')

    return render_template('reset_password.html', form=form, token=token, user_id=user_id,
                           password_policy=password_policy)
