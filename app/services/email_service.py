import smtplib
import datetime
from email.message import EmailMessage
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.config import Config
import logging
from app.database.db_manager import DBManager
from app.nlp.nlp_category_parser import extract_category_from_text, extract_date_range_from_text
from app.services.email_templates import EmailTemplates

logger = logging.getLogger(__name__)


def send_email(recipient, subject, body, attachments=None):
    """Send email with optional attachments and better error handling"""
    try:
        msg = MIMEMultipart()
        msg['From'] = Config.EMAIL_SENDER
        msg['To'] = recipient
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'html'))

        if attachments:
            for filename, file_content in attachments.items():
                attachment = MIMEApplication(file_content)
                attachment['Content-Disposition'] = f'attachment; filename="{filename}"'
                msg.attach(attachment)

        try:
            server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT,
                                local_hostname=None, source_address=('0.0.0.0', 0))
            server.starttls()
            server.login(Config.EMAIL_USER, Config.EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            logger.info(f"Email sent to {recipient} successfully")
            return True
        except Exception as e:
            logger.warning(f"Failed to send email via primary method: {e}")

            try:
                server = smtplib.SMTP_SSL(Config.SMTP_SERVER, 465)
                server.login(Config.EMAIL_USER, Config.EMAIL_PASSWORD)
                server.send_message(msg)
                server.quit()
                logger.info(f"Email sent to {recipient} successfully via alternate port")
                return True
            except Exception as e2:
                logger.error(f"All email sending methods failed: {e2}")
                return False

    except Exception as e:
        logger.error(f"Error preparing email: {str(e)}")
        return False
def send_confirmation_email(expenses, transcription=None):
    """Send confirmation email for added expenses - uses unified template"""
    if not expenses:
        return

    # Use unified email template
    subject, html = EmailTemplates.expense_confirmation(
        expenses=expenses,
        transcription=transcription,
        source="discord"  # This function is primarily called from Discord bot
    )

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = Config.EMAIL_SENDER
    msg['To'] = Config.DEFAULT_EMAIL_RECIPIENT
    msg.set_content("New expenses have been added. Please view the HTML version of this message.")
    msg.add_alternative(html, subtype='html')

    try:
        with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(Config.EMAIL_USER, Config.EMAIL_PASSWORD)
            smtp.send_message(msg)
        logger.info(f"Confirmation email sent to: {Config.DEFAULT_EMAIL_RECIPIENT}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

def send_category_addition_email(category_name, success, message):
    """Send confirmation email for category addition - uses unified template"""
    # Use unified email template
    subject, html = EmailTemplates.category_action(
        category_name=category_name,
        action="added",
        success=success,
        message=message
    )

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = Config.EMAIL_SENDER
    msg['To'] = Config.DEFAULT_EMAIL_RECIPIENT
    msg.set_content(f"Category addition {'succeeded' if success else 'failed'}: {category_name}. {message}")
    msg.add_alternative(html, subtype='html')

    try:
        with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(Config.EMAIL_USER, Config.EMAIL_PASSWORD)
            smtp.send_message(msg)
        logger.info(f"Category addition email sent to: {Config.DEFAULT_EMAIL_RECIPIENT}")
        return True
    except Exception as e:
        logger.error(f"Failed to send category addition email: {e}")
        return False

def send_category_confirmation_notification(expense, current_category, predicted_category, alternatives):
    """Send notification about pending category confirmation - uses unified template"""
    try:
        if not expense:
            logger.error("Cannot send notification - expense details not provided")
            return False

        # Use unified email template
        subject, body = EmailTemplates.category_confirmation_required(
            expense=expense,
            current_category=current_category,
            predicted_category=predicted_category,
            alternatives=alternatives
        )

        send_email(
            recipient=Config.DEFAULT_EMAIL_RECIPIENT,
            subject=subject,
            body=body
        )

        return True

    except Exception as e:
        logger.error(f"Error sending confirmation notification: {str(e)}", exc_info=True)
        return False

def try_generate_report_from_text(transcription):
    """Attempt to generate a report based on transcribed text"""
    config = Config()
    db = DBManager(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=config.DB_NAME
    )

    report_keywords = ['raport', 'report', 'zestawienie', 'podsumowanie', 'wyślij raport',
                       'generuj raport', 'stwórz raport', 'wygeneruj raport']

    is_report_command = any(keyword in transcription.lower() for keyword in report_keywords)

    # If there are no clear report keywords, do not proceed
    if not is_report_command:
        logger.info(f"Transkrypcja nie zawiera komend raportowania: '{transcription}'")
        return False

    categories = db.get_all_categories()
    category = extract_category_from_text(transcription, categories)

    # Extract date range if present
    start_date, end_date = extract_date_range_from_text(transcription)

    # Recognize report format (default Excel)
    format_type = 'excel'
    if 'pdf' in transcription.lower():
        format_type = 'pdf'
    elif 'csv' in transcription.lower():
        format_type = 'csv'

    # Log detected parameters
    logger.info(
        f"Report parameters - Category: {category}, Date range: {start_date} to {end_date}, Format: {format_type}")

    # Only proceed if we have either a category or date range
    if category or start_date:
        logger.info(
            f"Generating report - Category: {category or 'All'}, Date range: {start_date or 'All time'} to {end_date or 'Present'}")
        from app.core.report_generator import send_report_email
        send_report_email(
            category=category,
            start_date=start_date,
            end_date=end_date,
            format_type=format_type
        )
        return True
    else:
        logger.warning("No category or date range recognized for report from transcription.")
        return False