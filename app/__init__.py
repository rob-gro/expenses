"""
Expense Tracker Pro - aplikacja do śledzenia wydatków z rozpoznawaniem mowy
"""

from flask import Flask
from flask_cors import CORS
import os
import logging

__version__ = '1.0.0'

# Konfiguracja podstawowego loggera
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def create_app(config_object=None):
    """
    Fabryka aplikacji - tworzy i konfiguruje aplikację Flask

    Args:
        config_object: Obiekt konfiguracyjny do załadowania

    Returns:
        Skonfigurowana instancja aplikacji Flask
    """
    # Inicjalizacja aplikacji Flask
    app = Flask(__name__,
                static_folder='../static',
                template_folder='../templates')

    # Włącz CORS
    CORS(app)

    # Załaduj konfigurację
    if config_object:
        app.config.from_object(config_object)
    else:
        # Domyślnie, importuj konfigurację z app.config
        from app.config import Config
        app.config.from_object(Config)

        # Log environment info
        logger.info("=" * 60)
        logger.info(f"🚀 STARTING APPLICATION")
        logger.info(f"📌 ENVIRONMENT: {Config.ENVIRONMENT}")
        logger.info(f"🗄️  DATABASE: {Config.DB_NAME}")
        logger.info(f"🔗 DATABASE HOST: {Config.DB_HOST}")
        logger.info(f"🌐 APP URL: {Config.APP_URL}")
        logger.info("=" * 60)

    # Upewnij się, że katalogi istnieją
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)

    # Importy wymaganych modułów
    with app.app_context():
        # Zarejestruj trasy API
        from app.api import register_api_routes
        register_api_routes(app)

        # Zarejestruj trasy widoków
        from app.views import register_view_routes
        register_view_routes(app)

    logger.info(f"Application initialized with config: {config_object.__name__ if config_object else 'Config'}")

    return app


# Funkcjonalności eksportowane na poziom pakietu
__all__ = ['create_app']