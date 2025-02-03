import os
from datetime import datetime
from urllib.parse import urlparse, urljoin, unquote
from PIL import Image
from flask import jsonify, session, current_app, send_from_directory
from flask_login import logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from app import app
from app.decorators import ticket_owner_required
from app.forms import MessageForm, EditProfileForm, \
    ChangePasswordForm
from app.models import Message, MiscTicket, TrainingTicket, ProblemTicket, ProblemTicketUser, \
    TrainingTicketUser, MiscTicketUser, TicketHistory
from email_tools import send_ticket_link, notify_admin, notify_client, notify_user_about_ticket_change, send_reset_email


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@app.before_request
def before_request():
    session.permanent = True

@app.route('/')
def home():
    member_count = User.query.filter_by(active=True).count()
    return render_template('home.html', member_count=member_count)


@app.route('/members')
def members():
    active_members = User.query.filter_by(active=True).all()  # Aktive Mitglieder abrufen
    inactive_members = User.query.filter_by(active=False).all()  # Inaktive Mitglieder abrufen
    return render_template('members.html', active_members=active_members, inactive_members=inactive_members)


@app.route('/ticketverwaltung')
@login_required
def ticket_verwaltung():
    # Fetch all open tickets
    open_problem_tickets = ProblemTicket.query.filter_by(status_id=1).all()
    open_training_tickets = TrainingTicket.query.filter_by(status_id=1).all()
    open_misc_tickets = MiscTicket.query.filter_by(status_id=1).all()

    # Add type attribute to each ticket
    for ticket in open_problem_tickets:
        ticket.type = 'problem'
    for ticket in open_training_tickets:
        ticket.type = 'training'
    for ticket in open_misc_tickets:
        ticket.type = 'misc'

    # Fetch all tickets claimed by the current user that are not closed (status_id != 4)
    my_problem_tickets = ProblemTicket.query.join(ProblemTicketUser).filter(
        ProblemTicketUser.user_id == current_user.id,
        ProblemTicket.status_id != 4
    ).all()
    my_training_tickets = TrainingTicket.query.join(TrainingTicketUser).filter(
        TrainingTicketUser.user_id == current_user.id,
        TrainingTicket.status_id != 4
    ).all()
    my_misc_tickets = MiscTicket.query.join(MiscTicketUser).filter(
        MiscTicketUser.user_id == current_user.id,
        MiscTicket.status_id != 4
    ).all()

    # Add type attribute to each claimed ticket
    for ticket in my_problem_tickets:
        ticket.type = 'problem'
    for ticket in my_training_tickets:
        ticket.type = 'training'
    for ticket in my_misc_tickets:
        ticket.type = 'misc'

    # Combine all claimed tickets
    my_tickets = my_problem_tickets + my_training_tickets + my_misc_tickets

    # Count total open tickets
    total_open_tickets = len(open_problem_tickets) + len(open_training_tickets) + len(open_misc_tickets)

    return render_template('ticketverwaltung.html',
                           open_problem_tickets=open_problem_tickets,
                           open_training_tickets=open_training_tickets,
                           open_misc_tickets=open_misc_tickets,
                           my_tickets=my_tickets,
                           total_open_tickets=total_open_tickets)


@app.route('/ticket/<string:ticket_type>/<int:ticket_id>/details')
@login_required
def ticket_details(ticket_type, ticket_id):
    if ticket_type == 'problem':
        ticket = ProblemTicket.query.get(ticket_id)
    elif ticket_type == 'training':
        ticket = TrainingTicket.query.get(ticket_id)
    elif ticket_type == 'misc':
        ticket = MiscTicket.query.get(ticket_id)
    else:
        flash('Invalid ticket type.', 'danger')
        return redirect(url_for('ticket_verwaltung'))

    if not ticket:
        flash('Ticket not found.', 'danger')
        return redirect(url_for('ticket_verwaltung'))

    ticket_history = TicketHistory.query.filter_by(ticket_type=ticket_type, ticket_id=ticket_id).order_by(
        TicketHistory.created_at).all()

    return render_template('ticket_details.html', ticket=ticket, ticket_type=ticket_type, ticket_history=ticket_history)


@app.route('/ticket/<int:ticket_id>/claim', methods=['POST'])
@login_required
def claim_ticket(ticket_id):
    user_id = request.form.get('user_id')
    ticket_type = request.form.get('ticket_type')

    try:
        if ticket_type == 'problem':
            ticket = ProblemTicket.query.get(ticket_id)
            ticket_user = ProblemTicketUser(ticket_user_id=None, problem_ticket_id=ticket_id, user_id=user_id)
        elif ticket_type == 'training':
            ticket = TrainingTicket.query.get(ticket_id)
            ticket_user = TrainingTicketUser(ticket_user_id=None, training_ticket_id=ticket_id, user_id=user_id)
        elif ticket_type == 'misc':
            ticket = MiscTicket.query.get(ticket_id)
            ticket_user = MiscTicketUser(ticket_user_id=None, misc_ticket_id=ticket_id, user_id=user_id)
        else:
            app.logger.error(f'Invalid ticket type: {ticket_type}')
            flash('Invalid ticket type.', 'danger')
            return redirect(url_for('ticket_verwaltung'))

        ticket.status_id = 2
        db.session.add(ticket_user)
        db.session.commit()
        flash('Ticket claimed successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error claiming ticket', 'danger')
        app.logger.error(f'Error claiming ticket: {e}')

    return redirect(url_for('ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))


@app.route('/ticket/<int:ticket_id>/request_help', methods=['POST'])
@login_required
@ticket_owner_required
def request_help(ticket_id):
    ticket_type = request.form.get('ticket_type')
    print(f'Ticket Type: {ticket_type}')
    if ticket_type == 'problem':
        ticket = ProblemTicket.query.get(ticket_id)
    elif ticket_type == 'training':
        ticket = TrainingTicket.query.get(ticket_id)
    elif ticket_type == 'misc':
        ticket = MiscTicket.query.get(ticket_id)
    else:
        flash('Invalid ticket type.', 'danger')
        return redirect(url_for('ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))

    notify_admin(ticket, ticket_type, 'Help is requested for the following ticket:')
    flash('Help request has been sent for ticket ID: {}'.format(ticket_id), 'info')
    return redirect(url_for('ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))


@app.route('/ticket/<int:ticket_id>/submit_response', methods=['POST'])
@login_required
@ticket_owner_required
def submit_response(ticket_id):
    response_message = request.form.get('response_message')
    ticket_type = request.form.get('ticket_type')
    if not ticket_type:
        flash('Ticket type is required.', 'danger')
        return redirect(url_for('ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))


    # Update the ticket status to 3
    if ticket_type == 'problem':
        ticket = ProblemTicket.query.get(ticket_id)
    elif ticket_type == 'training':
        ticket = TrainingTicket.query.get(ticket_id)
    elif ticket_type == 'misc':
        ticket = MiscTicket.query.get(ticket_id)

    if ticket.status_id == 4 or ticket.status_id == 1:
        flash('Ticket is already solved.', 'danger')
        return redirect(url_for('ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))

    # Log the ticket message
    author_type = 'MedienScout: ' + current_user.first_name + ' ' + current_user.last_name
    log_ticket_message(ticket_type, ticket_id, response_message, author_type)

    ticket.status_id = 3
    db.session.commit()

    notify_client(ticket, response_message)

    flash('Response has been submitted for ticket ID: {}'.format(ticket_id), 'info')
    return redirect(url_for('ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))


@app.route('/ticket/<int:ticket_id>/mark_solved', methods=['POST'])
@login_required
@ticket_owner_required
def mark_ticket_solved(ticket_id):
    print(f'Ticket ID: {ticket_id}')
    print("Trying to find ticket_type")
    ticket_type = request.form.get('ticket_type')
    print(f'Ticket Type: {ticket_type}')

    if ticket_type == 'problem':
        ticket = ProblemTicket.query.get(ticket_id)
    elif ticket_type == 'training':
        ticket = TrainingTicket.query.get(ticket_id)
    elif ticket_type == 'misc':
        ticket = MiscTicket.query.get(ticket_id)
    else:
        flash('Invalid ticket type.', 'danger')
        return redirect(url_for('ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))

    if ticket:
        ticket.status_id = 4
        db.session.commit()
        flash('Ticket marked as solved.', 'success')
    else:
        app.logger.error(f'Ticket not found: {ticket_id}, {ticket_type}')
        flash('Ticket not found.', 'danger')

    return redirect(url_for('ticket_details', ticket_id=ticket_id, ticket_type=ticket_type))




@app.route('/send_ticket', methods=['GET', 'POST'])
def send_ticket():
    if request.method == 'POST':
        ticket_type = request.form.get('ticket_type')
        print(f'Ticket type: {ticket_type}')


        if ticket_type == 'problem':
            if not request.form.get('first_name') or not request.form.get('last_name') or not request.form.get('email_problem') or not request.form.get('class') or not request.form.get('problem_description') or not request.form.getlist('steps'):
                flash('Please fill in all the required fields.', 'danger')
                return redirect(request.url)
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            email = request.form.get('email_problem')
            print(f'First Name: {first_name}, Last Name: {last_name}, Email: {email}')
            class_stufe = request.form.get('class')
            serial_number = request.form.get('serial_number')
            problem_description = request.form.get('problem_description')
            steps = request.form.getlist('steps')
            steps_taken = ", ".join(steps)
            photo = request.files.get('photo')
            app.logger.info("Ticket submitted: %s, %s, %s, %s, %s, %s, %s", first_name, last_name, email, class_stufe, serial_number, problem_description, steps_taken)
            photo_path = None
            if photo:
                if len(photo.read()) > 1 * 1024 * 1024:  # Validate file size 1MB
                    flash('File size exceeds the limit of 1MB.', 'danger')
                    return redirect(request.url)
                filename = secure_filename(photo.filename)
                if not allowed_file(photo.filename):  # Validate file type
                    flash('Invalid file type.', 'danger')
                    return redirect(request.url)
                try:
                    # Generate the new filename
                    date_str = datetime.now().strftime('%d-%m-%Y')
                    new_filename = f"{date_str}_{first_name}_{last_name}{os.path.splitext(filename)[1]}"
                    full_path = os.path.normpath(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
                    if not full_path.startswith(app.config['UPLOAD_FOLDER']):
                        raise Exception("Invalid file path")
                    photo.save(full_path)
                    photo_path = new_filename
                    app.logger.info("Photo uploaded: %s", photo_path)
                except Exception as e:
                    app.logger.error(f"Error saving photo: {e}")
                    flash('Error saving photo.', 'danger')
                    return redirect(request.url)

            ticket = ProblemTicket(
                first_name=first_name,
                last_name=last_name,
                email=email,
                class_name=class_stufe,
                serial_number=serial_number,
                problem_description=problem_description,
                steps_taken=steps_taken,
                photo=photo_path,
                status_id=1
            )

            db.session.add(ticket)

        elif ticket_type == 'fortbildung':
            if not request.form.get('class_teacher') or not request.form.get('email_fortbildung') or not request.form.get('training_type') or not request.form.get('training_reason') or not request.form.get('proposed_date'):
                flash('Please fill in all the required fields.', 'danger')
                return redirect(request.url)
            class_teacher = request.form.get('class_teacher')
            email = request.form.get('email_fortbildung')
            training_type = request.form.get('training_type')
            training_reason = request.form.get('training_reason')
            proposed_date = request.form.get('proposed_date')
            app.logger.info("Ticket submitted: %s, %s, %s, %s, %s", class_teacher, email, training_type, training_reason, proposed_date)
            ticket = TrainingTicket(
                class_teacher=class_teacher,
                email=email,
                training_type=training_type,
                training_reason=training_reason,
                proposed_date=proposed_date,
                status_id=1
            )

            db.session.add(ticket)

        else:
            if not request.form.get('first_name_sonstiges') or not request.form.get('last_name_sonstiges') or not request.form.get('email_sonstiges') or not request.form.get('message_sonstiges'):
                flash('Please fill in all the required fields.', 'danger')
                return redirect(request.url)
            first_name = request.form.get('first_name_sonstiges')
            last_name = request.form.get('last_name_sonstiges')
            message = request.form.get('message_sonstiges')
            email = request.form.get('email_sonstiges')
            app.logger.info("Ticket submitted: %s, %s, %s, %s", first_name, last_name, email, message)

            ticket = MiscTicket(
                first_name=first_name,
                last_name=last_name,
                email=email,
                message=message,
                status_id=1
            )

            db.session.add(ticket)

        db.session.commit()

        # Generate token and send email with the link
        send_ticket_link(ticket)

        flash(f'Ticket submitted successfully! Type: {ticket_type}', 'success')
        return redirect(url_for('home'))

    return render_template('ticket.html')



@login_required
@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))


@app.route('/forum', methods=['GET', 'POST'])
@login_required
def forum():
    form = MessageForm()
    if form.validate_on_submit():
        role = 'Admin' if current_user.is_admin else 'Member'
        message = Message(author=current_user.username, role=role, content=form.content.data)
        db.session.add(message)
        db.session.commit()
        flash('Your message has been posted.', 'success')
        return redirect(url_for('forum'))

    page = request.args.get('page', 1, type=int)
    messages = Message.query.order_by(Message.timestamp.desc()).paginate(page=page, per_page=5)
    return render_template('forum.html', form=form, messages=messages.items, pagination=messages)

@app.route('/load_more_messages/<int:page>', methods=['GET'])
@login_required
def load_more_messages(page):
    messages = Message.query.order_by(Message.timestamp.desc()).paginate(page=page, per_page=5)
    return jsonify({
        'messages': [{
            'id': message.id,
            'author': message.author,
            'role': message.role,
            'content': message.content,
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'deleted': message.deleted
        } for message in messages.items],
        'more_messages': messages.has_next,
        'is_admin': current_user.is_admin()
    })




@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')


@app.route('/archiv')
@login_required
def archiv():
    solved_problem_tickets = ProblemTicket.query.filter_by(status_id=4).all()
    solved_training_tickets = TrainingTicket.query.filter_by(status_id=4).all()
    solved_misc_tickets = MiscTicket.query.filter_by(status_id=4).all()

    return render_template('archiv.html',
                           solved_problem_tickets=solved_problem_tickets,
                           solved_training_tickets=solved_training_tickets,
                           solved_misc_tickets=solved_misc_tickets)


from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.models import User, db, RoleEnum, RankEnum


@app.route('/impressum')
def impressum():
    return render_template('impressum.html')


@app.route('/ticket/<token>', methods=['GET', 'POST'])
def view_ticket(token):
    ticket_type = None
    for TicketModel, type_name in [(ProblemTicket, 'problem'), (TrainingTicket, 'training'), (MiscTicket, 'misc')]:
        ticket = TicketModel.verify_token(token)
        if ticket:
            ticket_type = type_name
            break

    if not ticket:
        app.logger.error(f'Invalid or expired token: {token}')
        flash('Invalid or expired token', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        response_message = request.form.get('response_message')
        if ticket_type == 'problem':
            author_type = ticket.first_name + ' ' + ticket.last_name
        elif ticket_type == 'training':
            author_type = ticket.class_teacher
        else:
            author_type = ticket.first_name + ' ' + ticket.last_name

        log_ticket_message(ticket_type, ticket.id, response_message, author_type)
        flash('Your response has been submitted.', 'success')

        notify_user_about_ticket_change(ticket, response_message, ticket_type)

        return redirect(url_for('view_ticket', token=token, ticket=ticket))

    ticket_history = TicketHistory.query.filter_by(ticket_type=ticket_type, ticket_id=ticket.id).order_by(TicketHistory.created_at).all()

    return render_template('view_ticket.html', ticket=ticket, token=token, ticket_history=ticket_history)


def log_ticket_message(ticket_type, ticket_id, message, author_type):
    history_entry = TicketHistory(
        ticket_type=ticket_type,
        ticket_id=ticket_id,
        message=message,
        author_type=author_type
    )
    db.session.add(history_entry)
    db.session.commit()

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_date_time():
    from datetime import datetime
    now = datetime.now()
    return now.strftime("%d:%m:%Y %H:%M:%S")


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = EditProfileForm(obj=current_user)
    password_form = ChangePasswordForm()

    if form.validate_on_submit():
        print('Form validated successfully.')

        # Ensure the upload folder exists
        upload_folder = os.path.join(current_app.root_path, app.config['USER_PROFILES'])
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)  # Create the directory if it doesn't exist

        if form.profile_image.data:
            filename = secure_filename(form.profile_image.data.filename)
            new_filename = f"{current_user.first_name}_{current_user.last_name}{os.path.splitext(filename)[1]}"
            new_filename = new_filename.replace(' ', '_')  # Replace spaces with underscores
            print(f'Saving profile image as: {new_filename}')
            file_path = os.path.join(upload_folder, new_filename)  # Use os.path.join here
            form.profile_image.data.save(file_path)  # Save the file

            # Resize the image
            with Image.open(file_path) as img:
                img.thumbnail((800, 800))  # Resize the image to a maximum of 800x800 pixels
                img.save(file_path)  # Save the resized image

            current_user.profile_picture = new_filename

        if form.delete_image.data:
            print('Delete image checkbox is checked.')

            print('Deleting profile image.')
            # Use the current user's profile_picture attribute directly
            filename = f"{current_user.first_name}_{current_user.last_name}.png".replace(' ', '_')
            upload_folder_absolute = os.path.join(current_app.root_path, app.config['USER_PROFILES'])
            file_path = os.path.join(upload_folder_absolute, filename)
            if os.path.exists(file_path):
                print(f'Deleting profile image: {file_path}')
                os.remove(file_path)
            current_user.profile_picture = None

        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('profile'))

    print('Rendering profile template.')
    return render_template('profile.html', form=form, password_form=password_form)

@app.route('/profile_picture/<first_name>_<last_name>')
@login_required
def profile_picture(first_name, last_name):
    # Decode and replace underscores with spaces
    first_name = unquote(first_name).replace('_', ' ').strip()
    last_name = unquote(last_name).replace('_', ' ').strip()
    full_name = f"{first_name} {last_name}"
    current_full_name = f"{current_user.first_name.strip()} {current_user.last_name.strip()}"

    # Authorization check
    if full_name != current_full_name:
        flash('You are not allowed to access this profile picture.', 'danger')
        current_app.logger.warning(f'Unauthorized access to profile picture: {full_name} by {current_full_name}')
        return redirect(url_for('profile'))

    # Construct the filename and use an absolute path for existence check
    filename = f"{first_name}_{last_name}.png".replace(' ', '_')
    upload_folder_absolute = os.path.join(current_app.root_path, app.config['USER_PROFILES'])
    file_path = os.path.normpath(os.path.join(upload_folder_absolute, filename))

    # Ensure the file path is within the upload folder
    if not file_path.startswith(upload_folder_absolute):
        flash('Invalid file path.', 'danger')
        current_app.logger.warning(f'Invalid file path access attempt: {file_path}')
        return redirect(url_for('profile'))

    # Debugging output
    print(f"Absolute file path being checked: {file_path}")

    # Serve the profile picture if it exists
    if os.path.exists(file_path):
        print('Profile picture found, serving the file.')
        return send_from_directory(upload_folder_absolute, filename)
    else:
        # Serve default image if profile picture is not found
        print('Profile picture not found, serving default image.')
        return send_from_directory(current_app.static_folder, 'images/default_profile.png')

# app/routes.py
@app.route('/send_password_reset_email', methods=['POST'])
@login_required
def send_password_reset_email():
    user = current_user
    if user:
        send_reset_email(user)
        flash('Password reset instructions have been sent to your email.', 'info')
    else:
        flash('User not found.', 'danger')
    return redirect(url_for('profile'))
