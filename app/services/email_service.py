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

        # Próbuj połączyć się używając IPv4
        try:
            # Wymuszenie korzystania z IPv4
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
def send_confirmation_email(expenses):
    """Send confirmation email for added expenses"""
    if not expenses:
        return

    first = expenses[0]
    date = first.get("date")
    if isinstance(date, datetime.datetime):
        date = date.strftime("%Y-%m-%d")

    subject = f"Expense added on {date}: £{first.get('amount', 0)} to {first.get('category', 'Other category')}"

    html = """
    <html>
    <body>
        <h3>Expense Addition Confirmation</h3>
        <p>The following expenses have been added:</p>
        <ul>
    """
    for expense in expenses:
        exp_date = expense.get("date")
        if isinstance(exp_date, datetime.datetime):
            exp_date = exp_date.strftime("%Y-%m-%d")

        html += f"<li><strong>{exp_date}</strong>: £{expense.get('amount', 0)} – {expense.get('vendor', '')} ({expense.get('category', '')})<br>Description: {expense.get('description', '')}</li>"

    html += """
        </ul>
        <p style='margin-top: 20px;'>--<br>This is an automated message.</p>
    </body>
    </html>
    """

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
    """Send confirmation email for category addition"""
    status = "Success" if success else "Failed"
    subject = f"Category Addition {status}: {category_name}"

    html = f"""
    <html>
    <body>
        <h3>Category Addition {status}</h3>
        <p>Result of adding category <strong>"{category_name}"</strong>:</p>
        <p>{message}</p>
        <p>{'The new category is now available for expense categorization.' if success else 'Please try again with a different category name.'}</p>
        <p style='margin-top: 20px;'>--<br>This is an automated message.</p>
    </body>
    </html>
    """

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = Config.EMAIL_SENDER
    msg['To'] = Config.DEFAULT_EMAIL_RECIPIENT
    msg.set_content(f"Category addition {status.lower()}: {category_name}. {message}")
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
    """Send notification about pending category confirmation"""
    try:
        if not expense:
            logger.error("Cannot send notification - expense details not provided")
            return False

        # Utwórz treść powiadomienia
        subject = "Category Confirmation Required"

        body = f"""
        <html>
            <body>
                <h2>Expense Category Confirmation</h2>
                <p>The system is uncertain about the category for your recent expense:</p>

                <ul>
                    <li>Date: {expense['date']}</li>
                    <li>Amount: £{expense['amount']}</li>
                    <li>Vendor: {expense['vendor'] or 'Not specified'}</li>
                    <li>Description: {expense['description'] or 'None'}</li>
                </ul>
                <p>Currently assigned category: <strong>{current_category}</strong></p>
                <p>Predicted category: <strong>{predicted_category or 'No confident prediction'}</strong></p>
                <p>To confirm the category, click on one of the links below:</p>
                <ul>
                    <li><a href="{Config.APP_URL}/confirm-category/{expense['id']}/{current_category}">Confirm current category: {current_category}</a></li>

                    {f'<li><a href="{Config.APP_URL}/confirm-category/{expense["id"]}/{predicted_category}">Confirm predicted category: {predicted_category}</a></li>' if predicted_category else ''}

                    {''.join([f'<li><a href="{Config.APP_URL}/confirm-category/{expense["id"]}/{alt["category"]}">Use category: {alt["category"]} (confidence: {alt["confidence"]:.0%})</a></li>' for alt in alternatives])}

                    <li><a href="{Config.APP_URL}/edit-expense/{expense['id']}">Edit expense details</a></li>
                </ul>
            </body>
        </html>
        """

        # Wyślij email
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

    # Jeśli nie ma wyraźnych słów kluczowych raportu, nie kontynuuj
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