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

    from app.config import Config

    if os.environ.get('ALWAYSDATA_ENV'):
        static_url_path = '/expenses/static'
    else:
        # Locally - always without prefix
        static_url_path = '/static'

    app = Flask(__name__,
                static_folder='../static',
                static_url_path=static_url_path,
                template_folder='../templates')

    CORS(app)

    if config_object:
        app.config.from_object(config_object)
    else:
        from app.config import Config
        app.config.from_object(Config)

        # Log environment info
        logger.info("=" * 60)
        logger.info(f"STARTING APPLICATION")
        logger.info(f"ENVIRONMENT: {Config.ENVIRONMENT}")
        logger.info(f"DATABASE: {Config.DB_NAME}")
        logger.info(f"DATABASE HOST: {Config.DB_HOST}")
        logger.info(f"APP URL: {Config.APP_URL}")
        logger.info("=" * 60)

    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)

    with app.app_context():

        from app.api import api_bp
        from app.views import views_bp

        # Determine URL prefix based on environment
        # IMPORTANT:
        # - AlwaysData serves app under /expenses mountpoint (handled by server)
        # - Localhost ALWAYS runs without prefix (regardless of ENVIRONMENT setting)
        if os.environ.get('ALWAYSDATA_ENV'):
            logger.info("AlwaysData production - NO prefix (server handles /expenses mountpoint)")
            # Register blueprints WITHOUT prefix - AlwaysData mountpoint handles it
            app.register_blueprint(views_bp)
            app.register_blueprint(api_bp, url_prefix='/api')
        else:
            logger.info(f"Localhost ({app.config.get('ENVIRONMENT', 'unknown')}) - NO prefix")
            # Register blueprints WITHOUT prefix for localhost
            app.register_blueprint(views_bp)
            app.register_blueprint(api_bp, url_prefix='/api')

    logger.info(f"Application initialized with config: {config_object.__name__ if config_object else 'Config'}")

    return app

__all__ = ['create_app']