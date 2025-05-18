from flask import request, jsonify
import os
import uuid
import datetime
import logging
import json
from werkzeug.utils import secure_filename

from app.core.expense_processor import process_audio_file, process_manual_expense
from app.services.transcription import transcribe_audio
from app.nlp.expense_extractor import enhance_with_llm
from app.services.category_service import detect_category_command
from app.services.email_service import send_email, send_category_confirmation_notification
from app.core.report_generator import generate_report
from app.core.expense_learner import ExpenseLearner
from app.database.db_manager import DBManager
from app.config import Config
from app.nlp.report_parser import parse_report_command

# Pobierz logger
logger = logging.getLogger(__name__)

# Inicjalizacja DBManager
db_manager = DBManager(
    host=Config.DB_HOST,
    user=Config.DB_USER,
    password=Config.DB_PASSWORD,
    database=Config.DB_NAME
)

def register_api_routes(app):
    logger.info("Registering API routes...")
    @app.route('/health', methods=['GET'])
    def health_check():
        """Endpoint to check if the service is running"""
        return jsonify({"status": "ok", "timestamp": datetime.datetime.now().isoformat()})

    @app.route('/api/process-audio', methods=['POST'])
    def process_audio():
        """Process audio file, extract expense information and save to database"""
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        try:
            # Save the uploaded file
            filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            logger.info(f"Saved audio file: {file_path}")

            # Transcribe audio using Whisper API
            transcription = transcribe_audio(file_path)
            logger.info(f"Transcription: {transcription}")

            # Check if this is a category command
            is_category_command, category_name = detect_category_command(transcription)

            if is_category_command and category_name:
                # Process category addition command
                success, message = db_manager.add_category(category_name)

                # Send email notification about category action
                recipient = request.form.get('email', app.config['DEFAULT_EMAIL_RECIPIENT'])
                send_email(
                    recipient=recipient,
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

                return jsonify({
                    "success": success,
                    "message": message,
                    "transcription": transcription,
                    "command_type": "add_category"
                })

            # Extract expense information
            expenses = enhance_with_llm(transcription)
            logger.info(f"Extracted expenses: {expenses}")

            if not expenses:
                return jsonify({"error": "Could not recognize expenses in the recording."}), 400

            # Save to database
            expense_ids = []
            expense_details = []
            for expense in expenses:
                # Determine if category confirmation is needed
                needs_confirmation = False
                predicted_category = None
                category_confidence = 0.0
                alternative_categories = []

                # Example logic to determine if confirmation is needed
                # This could be based on model confidence or other factors
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
            recipient = request.form.get('email', app.config['DEFAULT_EMAIL_RECIPIENT'])
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

            # Try to send email, but don't let failure stop the process
            email_success = False
            try:
                email_success = send_email(
                    recipient=recipient,
                    subject="Expense(s) Recorded Successfully",
                    body=email_body
                )
            except Exception as e:
                logger.error(f"Error sending confirmation email: {str(e)}")
                # Continue with success response even if email fails

            # Return success response regardless of email outcome
            response_data = {
                "success": True,
                "message": "Audio processed successfully",
                "expense_ids": expense_ids,
                "transcription": transcription,
                "expenses": expense_details
            }

            # Add info about email status
            if not email_success:
                response_data[
                    "email_status"] = "Email confirmation could not be sent, but expenses were recorded successfully"

            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to process audio: {str(e)}"}), 500

    @app.route('/api/generate-report', methods=['POST'])
    def generate_report_api():
        """Generate expense report based on voice command or parameters"""
        try:
            if 'file' in request.files:
                # Process voice command
                file = request.files['file']
                if file.filename == '':
                    return jsonify({"error": "No selected file"}), 400

                # Save the uploaded file
                filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                # Transcribe audio using Whisper
                transcription = transcribe_audio(file_path)
                logger.info(f"Report request transcription: {transcription}")

                # Parse report parameters from transcription
                report_params = parse_report_command(transcription)
            else:
                # Get report parameters from request body
                report_params = request.json

            # Generate the report
            report_file, report_type, format_type = generate_report(
                db_manager,
                report_params.get('category'),
                report_params.get('start_date'),
                report_params.get('end_date'),
                report_params.get('group_by', 'month'),
                report_params.get('format', 'excel')
            )

            # Save report info to database
            report_id = db_manager.add_report(
                report_type=report_type,
                parameters=json.dumps(report_params),
                file_path=report_file
            )

            # Send email with report
            recipient = request.form.get('email', app.config['DEFAULT_EMAIL_RECIPIENT'])
            with open(report_file, 'rb') as f:
                file_content = f.read()

            send_email(
                recipient=recipient,
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

            return jsonify({
                "success": True,
                "message": "Report generated and sent successfully",
                "report_id": report_id
            })

        except Exception as e:
            logger.error(f"Error generating report: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to generate report: {str(e)}"}), 500

    @app.route('/api/process-manual-expense', methods=['POST'])
    def process_manual_expense():
        """Process manually entered expense and save to database"""
        try:
            # Get expense data from request
            data = request.json

            if not data:
                return jsonify({"error": "No data provided"}), 400

            # Validate required fields
            if not data.get('date') or not data.get('amount'):
                return jsonify({"error": "Date and amount are required fields"}), 400

            # Convert date string to datetime object
            try:
                expense_date = datetime.datetime.strptime(data.get('date'), '%Y-%m-%d')
            except ValueError:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

            # Try to parse amount as float
            try:
                amount = float(data.get('amount'))
            except ValueError:
                return jsonify({"error": "Invalid amount value"}), 400

            # Determine if category needs confirmation - normally this would be
            # for voice-processed expenses, but we could add a confidence model for manual ones too
            needs_confirmation = False
            predicted_category = None
            alternative_categories = []

            # For manual expenses, typically confirmation is not needed,
            # but we could add some business logic here if needed

            # Add expense to database
            expense_id = db_manager.add_expense(
                date=expense_date,
                amount=amount,
                vendor=data.get('vendor', ''),
                category=data.get('category', 'Other'),
                description=data.get('description', ''),
                needs_confirmation=needs_confirmation,
                predicted_category=predicted_category,
                alternative_categories=alternative_categories,
                # We don't pass notification_callback for manual expenses,
                # but we could if needed in the future
                notification_callback=None
            )

            if expense_id:
                return jsonify({
                    "success": True,
                    "message": "Expense saved successfully",
                    "expense_id": expense_id
                })
            else:
                return jsonify({"error": "Failed to save expense"}), 500

        except Exception as e:
            logger.error(f"Error processing manual expense: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to process expense: {str(e)}"}), 500

    @app.route('/api/categories', methods=['GET'])
    def get_categories():
        """Endpoint to get all available expense categories"""
        try:
            categories = db_manager.get_all_categories()
            return jsonify({
                "success": True,
                "categories": categories
            })
        except Exception as e:
            logger.error(f"Error fetching categories: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to fetch categories: {str(e)}"}), 500


    @app.route('/api/view-expenses', methods=['GET'])
    def view_expenses():
        """API endpoint to view expenses with pagination and filtering"""
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        category = request.args.get('category')

        expenses, total = db_manager.get_expenses(
            page=page,
            per_page=per_page,
            category=category
        )

        return jsonify({
            "expenses": expenses,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page  # Ceiling division
        })

    @app.route('/api/get-expense-details/<int:expense_id>', methods=['GET'])
    def get_expense_details(expense_id):
        """Get expense details for confirmation page"""
        expense = db_manager.get_expense(expense_id)
        if expense:
            # Pobierz również oczekujące kategoryzacje
            pending = db_manager.get_pending_categorization(expense_id)

            # Pobierz wszystkie dostępne kategorie
            categories = db_manager.get_all_categories()

            return jsonify({
                "expense": expense,
                "pending": pending,
                "available_categories": categories
            })
        return jsonify({"error": "Expense not found"}), 404


    @app.route('/api/confirm-category', methods=['POST'])
    def confirm_category():
        """Handle category confirmation from user"""
        try:
            data = request.json
            expense_id = data.get('expense_id')
            confirmed_category = data.get('category')

            if not expense_id or not confirmed_category:
                return jsonify({"error": "Missing expense_id or category"}), 400

            # Aktualizuj kategorię wydatku
            db_manager.update_expense(expense_id, category=confirmed_category)

            # Zaktualizuj status w tabeli pending_categorizations
            db_manager.update_pending_categorization(expense_id, status='confirmed')

            learner = ExpenseLearner(db_manager)
            learner.incremental_train(expense_id, confirmed_category)

            return jsonify({"success": True, "message": "Category confirmed successfully"})

        except Exception as e:
            logger.error(f"Error confirming category: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to confirm category: {str(e)}"}), 500

    @app.route('/api/train-expense-model', methods=['POST'])
    def train_expense_model():
        """Admin endpoint to train expense categorization model"""
        try:
            learner = ExpenseLearner(db_manager)
            success = learner.train_model()

            if success:
                return jsonify({"success": True, "message": "Model trained successfully"})
            else:
                return jsonify({"success": False, "message": "Not enough data to train model"}), 400

        except Exception as e:
            logger.error(f"Error training model: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to train model: {str(e)}"}), 500