import logging
import os
from flask_migrate import Migrate
from flask_talisman import Talisman
from flask import Flask, flash, render_template, redirect, session, url_for
from flask_login import LoginManager, current_user
from flask_wtf import CSRFProtect
from sqlalchemy import text
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from concurrent_log_handler import ConcurrentRotatingFileHandler
from werkzeug.middleware.proxy_fix import ProxyFix
from .maintenance import start_maintenance_scheduler
from .models import db, User
import config


def create_app():
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
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
    talisman = Talisman(
        app,
        content_security_policy=csp,
        force_https=app.config['FORCE_HTTPS']
    )
    app.logger.info("CSRF protection initialized")

    # Limiter
    app.logger.info("Initializing rate limiting")
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["1000 per hour"],
        storage_uri=app.config["RATELIMIT_STORAGE_URI"],
    )
    app.logger.info("Rate limiting initialized")

    db.init_app(app)

    app.logger.info("Initializing login manager")
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    app.logger.info("Login manager initialized")

    @login_manager.user_loader
    def load_user(user_id):
        return User.load_from_session_identifier(user_id)

    @app.context_processor
    def inject_user():
        return dict(current_user=current_user)

    @app.context_processor
    def inject_ticket_assignment_notifications():
        from .ticket_notifications import get_unread_ticket_assignment_notifications

        if not current_user.is_authenticated:
            return dict(ticket_assignment_notifications=[])
        return dict(
            ticket_assignment_notifications=get_unread_ticket_assignment_notifications(current_user.id)
        )

    @app.errorhandler(401)
    def unauthorized(e):
        app.logger.warning('Unauthorized access: %s', e)
        flash('You must be logged in to access this page.', 'warning')
        return redirect(url_for('auth.login'))

    @app.before_request
    def before_request():
        session.permanent = True
        try:
            db.session.execute(text('SELECT 1'))
        except Exception as e:
            app.logger.error(f'Database is not available: {e}')
            return "Service Unavailable Try again later!", 503

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    from .blueprints.bp_auth import bp_auth
    from .blueprints.bp_admin import bp_admin
    from .blueprints.main import bp_main
    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_admin)
    app.register_blueprint(bp_main)
    app.logger.info('Starting maintenance scheduler')
    start_maintenance_scheduler(app)
    limiter.limit("3 per minute", methods=["POST"])(app.view_functions["auth.login"])
    limiter.limit("1 per minute", methods=["POST"])(app.view_functions["main.send_ticket"])
    limiter.limit("1 per minute", methods=["POST"])(app.view_functions["auth.request_password_reset"])
    app.logger.info('Application started successfully')
    return app
