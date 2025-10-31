import os
import datetime
import logging
import uuid
import json
from werkzeug.utils import secure_filename

from app.services.transcription import transcribe_audio
from app.nlp.expense_extractor import enhance_with_llm
from app.services.category_service import detect_category_command
from app.services.email_service import send_email, send_category_confirmation_notification
from app.config import Config

logger = logging.getLogger(__name__)


def process_audio_file(file_object, upload_folder, db_manager, email=None):
    """
    Args:
        file_object: File object with recording (e.g. from request.files['file'])
        upload_folder: Path to directory for uploaded files
        db_manager: DBManager instance for database interaction
        email: Optional email address to send confirmation

    Returns:
        dict: Dictionary containing processing result (success/error, expense data)
    """
    try:
        # Save uploaded file
        filename = secure_filename(f"{uuid.uuid4()}_{file_object.filename}")
        file_path = os.path.join(upload_folder, filename)
        file_object.save(file_path)
        logger.info(f"Saved audio file: {file_path}")

        # Perform audio transcription
        transcription = transcribe_audio(file_path)
        logger.info(f"Transcription: {transcription}")

        # Check if this is an add category command
        is_category_command, category_name = detect_category_command(transcription)

        if is_category_command and category_name:
            # Process add category command
            success, message = db_manager.add_category(category_name)

            # Send email notification about category addition
            if email:
                send_email(
                    recipient=email,
                    subject="Expense Category Action",
                    body=f"""
                    <html>
                        <body>
                            <h2>Category Action</h2>
                            <p>Your audio command has been processed.</p>
                            <p>Transcription: <em>{transcription}</em></p>
                            <p>Result: {message}</p>
                        </body>
                    </html>
                    """
                )

            return {
                "success": success,
                "message": message,
                "transcription": transcription,
                "command_type": "add_category",
                "category_name": category_name
            }

        # Extract expense information
        expenses = enhance_with_llm(transcription)
        logger.info(f"Extracted expenses: {expenses}")

        if not expenses:
            return {"success": False, "error": "Could not recognize expenses in the recording."}

        # Saving to the database
        expense_ids = []
        expense_details = []

        for expense in expenses:
            # Determine if category confirmation is needed
            needs_confirmation = False
            predicted_category = None
            category_confidence = 0.0
            alternative_categories = []

            # Example logic for determining if confirmation is needed
            if hasattr(expense, 'category_confidence') and expense.category_confidence < 0.8:
                needs_confirmation = True
                predicted_category = expense.get('category')
                category_confidence = expense.get('category_confidence', 0.0)
                # Add alternative categories if available
                if hasattr(expense, 'alternative_categories'):
                    alternative_categories = expense.alternative_categories

            expense_id = db_manager.add_expense(
                date=expense.get('date', datetime.datetime.now()),
                amount=expense.get('amount'),
                vendor=expense.get('vendor', ''),
                category=expense.get('category', ''),
                description=expense.get('description', ''),
                audio_file_path=file_path,
                transcription=transcription,
                needs_confirmation=needs_confirmation,
                predicted_category=predicted_category,
                category_confidence=category_confidence,
                alternative_categories=alternative_categories,
                notification_callback=send_category_confirmation_notification if needs_confirmation else None
            )

            if expense_id:
                expense_ids.append(expense_id)
                expense_details.append({
                    "date": expense.get('date').isoformat() if isinstance(expense.get('date'),
                                                                          datetime.datetime) else expense.get('date'),
                    "amount": expense.get('amount'),
                    "vendor": expense.get('vendor', ''),
                    "category": expense.get('category', ''),
                    "description": expense.get('description', '')
                })

        # Prepare email content
        if email:
            email_body = f"""
            <html>
                <body>
                    <h2>Expense Recording Confirmation</h2>
                    <p>Your audio message has been processed successfully.</p>
                    <p>Transcription: <em>{transcription}</em></p>
                    <h3>Recorded Expenses:</h3>
                    <ul>
                        {"".join(f"<li>{expense['date'].strftime('%Y-%m-%d') if isinstance(expense['date'], datetime.datetime) else expense['date']}: {expense.get('vendor', 'Unknown')} - £{expense.get('amount', 0)} ({expense.get('category', 'Uncategorized')})</li>" for expense in expenses)}
                    </ul>
                </body>
            </html>
            """

            try:
                email_success = send_email(
                    recipient=email,
                    subject="Expense(s) Recorded Successfully",
                    body=email_body
                )

                if not email_success:
                    logger.warning(f"Failed to send confirmation email to {email}")
            except Exception as e:
                logger.error(f"Error sending confirmation email: {str(e)}")

        # Return success response
        response_data = {
            "success": True,
            "message": "Audio processed successfully",
            "expense_ids": expense_ids,
            "transcription": transcription,
            "expenses": expense_details
        }

        return response_data

    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Failed to process audio: {str(e)}"}


def process_manual_expense(expense_data, db_manager):
    """
    Processes manually entered expense data and saves it to the database.

    Args:
        expense_data: Dictionary with expense data (date, amount, vendor, category, description)
        db_manager: DBManager instance for database interaction

    Returns:
        dict: Dictionary containing processing result (success/error, expense_id)
    """
    try:
        # Validate required fields
        if not expense_data.get('date') or not expense_data.get('amount'):
            return {"success": False, "error": "Date and amount are required fields"}

        # Convert date from string format to datetime object
        try:
            if isinstance(expense_data.get('date'), str):
                expense_date = datetime.datetime.strptime(expense_data.get('date'), '%Y-%m-%d')
            else:
                expense_date = expense_data.get('date')
        except ValueError:
            return {"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}

        # Try to parse amount as float
        try:
            amount = float(expense_data.get('amount'))
        except ValueError:
            return {"success": False, "error": "Invalid amount value"}

        # Determining whether category confirmation is needed
        needs_confirmation = False
        predicted_category = None
        alternative_categories = []

        # For manually entered expenses, confirmation is usually not needed
        # but business logic can be added if necessary

        # Add expense to database
        expense_id = db_manager.add_expense(
            date=expense_date,
            amount=amount,
            vendor=expense_data.get('vendor', ''),
            category=expense_data.get('category', 'Other'),
            description=expense_data.get('description', ''),
            needs_confirmation=needs_confirmation,
            predicted_category=predicted_category,
            alternative_categories=alternative_categories,
            notification_callback=None
        )

        if expense_id:
            return {
                "success": True,
                "message": "Expense saved successfully",
                "expense_id": expense_id
            }
        else:
            return {"success": False, "error": "Failed to save expense"}

    except Exception as e:
        logger.error(f"Error processing manual expense: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Failed to process expense: {str(e)}"}


def process_report_request(report_params, db_manager, email=None):
    """
    Generates expense report based on given parameters.

    Args:
        report_params: Dictionary with report parameters (category, start_date, end_date, group_by, format)
        db_manager: DBManager instance for database interaction
        email: Optional email address to send the report

    Returns:
        dict: Dictionary containing report generation result (success/error, report_id)
    """
    try:
        from app.core.report_generator import generate_report

        # Generate report
        report_file, report_type, format_type = generate_report(
            db_manager,
            report_params.get('category'),
            report_params.get('start_date'),
            report_params.get('end_date'),
            report_params.get('group_by', 'month'),
            report_params.get('format', 'excel')
        )

        # Save report information to database
        report_id = db_manager.add_report(
            report_type=report_type,
            parameters=json.dumps(report_params),
            file_path=report_file
        )

        # Send email with report if email address is provided
        if email:
            with open(report_file, 'rb') as f:
                file_content = f.read()

            send_email(
                recipient=email,
                subject=f"Expense Report: {report_type}",
                body=f"""
                <html>
                    <body>
                        <h2>Expense Report</h2>
                        <p>Please find attached your requested expense report.</p>
                        <p>Report parameters:</p>
                        <ul>
                            <li>Category: {report_params.get('category', 'All')}</li>
                            <li>Period: {report_params.get('start_date', 'All time')} to {report_params.get('end_date', 'Present')}</li>
                            <li>Grouped by: {report_params.get('group_by', 'Month')}</li>
                        </ul>
                    </body>
                </html>
                """,
                attachments={os.path.basename(report_file): file_content}
            )

        return {
            "success": True,
            "message": "Report generated and sent successfully",
            "report_id": report_id,
            "report_file": report_file
        }

    except Exception as e:
        logger.error(f"Error generating report: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Failed to generate report: {str(e)}"}