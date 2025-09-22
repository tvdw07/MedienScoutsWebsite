import logging
import os
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask_migrate import Migrate
from flask_talisman import Talisman
from flask import Flask, flash, render_template, redirect, session
from flask_login import LoginManager, current_user
from flask_wtf import CSRFProtect
from sqlalchemy import text
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash
from concurrent_log_handler import ConcurrentRotatingFileHandler
from .models import db, User, ProblemTicket, ProblemTicketUser, TicketHistory, TrainingTicket, TrainingTicketUser, \
    MiscTicket, MiscTicketUser
import config
import atexit


def create_app():
    app = Flask(__name__)
    migrate = Migrate(app, db)

    # Logging
    if not os.path.exists('logs'):
        os.mkdir('logs')
    general_log_format = '%(asctime)s %(levelname)s: %(message)s'
    error_log_format = '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    date_format = '%d-%m-%Y %H:%M:%S'

    class CustomFormatter(logging.Formatter):
        def __init__(self, general_fmt, error_fmt, datefmt):
            super().__init__(datefmt=datefmt)
            self.general_fmt = logging.Formatter(general_fmt, datefmt=datefmt)
            self.error_fmt = logging.Formatter(error_fmt, datefmt=datefmt)

        def format(self, record):
            if record.levelno == logging.ERROR:
                return self.error_fmt.format(record)
            return self.general_fmt.format(record)

    file_handler = ConcurrentRotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(CustomFormatter(general_log_format, error_log_format, date_format))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Application startup')
    app.logger.info('Logging configured and started')

    app.logger.info("Loading configuration")
    app.config.from_object(config)
    app.logger.info("Configuration loaded")

    # CSRF
    app.logger.info("Initializing CSRF protection")
    csrf = CSRFProtect(app)

    csp = {
        'default-src': [
            '\'self\'',
            'https://stackpath.bootstrapcdn.com',
            'https://cdnjs.cloudflare.com',
            'https://cdn.jsdelivr.net',
            'https://code.jquery.com'
        ],
        'script-src': [
            '\'self\'',
            '\'unsafe-inline\'',
            'https://stackpath.bootstrapcdn.com',
            'https://cdnjs.cloudflare.com',
            'https://cdn.jsdelivr.net',
            'https://code.jquery.com'
        ],
        'style-src': [
            '\'self\'',
            '\'unsafe-inline\'',
            'https://stackpath.bootstrapcdn.com',
            'https://cdnjs.cloudflare.com',
            'https://cdn.jsdelivr.net'
        ],
        'font-src': [
            '\'self\'',
            'https://cdnjs.cloudflare.com',
            'https://cdn.jsdelivr.net'
        ],
        'img-src': [
            '\'self\'',
            'data:'
        ]
    }
    talisman = Talisman(app, content_security_policy=csp)
    app.logger.info("CSRF protection initialized")

    # Limiter
    app.logger.info("Initializing rate limiting")
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["1000 per hour"]
    )
    limiter.limit("5 per minute")(app.route('/login', methods=['POST']))
    limiter.limit("2 per minute")(app.route('/send_ticket', methods=['POST']))
    app.logger.info("Rate limiting initialized")

    db.init_app(app)

    app.logger.info("Initializing login manager")
    login_manager = LoginManager()
    login_manager.init_app(app)
    app.logger.info("Login manager initialized")

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_user():
        return dict(current_user=current_user)

    @app.errorhandler(401)
    def unauthorized(e):
        app.logger.warning('Unauthorized access: %s', e)
        flash('You must be logged in to access this page.', 'warning')
        return redirect('/login')

    def check_database():
        try:
            with app.app_context():
                db.session.execute(text('SELECT 1'))
            return True
        except Exception as e:
            app.logger.error(f"Database check failed: {e}")
            return False

    database_available = check_database()

    @app.before_request
    def before_request():
        session.permanent = True
        if not database_available:
            app.logger.error('Database is not available')
            return ("Service Unavailable Try again later!"), 503

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    def delete_old_things():
        with app.app_context():
            threshold_date = datetime.now() - timedelta(days=5 * 365)
            tickets_deleted = False
            old_problem_tickets = ProblemTicket.query.filter(ProblemTicket.created_at < threshold_date).all()
            for ticket in old_problem_tickets:
                ProblemTicketUser.query.filter_by(problem_ticket_id=ticket.id).delete()
                TicketHistory.query.filter_by(ticket_id=ticket.id, ticket_type='problem').delete()
                db.session.delete(ticket)
                tickets_deleted = True
            old_training_tickets = TrainingTicket.query.filter(TrainingTicket.created_at < threshold_date).all()
            for ticket in old_training_tickets:
                TrainingTicketUser.query.filter_by(training_ticket_id=ticket.id).delete()
                TicketHistory.query.filter_by(ticket_id=ticket.id, ticket_type='training').delete()
                db.session.delete(ticket)
                tickets_deleted = True
            old_misc_tickets = MiscTicket.query.filter(MiscTicket.created_at < threshold_date).all()
            for ticket in old_misc_tickets:
                MiscTicketUser.query.filter_by(misc_ticket_id=ticket.id).delete()
                TicketHistory.query.filter_by(ticket_id=ticket.id, ticket_type='misc').delete()
                db.session.delete(ticket)
                tickets_deleted = True
            if tickets_deleted:
                app.logger.info('Deleted old tickets')
                db.session.commit()
            photo_threshold_date = datetime.now() - timedelta(days=0.5 * 365)
            upload_folder = app.config['UPLOAD_FOLDER']
            if os.path.exists(upload_folder):
                for filename in os.listdir(upload_folder):
                    file_path = os.path.join(upload_folder, filename)
                    if os.path.isfile(file_path):
                        file_modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        if file_modified_time < photo_threshold_date:
                            os.remove(file_path)
                            app.logger.info(f'Deleted old photo: {filename}')
            log_threshold_date = datetime.now() - timedelta(days=7)
            log_file_path = 'logs/app.log'
            logs_deleted = False
            if os.path.exists(log_file_path):
                with open(log_file_path, 'r') as file:
                    lines = file.readlines()
                with open(log_file_path, 'w') as file:
                    for line in lines:
                        log_date_str = line.split(' ')[0]
                        log_date = datetime.strptime(log_date_str, '%Y-%m-%d')
                        if log_date >= log_threshold_date:
                            file.write(line)
                        else:
                            logs_deleted = True
            if logs_deleted:
                app.logger.info('Deleted old log entries')

    app.logger.info('Starting scheduler')
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=delete_old_things, trigger="interval", days=1)
    scheduler.start()
    app.logger.info('Scheduler started')
    atexit.register(lambda: scheduler.shutdown())

    with app.app_context():
        pass  # Admin-User-Anlage entfernt, erfolgt jetzt im Setup-Skript

    from .blueprints.bp_auth import bp_auth
    from .blueprints.bp_admin import bp_admin
    from .routes import bp_main
    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_admin)
    app.register_blueprint(bp_main)
    from . import routes
    app.logger.info('Application started successfully')
    return app
