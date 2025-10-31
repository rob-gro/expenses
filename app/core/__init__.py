import os
import logging

# Import the main functionalities to expose them at the package level
from app.core.expense_learner import ExpenseLearner
from app.core.report_generator import generate_report, generate_excel_report, generate_pdf_report, generate_csv_report
from app.core.expense_processor import process_audio_file, process_manual_expense

# Indicates which functions and classes are available when importing from the package
__all__ = [
    'ExpenseLearner',
    'generate_report',
    'generate_excel_report',
    'generate_pdf_report',
    'generate_csv_report',
    'process_audio_file',
    'process_manual_expense'
]

# Information about the version of this component
__version__ = '1.0.0'


logger = logging.getLogger(__name__)

def _ensure_model_directory_exists():
    """Checks if the directory for ML models exists and creates it if necessary"""
    model_dir = 'models'
    if not os.path.exists(model_dir):
        os.makedirs(model_dir, exist_ok=True)
        logger.info(f"Created model directory: {model_dir}")

try:
    _ensure_model_directory_exists()
except Exception as e:
    logger.warning(f"Could not ensure model directory exists: {e}")