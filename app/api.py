from flask import request, jsonify
import datetime
import logging
import json

from app.services.expense_service import ExpenseService
from app.core.report_generator import generate_report
from app.database.db_manager import DBManager
from app.config import Config
from app.nlp.report_parser import parse_report_command
from app.services.report_service import ReportService

# Configure logging
logger = logging.getLogger(__name__)

# Initialize services
config = Config()
db_manager = DBManager(
    host=Config.DB_HOST,
    user=Config.DB_USER,
    password=Config.DB_PASSWORD,
    database=config.DB_NAME
)

report_service = ReportService(db_manager, config.UPLOAD_FOLDER)


def register_api_routes(app):
    logger.info("Registering API routes...")

    # Initialize expense service with config
    expense_service = ExpenseService(db_manager, config.UPLOAD_FOLDER)

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
            email = request.form.get('email', app.config['DEFAULT_EMAIL_RECIPIENT'])
            result = expense_service.process_audio_expense(file, email)

            status_code = 200 if result.get('success') else 400
            return jsonify(result), status_code

        except Exception as e:
            logger.error(f"Error in process_audio endpoint: {str(e)}", exc_info=True)
            return jsonify({"error": f"Internal server error: {str(e)}"}), 500

    @app.route('/api/generate-report', methods=['POST'])
    def generate_report_api():
        """Generate expense report based on voice command or parameters"""
        try:
            if 'file' in request.files:
                # Voice command - email from form data
                email = request.form.get('email', '').strip()
                if not email:
                    email = app.config['DEFAULT_EMAIL_RECIPIENT']
                file = request.files['file']
                if file.filename == '':
                    return jsonify({"error": "No selected file"}), 400

                result = report_service.generate_report_from_voice(file, email)
            else:
                # JSON parameters - email from JSON
                report_params = request.json
                email = report_params.get('email', '').strip()
                if not email:
                    email = app.config['DEFAULT_EMAIL_RECIPIENT']
                result = report_service.generate_report_from_params(report_params, email)

            status_code = 200 if result.get('success') else 400
            return jsonify(result), status_code

        except Exception as e:
            logger.error(f"Error in generate_report endpoint: {str(e)}", exc_info=True)
            return jsonify({"error": f"Internal server error: {str(e)}"}), 500

    @app.route('/api/process-manual-expense', methods=['POST'])
    def process_manual_expense():
        """Process manually entered expense and save to database"""
        try:
            data = request.json
            if not data:
                return jsonify({"error": "No data provided"}), 400

            result = expense_service.process_manual_expense(data)
            status_code = 200 if result.get('success') else 400
            return jsonify(result), status_code

        except Exception as e:
            logger.error(f"Error in process_manual_expense endpoint: {str(e)}", exc_info=True)
            return jsonify({"error": f"Internal server error: {str(e)}"}), 500

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
        try:
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
                "total_pages": (total + per_page - 1) // per_page
            })

        except Exception as e:
            logger.error(f"Error in view_expenses endpoint: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to retrieve expenses: {str(e)}"}), 500

    @app.route('/api/get-expense-details/<int:expense_id>', methods=['GET'])
    def get_expense_details(expense_id):
        """Get expense details for confirmation page"""
        try:
            details = expense_service.get_expense_details(expense_id)
            if details:
                return jsonify(details)
            return jsonify({"error": "Expense not found"}), 404

        except Exception as e:
            logger.error(f"Error getting expense details: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to get expense details: {str(e)}"}), 500

    @app.route('/api/confirm-category', methods=['POST'])
    def confirm_category():
        """Handle category confirmation from user"""
        try:
            data = request.json
            expense_id = data.get('expense_id')
            confirmed_category = data.get('category')

            result = expense_service.confirm_category(expense_id, confirmed_category)
            status_code = 200 if result.get('success') else 400
            return jsonify(result), status_code

        except Exception as e:
            logger.error(f"Error in confirm_category endpoint: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to confirm category: {str(e)}"}), 500

    @app.route('/api/train-expense-model', methods=['POST'])
    def train_expense_model():
        """Admin endpoint to train expense categorization model"""
        try:
            result = expense_service.train_expense_model()
            status_code = 200 if result.get('success') else 400
            return jsonify(result), status_code

        except Exception as e:
            logger.error(f"Error in train_expense_model endpoint: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to train model: {str(e)}"}), 500

    @app.route('/api/model-metrics', methods=['GET'])
    def get_model_metrics():
        """Get model training history and metrics"""
        try:
            with db_manager._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, timestamp, accuracy, samples_count, 
                               categories_count, training_type, notes
                        FROM model_metrics
                        ORDER BY timestamp DESC
                        LIMIT 50
                    """)
                    metrics = cursor.fetchall()

                    # Konwertuj timestamp na string
                    for m in metrics:
                        m['timestamp'] = m['timestamp'].isoformat()

                    # Pobierz najnowszą macierz pomyłek
                    if metrics:
                        cursor.execute("""
                            SELECT confusion_matrix
                            FROM model_metrics
                            ORDER BY timestamp DESC
                            LIMIT 1
                        """)
                        latest = cursor.fetchone()
                        confusion_data = json.loads(latest['confusion_matrix'])
                    else:
                        confusion_data = {}

                    return jsonify({
                        "success": True,
                        "metrics": metrics,
                        "confusion_data": confusion_data,
                        "current_accuracy": metrics[0]['accuracy'] if metrics else None
                    })
        except Exception as e:
            logger.error(f"Error fetching model metrics: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to fetch metrics: {str(e)}"}), 500