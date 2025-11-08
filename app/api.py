from flask import Blueprint, request, jsonify, current_app
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

# Create Blueprint
api_bp = Blueprint('api', __name__)

# Initialize services
config = Config()
db_manager = DBManager(
    host=Config.DB_HOST,
    user=Config.DB_USER,
    password=Config.DB_PASSWORD,
    database=config.DB_NAME
)

report_service = ReportService(db_manager, config.UPLOAD_FOLDER)
expense_service = ExpenseService(db_manager, config.UPLOAD_FOLDER)


# Health check endpoint (without /api prefix)
@api_bp.route('/health', methods=['GET'])
def health_check():
    """Endpoint to check if the service is running"""
    return jsonify({"status": "ok", "timestamp": datetime.datetime.now().isoformat()})


@api_bp.route('/debug-wsgi', methods=['GET'])
def debug_wsgi():
    """Debug endpoint to see what Flask receives from the server"""
    import os
    from flask import request

    debug_info = {
        "request_url": request.url,
        "request_path": request.path,
        "request_full_path": request.full_path,
        "request_script_root": request.script_root,
        "request_url_root": request.url_root,
        "blueprint": request.blueprint,
        "endpoint": request.endpoint,
        "environ": {
            "SCRIPT_NAME": request.environ.get('SCRIPT_NAME', ''),
            "PATH_INFO": request.environ.get('PATH_INFO', ''),
            "REQUEST_URI": request.environ.get('REQUEST_URI', ''),
            "HTTP_HOST": request.environ.get('HTTP_HOST', ''),
            "SERVER_NAME": request.environ.get('SERVER_NAME', ''),
            "uwsgi_mountpoint": request.environ.get('uwsgi.mountpoint', 'not set')
        },
        "os_environ": {
            "ALWAYSDATA_ENV": os.environ.get('ALWAYSDATA_ENV', 'not set'),
            "ENVIRONMENT": os.environ.get('ENVIRONMENT', 'not set')
        }
    }

    return jsonify(debug_info)


@api_bp.route('/process-audio', methods=['POST'])
def process_audio():
    """Process audio file, extract expense information and save to database"""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        email = request.form.get('email', current_app.config['DEFAULT_EMAIL_RECIPIENT'])
        result = expense_service.process_audio_expense(file, email)

        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"Error in process_audio endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@api_bp.route('/generate-report', methods=['POST'])
def generate_report_api():
    """Generate expense report based on voice command or parameters"""
    try:
        if 'file' in request.files:
            # Voice command - email from form data
            email = request.form.get('email', '').strip()
            if not email:
                email = current_app.config['DEFAULT_EMAIL_RECIPIENT']
            file = request.files['file']
            if file.filename == '':
                return jsonify({"error": "No selected file"}), 400

            result = report_service.generate_report_from_voice(file, email)
        else:
            # JSON parameters - email from JSON
            report_params = request.json
            email = report_params.get('email', '').strip()
            if not email:
                email = current_app.config['DEFAULT_EMAIL_RECIPIENT']
            result = report_service.generate_report_from_params(report_params, email)

        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"Error in generate_report endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@api_bp.route('/process-manual-expense', methods=['POST'])
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


@api_bp.route('/categories', methods=['GET'])
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


@api_bp.route('/view-expenses', methods=['GET'])
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


@api_bp.route('/get-expense-details/<int:expense_id>', methods=['GET'])
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


@api_bp.route('/confirm-category', methods=['POST'])
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


@api_bp.route('/train-expense-model', methods=['POST'])
def train_expense_model():
    """Admin endpoint to train expense categorization model (async)"""
    try:
        import threading

        # Start training in background thread
        def train_in_background():
            try:
                expense_service.train_expense_model()
            except Exception as e:
                logger.error(f"Background training failed: {str(e)}", exc_info=True)

        thread = threading.Thread(target=train_in_background, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "message": "Model training started in background. This may take 3-5 minutes. You will receive an email when complete.",
            "status": "training"
        }), 200

    except Exception as e:
        logger.error(f"Error starting training: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to start training: {str(e)}"}), 500


@api_bp.route('/model-metrics', methods=['GET'])
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


# Legacy compatibility function
def register_api_routes(app):
    """Legacy function for backward compatibility"""
    logger.info("Registering API routes...")