import os
import logging
import threading
import json
import schedule
import time
import sys

from flask import Flask
from flask_cors import CORS
import spacy

from app.api import register_api_routes
from app.views import register_view_routes
from app.database.db_manager import DBManager
from app.core.expense_learner import ExpenseLearner
from app.services.discord_bot import run_discord_bot
from app.config import Config

# Sprawdź konfigurację
try:
    Config.validate_config()
except Exception as e:
    print(f"Błąd konfiguracji: {e}")
    sys.exit(1)

# Inicjalizacja Flask
app = Flask(__name__)
CORS(app)
app.config.from_object(Config)

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Inicjalizacja bazy danych
config = Config()
db_name = config.DB_NAME

db_manager = DBManager(
    host=app.config['DB_HOST'],
    user=app.config['DB_USER'],
    password=app.config['DB_PASSWORD'],
    database=db_name
)

# Inicjalizacja modeli spaCy
nlp = spacy.load('en_core_web_sm')
nlp_pl = spacy.load('pl_core_news_sm')

# Tworzenie katalogów
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)

# Rejestracja tras API i widoków
register_api_routes(app)
register_view_routes(app)

# Funkcja do planowania treningu modelu
def schedule_model_training():
    def train_job():
        logger.info("Running scheduled model training")
        learner = ExpenseLearner(db_manager)
        learner.train_model()

    schedule.every().monday.at("03:00").do(train_job)

    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(3600)  # Sprawdzaj co godzinę

    # Uruchom w osobnym wątku
    threading.Thread(target=run_scheduler, daemon=True).start()

# Funkcja do uruchomienia bota Discord
def start_discord_bot():
    """Start Discord bot in a separate thread"""
    if os.environ.get('ALWAYSDATA_ENV'):
        logger.info("Discord bot disabled on AlwaysData")
        return

    try:
        from app.services.discord_bot import run_discord_bot
        logger.info("Starting Discord bot in background thread")
        discord_thread = threading.Thread(target=run_discord_bot)
        discord_thread.daemon = True
        discord_thread.start()
    except ImportError:
        logger.warning("Discord bot module not found - bot will not start")
    except Exception as e:
        logger.error(f"Error starting Discord bot: {str(e)}")


if __name__ == '__main__':
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.config['DEBUG']:
        try:
            schedule_model_training()
            logger.info("Model training scheduler started")
        except ImportError:
            logger.warning("Schedule module not found - model training scheduler not started")
        except Exception as e:
            logger.error(f"Error starting model training scheduler: {str(e)}")

        # Discord bot - wyłączony na AlwaysData
        try:
            start_discord_bot()
            logger.info("Discord bot started")
        except Exception as e:
            logger.error(f"Error starting Discord bot: {str(e)}", exc_info=True)

    # Uruchom aplikację Flask
    logger.info(f"Starting Flask application on port {app.config['PORT']}")
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=app.config['PORT'])