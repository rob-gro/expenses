import os
import logging

# Importujemy główne funkcjonalności, aby udostępnić je na poziomie pakietu
from app.core.expense_learner import ExpenseLearner
from app.core.report_generator import generate_report, generate_excel_report, generate_pdf_report, generate_csv_report
from app.core.expense_processor import process_audio_file, process_manual_expense

# Oznacza, które funkcje i klasy są dostępne przy importowaniu z pakietu
__all__ = [
    'ExpenseLearner',             # Klasa do uczenia maszynowego kategoryzacji wydatków
    'generate_report',            # Główna funkcja generująca raporty
    'generate_excel_report',      # Funkcja generująca raporty Excel
    'generate_pdf_report',        # Funkcja generująca raporty PDF
    'generate_csv_report',        # Funkcja generująca raporty CSV
    'process_audio_file',         # Funkcja przetwarzająca nagrania wydatków
    'process_manual_expense'      # Funkcja przetwarzająca ręcznie wprowadzone wydatki
]

# Informacja o wersji tego komponentu
__version__ = '1.0.0'


logger = logging.getLogger(__name__)

def _ensure_model_directory_exists():
    """Sprawdza, czy katalog na modele ML istnieje i tworzy go w razie potrzeby"""
    model_dir = 'models'
    if not os.path.exists(model_dir):
        os.makedirs(model_dir, exist_ok=True)
        logger.info(f"Created model directory: {model_dir}")

try:
    _ensure_model_directory_exists()
except Exception as e:
    logger.warning(f"Could not ensure model directory exists: {e}")