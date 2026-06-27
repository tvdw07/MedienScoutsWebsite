from flask import current_app, render_template

from app.decorators import permission_required
from app.legal import build_legal_context
from app.models import User

from . import bp_main


@bp_main.context_processor
def inject_legal_context():
    return {
        'legal': build_legal_context(current_app.config),
    }


@bp_main.route('/')
def home():
    """Start page with the number of active members."""
    member_count = User.query.filter_by(active=True).count()
    return render_template('pages/home.html', member_count=member_count)


@bp_main.route('/members')
def members():
    """List active and inactive members."""
    active_members = User.query.filter_by(active=True).all()
    inactive_members = User.query.filter_by(active=False).all()
    return render_template('pages/members.html', active_members=active_members, inactive_members=inactive_members)


@bp_main.route('/privacy_policy')
def privacy_policy():
    return render_template('legal/privacy_policy.html')


@bp_main.route('/impressum')
def impressum():
    return render_template('legal/impressum.html')


@bp_main.route('/archiv')
@permission_required('tickets.archive')
def archiv():
    """Display the archive of solved tickets."""
    from app.models import MediaConsultingTicket, MiscTicket, ProblemTicket, TrainingTicket

    solved_problem_tickets = ProblemTicket.query.filter_by(status_id=4).all()
    solved_training_tickets = TrainingTicket.query.filter_by(status_id=4).all()
    solved_misc_tickets = MiscTicket.query.filter_by(status_id=4).all()
    solved_media_consulting_tickets = MediaConsultingTicket.query.filter_by(status_id=4).all()

    return render_template(
        'pages/archiv.html',
        solved_problem_tickets=solved_problem_tickets,
        solved_training_tickets=solved_training_tickets,
        solved_misc_tickets=solved_misc_tickets,
        solved_media_consulting_tickets=solved_media_consulting_tickets,
    )

