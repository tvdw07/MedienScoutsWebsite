import configparser
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import url_for, current_app


class EmailTemplate:
    def __init__(self, subject, template_content):
        self.subject = subject
        self.template_content = template_content

    def render(self, **kwargs):
        # Ensure the template content is formatted correctly
        return self.template_content.format(**kwargs)


def test_email_functionality(recipient_email):
    """
    Test function to verify email sending functionality.
    This function should be called in a test environment to ensure that the email
    sending process works correctly.
    """
    try:
        # Example usage of the send_email function
        send_email(
            template=ticket_link_template,
            recipient=recipient_email,
            link="https://example.com"  # Placeholder link for testing
        )
        print("Email functionality test passed.")
    except Exception as e:
        print(f"Email functionality test failed: {e}")


# Function to send an email with a dynamic template
import logging

def send_email(template, recipient, **variables):
    # Read configuration file
    config = configparser.ConfigParser()
    config.read('config.ini')

    # Read SMTP configuration data
    smtp_server = config['SMTP']['server']
    smtp_port = int(config['SMTP']['port'])
    smtp_user = config['SMTP']['user']
    smtp_password = config['SMTP']['password']

    variables['current_year'] = datetime.now().year

    from_email = smtp_user
    subject = template.subject
    html_content = template.render(**variables)

    # Create email message
    message = MIMEMultipart('alternative')
    message['From'] = from_email
    message['To'] = recipient
    message['Subject'] = subject

    # Add HTML message
    html_part = MIMEText(html_content, 'html')
    message.attach(html_part)

    # Send email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.set_debuglevel(1)  # Enable SMTP debug output
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(from_email, recipient, message.as_string())
        server.quit()
        logging.info("Email sent successfully.")
    except smtplib.SMTPAuthenticationError as e:
        logging.error(f"SMTP Authentication Error: {e}")
        print("Authentication failed. Please check your SMTP credentials.")
    except smtplib.SMTPConnectError as e:
        logging.error(f"SMTP Connection Error: {e}")
        print("Failed to connect to the SMTP server. Please check the server address and port.")
    except smtplib.SMTPRecipientsRefused as e:
        logging.error(f"SMTP Recipients Refused: {e}")
        print("The recipient address was refused. Please check the recipient email.")
    except smtplib.SMTPException as e:
        logging.error(f"SMTP Error: {e}")
        print("An SMTP error occurred. Please check the SMTP configuration.")
    except Exception as e:
        logging.error(f"General Error: {e}")
        print("An unexpected error occurred while sending the email.")


# Ticket Link Email Template
ticket_link_template = EmailTemplate(
    subject="Your Ticket Link",
    template_content="""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <!-- Using Google Fonts for a modern look -->
      <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap" rel="stylesheet">
      <style>
        body {{
          font-family: 'Roboto', Arial, sans-serif;
          background-color: #f7f9fc;
          margin: 0;
          padding: 0;
          color: #444;
          line-height: 1.6;
        }}
        .container {{
          max-width: 600px;
          margin: 40px auto;
          background: #fff;
          border-radius: 12px;
          box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
          overflow: hidden;
        }}
        .header {{
          background: linear-gradient(135deg, #4CAF50, #2E7D32);
          padding: 30px;
          text-align: center;
        }}
        .header h1 {{
          color: #fff;
          margin: 0;
          font-size: 26px;
          font-weight: 500;
        }}
        .content {{
          padding: 30px;
        }}
        .content p {{
          margin: 15px 0;
          font-size: 16px;
        }}
        .btn {{
          display: inline-block;
          padding: 14px 30px;
          margin: 20px 0;
          background: #007BFF;
          color: #fff;
          text-decoration: none;
          border-radius: 6px;
          font-size: 16px;
          font-weight: 500;
        }}
        .btn:hover {{
          background: #0056b3;
        }}
        .footer {{
          background: #f1f1f1;
          text-align: center;
          padding: 15px;
          font-size: 12px;
          color: #777;
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
          <p style="text-align: center;"><a href="{link}" class="btn">View Ticket</a></p>
        </div>
        <div class="footer">
          <p>&copy; {current_year} Medienscouts | All rights reserved.</p>
        </div>
      </div>
    </body>
    </html>
    """
)

# Admin Notification Email Template
notify_admin_template = EmailTemplate(
    subject="Admin Notification",
    template_content="""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap" rel="stylesheet">
      <style>
        body {{
          font-family: 'Roboto', Arial, sans-serif;
          background-color: #f2f4f8;
          padding: 20px;
          color: #333;
        }}
        .email-container {{
          max-width: 600px;
          margin: 0 auto;
          background: #fff;
          border-radius: 10px;
          box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
          overflow: hidden;
        }}
        .email-header {{
          background-color: #4CAF50;
          padding: 25px;
          text-align: center;
          color: #fff;
        }}
        .email-header h1 {{
          margin: 0;
          font-size: 24px;
          font-weight: 500;
        }}
        .email-content {{
          padding: 30px;
          font-size: 16px;
        }}
        .btn {{
          display: inline-block;
          padding: 12px 25px;
          background-color: #007BFF;
          color: #fff;
          text-decoration: none;
          border-radius: 6px;
          margin-top: 20px;
          font-weight: 500;
        }}
        .btn:hover {{
          background-color: #0056b3;
        }}
        .email-footer {{
          background: #f9f9f9;
          text-align: center;
          padding: 15px;
          font-size: 12px;
          color: #777;
        }}
      </style>
    </head>
    <body>
      <div class="email-container">
        <div class="email-header">
          <h1>New Ticket Notification</h1>
        </div>
        <div class="email-content">
          <p>Hello Admin,</p>
          <p>{message}</p>
          <p style="text-align: center;"><a href="{link}" class="btn">View Ticket</a></p>
        </div>
        <div class="email-footer">
          <p>&copy; {current_year} Medienscouts | All rights reserved.</p>
        </div>
      </div>
    </body>
    </html>
    """
)

inform_admin_template = EmailTemplate(
    subject="Admin Notification",
    template_content="""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap" rel="stylesheet">
      <style>
        body {{
          font-family: 'Roboto', Arial, sans-serif;
          background-color: #f2f4f8;
          padding: 20px;
          color: #333;
        }}
        .email-container {{
          max-width: 600px;
          margin: 0 auto;
          background: #fff;
          border-radius: 10px;
          box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
          overflow: hidden;
        }}
        .email-header {{
          background-color: #4CAF50;
          padding: 25px;
          text-align: center;
          color: #fff;
        }}
        .email-header h1 {{
          margin: 0;
          font-size: 24px;
          font-weight: 500;
        }}
        .email-content {{
          padding: 30px;
          font-size: 16px;
        }}
        .btn {{
          display: inline-block;
          padding: 12px 25px;
          background-color: #007BFF;
          color: #fff;
          text-decoration: none;
          border-radius: 6px;
          margin-top: 20px;
          font-weight: 500;
        }}
        .btn:hover {{
          background-color: #0056b3;
        }}
        .email-footer {{
          background: #f9f9f9;
          text-align: center;
          padding: 15px;
          font-size: 12px;
          color: #777;
        }}
      </style>
    </head>
    <body>
      <div class="email-container">
        <div class="email-header">
          <h1>{headline}</h1>
        </div>
        <div class="email-content">
          <p>Hello Admin,</p>
          <p>{message}</p>
          <p style="text-align: center; {button_style}"><a href="{link}" class="btn">{button_text}</a></p>
        </div>
        <div class="email-footer">
          <p>&copy; {current_year} Medienscouts | All rights reserved.</p>
        </div>
      </div>
    </body>
    </html>
    """
)

# Client Notification about Ticket Change
notify_client_about_ticket_change_template = EmailTemplate(
    subject="Response to Your Ticket",
    template_content="""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap" rel="stylesheet">
      <style>
        body {{
          font-family: 'Roboto', Arial, sans-serif;
          background-color: #f2f4f8;
          padding: 20px;
          color: #333;
        }}
        .email-container {{
          max-width: 600px;
          margin: 0 auto;
          background: #fff;
          border-radius: 10px;
          box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
          overflow: hidden;
        }}
        .email-header {{
          background-color: #4CAF50;
          padding: 25px;
          text-align: center;
          color: #fff;
        }}
        .email-header h1 {{
          margin: 0;
          font-size: 24px;
          font-weight: 500;
        }}
        .email-content {{
          padding: 30px;
          font-size: 16px;
        }}
        .btn {{
          display: inline-block;
          padding: 12px 25px;
          background-color: #007BFF;
          color: #fff;
          text-decoration: none;
          border-radius: 6px;
          margin-top: 20px;
          font-weight: 500;
        }}
        .btn:hover {{
          background-color: #0056b3;
        }}
        .email-footer {{
          background: #f9f9f9;
          text-align: center;
          padding: 15px;
          font-size: 12px;
          color: #777;
        }}
      </style>
    </head>
    <body>
      <div class="email-container">
        <div class="email-header">
          <h1>Response to Your Ticket</h1>
        </div>
        <div class="email-content">
          <p>Hello,</p>
          <p>We have responded to your ticket. Please check the details below:</p>
          <p>{response_message}</p>
          <p style="text-align: center;"><a href="{link}" class="btn">View Ticket</a></p>
        </div>
        <div class="email-footer">
          <p>&copy; {current_year} Medienscouts | All rights reserved.</p>
        </div>
      </div>
    </body>
    </html>
    """
)

# User Notification about Ticket Change
notify_user_about_ticket_change_template = EmailTemplate(
    subject="Response to Your Ticket",
    template_content="""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap" rel="stylesheet">
      <style>
        body {{
          font-family: 'Roboto', Arial, sans-serif;
          background-color: #f2f4f8;
          padding: 20px;
          color: #333;
        }}
        .email-container {{
          max-width: 600px;
          margin: 0 auto;
          background: #fff;
          border-radius: 10px;
          box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
          overflow: hidden;
        }}
        .email-header {{
          background-color: #4CAF50;
          padding: 25px;
          text-align: center;
          color: #fff;
        }}
        .email-header h1 {{
          margin: 0;
          font-size: 24px;
          font-weight: 500;
        }}
        .email-content {{
          padding: 30px;
          font-size: 16px;
        }}
        .btn {{
          display: inline-block;
          padding: 12px 25px;
          background-color: #007BFF;
          color: #fff;
          text-decoration: none;
          border-radius: 6px;
          margin-top: 20px;
          font-weight: 500;
        }}
        .btn:hover {{
          background-color: #0056b3;
        }}
        .email-footer {{
          background: #f9f9f9;
          text-align: center;
          padding: 15px;
          font-size: 12px;
          color: #777;
        }}
      </style>
    </head>
    <body>
      <div class="email-container">
        <div class="email-header">
          <h1>Response to Your Ticket</h1>
        </div>
        <div class="email-content">
          <p>Hello,</p>
          <p>The client has responded to your ticket. Please check the details below:</p>
          <p>{response_message}</p>
          <p style="text-align: center;"><a href="{link}" class="btn">View Ticket</a></p>
        </div>
        <div class="email-footer">
          <p>&copy; {current_year} Medienscouts | All rights reserved.</p>
        </div>
      </div>
    </body>
    </html>
    """
)

# Reset Password Email Template
reset_password_template = EmailTemplate(
    subject="Password Reset Request",
    template_content="""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap" rel="stylesheet">
      <style>
        body {{
          font-family: 'Roboto', Arial, sans-serif;
          background-color: #f2f4f8;
          padding: 20px;
          color: #333;
        }}
        .email-container {{
          max-width: 600px;
          margin: 0 auto;
          background: #fff;
          border-radius: 10px;
          box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
          overflow: hidden;
        }}
        .email-header {{
          background-color: #4CAF50;
          padding: 25px;
          text-align: center;
          color: #fff;
        }}
        .email-header h1 {{
          margin: 0;
          font-size: 24px;
          font-weight: 500;
        }}
        .email-content {{
          padding: 30px;
          font-size: 16px;
        }}
        .btn {{
          display: inline-block;
          padding: 12px 25px;
          background-color: #007BFF;
          color: #fff;
          text-decoration: none;
          border-radius: 6px;
          margin-top: 20px;
          font-weight: 500;
        }}
        .btn:hover {{
          background-color: #0056b3;
        }}
        .email-footer {{
          background: #f9f9f9;
          text-align: center;
          padding: 15px;
          font-size: 12px;
          color: #777;
        }}
      </style>
    </head>
    <body>
      <div class="email-container">
        <div class="email-header">
          <h1>Password Reset Request</h1>
        </div>
        <div class="email-content">
          <p>Hello,</p>
          <p>You can reset your password using the link below:</p>
          <p style="text-align: center;"><a href="{reset_url}" class="btn">Reset Password</a></p>
        </div>
        <div class="email-footer">
          <p>&copy; {current_year} Medienscouts | All rights reserved.</p>
        </div>
      </div>
    </body>
    </html>
    """
)


def send_ticket_link(ticket):
    token = ticket.generate_token()
    link = url_for('main.view_ticket', token=token, _external=True)
    send_email(ticket_link_template, ticket.email, link=link)
    current_app.logger.info(f"Sent ticket link to {ticket.email}")


def notify_admin(ticket, ticket_type, message):
    from app.models import User
    admin = User.query.filter_by(role='ADMIN', active=True).first()
    link = url_for('main.ticket_details', ticket_id=ticket.id, ticket_type=ticket_type, _external=True)
    send_email(notify_admin_template, admin.email, message=message, link=link)
    current_app.logger.info(f"Sent admin notification about new ticket {ticket.id}")


def inform_admin(headline, message):
    from app.models import User
    admin = User.query.filter_by(role='ADMIN', active=True).first()
    send_email(
        inform_admin_template,
        recipient=admin.email,
        headline=headline,
        message=message,
        link="",  # Empty link
        button_text="",  # No button text
        button_style="display: none;"  # Hide the button
    )
    current_app.logger.info(f"Sent admin notification")


def notify_client(ticket, message):
    token = ticket.generate_token()
    link = url_for('main.view_ticket', token=token, _external=True)
    send_email(notify_client_about_ticket_change_template, ticket.email, response_message=message, link=link)
    current_app.logger.info(f"Sent client notification about ticket {ticket.id}")


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
            link = url_for('main.ticket_details', ticket_id=ticket.id, ticket_type=ticket_type, _external=True)
            send_email(notify_user_about_ticket_change_template, user.email, response_message=message, link=link)
            current_app.logger.info(f"Sent user notification about ticket {ticket.id}")
        else:
            current_app.logger.error(f"User not found for ticket {ticket.id}")


def send_reset_email(user):
    token = user.generate_reset_password_token()
    reset_url = url_for('auth.reset_password', token=token, user_id=user.id, _external=True)
    send_email(reset_password_template, user.email, reset_url=reset_url)
    current_app.logger.info(f"Sent password reset email to {user.email}")
