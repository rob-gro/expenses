import os
import logging

from app.database.db_manager import DBManager

# List of public components exported by this package
__all__ = ['DBManager']

logger = logging.getLogger(__name__)

def _ensure_database_directories():
    """
    Checks and creates necessary directories for the database.
    Used internally during package initialization only.
    """
    try:
        # Directory for database files (if SQLite is used)
        db_dir = os.path.join(os.getcwd(), 'data')
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")
    except Exception as e:
        logger.warning(f"Failed to create database directories: {e}")

# Run initialization when the package is loaded
_ensure_database_directories()

__version__ = '1.0.0'