import os
import logging

from app.database.db_manager import DBManager

# Lista publicznych komponentów eksportowanych przez ten pakiet
__all__ = ['DBManager']

# Inicjalizacja loggera
logger = logging.getLogger(__name__)

def _ensure_database_directories():
    """
    Sprawdza i tworzy niezbędne katalogi dla bazy danych.
    Używane tylko wewnętrznie przy inicjalizacji pakietu.
    """
    try:
        # Katalog na pliki bazy (jeśli używany jest SQLite)
        db_dir = os.path.join(os.getcwd(), 'data')
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")
    except Exception as e:
        logger.warning(f"Failed to create database directories: {e}")

# Uruchom inicjalizację podczas ładowania pakietu
_ensure_database_directories()

# Eksportuj wersję pakietu
__version__ = '1.0.0'