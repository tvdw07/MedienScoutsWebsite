import configparser
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import url_for

from app import app, User


class EmailTemplate:
    def __init__(self, subject, template_content):
        self.subject = subject
        self.template_content = template_content

    def render(self, **kwargs):
        # Fügt die Variablen in den Template-Content ein
        return self.template_content.format(**kwargs)


# Funktion zum Senden einer E-Mail mit dynamischem Template
def send_email(template, recipient, **variables):
    # Konfigurationsdatei lesen
    config = configparser.ConfigParser()
    config.read('config.ini')

    # SMTP-Konfigurationsdaten auslesen
    smtp_server = config['SMTP']['server']
    smtp_port = config['SMTP'].getint('port')
    smtp_user = config['SMTP']['user']
    smtp_password = config['SMTP']['password']

    variables['current_year'] = datetime.now().year

    from_email = smtp_user
    subject = template.subject
    html_content = template.render(**variables)

    # E-Mail-Nachricht erstellen
    message = MIMEMultipart('alternative')
    message['From'] = from_email
    message['To'] = recipient
    message['Subject'] = subject

    # HTML-Nachricht hinzufügen
    html_part = MIMEText(html_content, 'html')
    message.attach(html_part)

    # E-Mail senden
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(from_email, recipient, message.as_string())
        server.quit()
        print("E-Mail wurde erfolgreich gesendet.")
    except Exception as e:
        print(f"Fehler beim Senden der E-Mail: {e}")

ticket_link_template = EmailTemplate(
    subject="Your Ticket Link",
    template_content="""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                background-color: #f4f4f7;
                color: #333333;
                margin: 0;
                padding: 0;
                line-height: 1.6;
            }}
            .container {{
                max-width: 600px;
                margin: 30px auto;
                padding: 20px;
                background: #ffffff;
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                background: linear-gradient(135deg, #4CAF50, #3b8d41);
                padding: 20px 10px;
                border-radius: 10px 10px 0 0;
            }}
            .header h1 {{
                color: #ffffff;
                margin: 0;
                font-size: 24px;
            }}
            .content {{
                padding: 20px;
                text-align: left;
            }}
            .content p {{
                margin: 10px 0;
            }}
            .btn {{
                display: block;
                width: fit-content;
                padding: 12px 25px;
                margin: 20px auto;
                background: #007BFF;
                color: white;
                text-align: center;
                border-radius: 5px;
                text-decoration: none;
                font-size: 16px;
                font-weight: bold;
            }}
            .btn:hover {{
                background: #0056b3;
            }}
            .footer {{
                text-align: center;
                font-size: 12px;
                color: #666666;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Your Ticket Link</h1>
            </div>
            <div class="content">
                <p>Hello,</p>
                <p>You can view and reply to your ticket using the link below:</p>
                <a href="{link}" class="btn">View Ticket</a>
            </div>
            <div class="footer">
                <p>&copy; {current_year} Medienscouts | All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
)

notify_admin_template = EmailTemplate(
    subject="Admin Notification",
    template_content="""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f9f9f9; color: #333; padding: 20px; }}
            .email-header {{ background-color: #4CAF50; color: white; padding: 10px; text-align: center; }}
            .email-content {{ padding: 20px; background-color: white; border-radius: 8px; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1); }}
            .btn {{ display: inline-block; padding: 10px 20px; background-color: #007BFF; color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
            .email-footer {{ font-size: 12px; color: #777; text-align: center; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="email-header">
            <h1>New Ticket Notification</h1>
        </div>
            <div class="email-content">
                <p>Hello Admin,</p>
                <p>{message}</p>
                <p><a href="{link}" class="btn">View Ticket</a></p>
            </div>
        <div class="email-footer">
            <p>&copy; {current_year} Medienscouts | All rights reserved.</p>
        </div>
    </body>
    </html>
    """
)

notify_client_about_ticket_change_template = EmailTemplate(
    subject="Response to Your Ticket",
    template_content="""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; background-color: #f9f9f9; color: #333; padding: 20px; }}
                    .email-header {{ background-color: #4CAF50; color: white; padding: 10px; text-align: center; }}
                    .email-content {{ padding: 20px; background-color: white; border-radius: 8px; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1); }}
                    .btn {{ display: inline-block; padding: 10px 20px; background-color: #007BFF; color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
                    .email-footer {{ font-size: 12px; color: #777; text-align: center; margin-top: 20px; }}
                </style>
            </head>
            <body>
                <div class="email-header">
                    <h1>Response to Your Ticket</h1>
                </div>
                <div class="email-content">
                    <p>Hello,</p>
                    <p>We have responded to your ticket. Please check the details below:</p>
                    <p>{response_message}</p>
                    <p><a href="{link}" class="btn">View Ticket</a></p>
                </div>
                <div class="email-footer">
                    <p>&copy; {current_year} Medienscouts | All rights reserved.</p>
                </div>
            </body>
            </html>
            """
)

notify_user_about_ticket_change_template = EmailTemplate(
    subject="Response to Your Ticket",
    template_content="""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; background-color: #f9f9f9; color: #333; padding: 20px; }}
                    .email-header {{ background-color: #4CAF50; color: white; padding: 10px; text-align: center; }}
                    .email-content {{ padding: 20px; background-color: white; border-radius: 8px; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1); }}
                    .btn {{ display: inline-block; padding: 10px 20px; background-color: #007BFF; color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
                    .email-footer {{ font-size: 12px; color: #777; text-align: center; margin-top: 20px; }}
                </style>
            </head>
            <body>
                <div class="email-header">
                    <h1>Response to Your Ticket</h1>
                </div>
                <div class="email-content">
                    <p>Hello,</p>
                    <p>The Client has responded to your ticket. Please check the details below:</p>
                    <p>{response_message}</p>
                    <p><a href="{link}" class="btn">View Ticket</a></p>
                </div>
                <div class="email-footer">
                    <p>&copy; {current_year} Medienscouts | All rights reserved.</p>
                </div>
            </body>
            </html>
            """
)

reset_password_template = EmailTemplate(
    subject="Password Reset Request",
    template_content="""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f9f9f9; color: #333; padding: 20px; }}
            .email-header {{ background-color: #4CAF50; color: white; padding: 10px; text-align: center; }}
            .email-content {{ padding: 20px; background-color: white; border-radius: 8px; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1); }}
            .btn {{ display: inline-block; padding: 10px 20px; background-color: #007BFF; color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
            .email-footer {{ font-size: 12px; color: #777; text-align: center; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="email-header">
            <h1>Password Reset Request</h1>
        </div>
        <div class="email-content">
            <p>Hello,</p>
            <p>You can reset your password using the following link:</p>
            <p><a href="{reset_url}" class="btn">Reset Password</a></p>
        </div>
        <div class="email-footer">
            <p>&copy; {current_year} Medienscouts | All rights reserved.</p>
        </div>
    </body>
    </html>
    """
)



def send_ticket_link(ticket):
    token = ticket.generate_token()
    link = url_for('view_ticket', token=token, _external=True)
    send_email(ticket_link_template, ticket.email, link=link)
    app.logger.info(f"Sent ticket link to {ticket.email}")


def notify_admin(ticket, ticket_type, message):
    from app.models import User
    admin = User.query.filter_by(role='ADMIN', active=True).first()
    link = url_for('ticket_details', ticket_id=ticket.id, ticket_type=ticket_type, _external=True)
    send_email(notify_admin_template, admin.email, message=message, link=link)
    app.logger.info(f"Sent admin notification about new ticket {ticket.id}")


def notify_client(ticket, message):
    token = ticket.generate_token()
    link = url_for('view_ticket', token=token, _external=True)
    send_email(notify_client_about_ticket_change_template, ticket.email, response_message=message, link=link)
    app.logger.info(f"Sent client notification about ticket {ticket.id}")

def notify_user_about_ticket_change(ticket, message, ticket_type):
    from app.models import ProblemTicketUser, TrainingTicketUser, MiscTicketUser, User

    # Determine the correct user assignment model based on ticket type
    if ticket_type == 'problem':
        responsible_user = ProblemTicketUser.query.filter_by(problem_ticket_id=ticket.id).first()
    elif ticket_type == 'training':
        responsible_user = TrainingTicketUser.query.filter_by(training_ticket_id=ticket.id).first()
    elif ticket_type == 'misc':
        responsible_user = MiscTicketUser.query.filter_by(misc_ticket_id=ticket.id).first()
    else:
        responsible_user = None

    if responsible_user:
        user = User.query.get(responsible_user.user_id)
        if user:
            link = url_for('ticket_details', ticket_id=ticket.id, ticket_type=ticket_type, _external=True)
            send_email(notify_user_about_ticket_change_template, user.email, response_message=message, link=link)
            app.logger.info(f"Sent user notification about ticket {ticket.id}")
        else:
            app.logger.error(f"User not found for ticket {ticket.id}")

def send_reset_email(user):
    token = user.generate_reset_password_token()
    reset_url = url_for('reset_password', token=token, user_id=user.id, _external=True)  # Use 'user_id' instead of 'id'
    send_email(reset_password_template, user.email, reset_url=reset_url)
    app.logger.info(f"Sent password reset email to {user.email}")