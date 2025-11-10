import os
import logging
import threading
import schedule
import time
import sys

from app import create_app
from app.database.db_manager import DBManager
from app.core.expense_learner import ExpenseLearner
from app.config import Config

# Sprawdź konfigurację
try:
    Config.validate_config()
except Exception as e:
    print(f"Błąd konfiguracji: {e}")
    sys.exit(1)

# Inicjalizacja Flask używając factory pattern
app = create_app()

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

# Funkcja do planowania treningu modelu
def schedule_model_training():
    def train_job():
        logger.info("Running scheduled model training - using Qdrant vector model")

        training_success = False

        try:
            from app.core.vector_expense_learner import QdrantExpenseLearner
            learner = QdrantExpenseLearner(db_manager)
            training_success = learner.train_model()
            logger.info("Scheduled training completed using Qdrant vector model")
        except ImportError as e:
            logger.error(f"CRITICAL: Qdrant libraries not installed: {str(e)}")
            logger.error("Training aborted - Qdrant is required!")
            return
        except Exception as e:
            logger.error(f"Error during Qdrant training: {str(e)}", exc_info=True)
            return

        # Send email notification after training
        if training_success:
            try:
                from app.services.email_service import send_email

                # Get latest metrics
                metrics = db_manager.get_latest_model_metrics()

                if metrics:
                    # Extract confusion matrix data
                    confusion_data = metrics.get('confusion_matrix', {})
                    if isinstance(confusion_data, str):
                        import json
                        confusion_data = json.loads(confusion_data)

                    cv_scores = confusion_data.get('cv_scores', [])
                    cv_scores_str = ', '.join([f"{score:.4f}" for score in cv_scores]) if cv_scores else 'N/A'

                    # Format email body
                    email_body = f"""
                    <html>
                        <body>
                            <h2>Model Training Completed Successfully</h2>
                            <p>The scheduled model training has been completed.</p>

                            <h3>Training Results:</h3>
                            <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse;">
                                <tr>
                                    <td><strong>Training Type:</strong></td>
                                    <td>{metrics.get('training_type', 'N/A')}</td>
                                </tr>
                                <tr>
                                    <td><strong>Accuracy:</strong></td>
                                    <td>{metrics.get('accuracy', 0):.4f} ({metrics.get('accuracy', 0)*100:.2f}%)</td>
                                </tr>
                                <tr>
                                    <td><strong>Samples Count:</strong></td>
                                    <td>{metrics.get('samples_count', 0)}</td>
                                </tr>
                                <tr>
                                    <td><strong>Categories Count:</strong></td>
                                    <td>{metrics.get('categories_count', 0)}</td>
                                </tr>
                                <tr>
                                    <td><strong>Cross-Validation Scores:</strong></td>
                                    <td>{cv_scores_str}</td>
                                </tr>
                                <tr>
                                    <td><strong>Training Date:</strong></td>
                                    <td>{metrics.get('created_at', 'N/A')}</td>
                                </tr>
                                <tr>
                                    <td><strong>Notes:</strong></td>
                                    <td>{metrics.get('notes', 'N/A')}</td>
                                </tr>
                            </table>

                            <p style="margin-top: 20px;">
                                <small>This is an automated message from your Expense Tracking System.</small>
                            </p>
                        </body>
                    </html>
                    """

                    # Send email
                    send_email(
                        recipient=Config.DEFAULT_EMAIL_RECIPIENT,
                        subject=f"Model Training Completed - Accuracy: {metrics.get('accuracy', 0)*100:.2f}%",
                        body=email_body
                    )
                    logger.info("Training completion email sent successfully")
                else:
                    logger.warning("Could not retrieve metrics to send email notification")

            except Exception as e:
                logger.error(f"Error sending training completion email: {str(e)}", exc_info=True)

    schedule.every().sunday.at("13:00").do(train_job)

    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(3600)

    threading.Thread(target=run_scheduler, daemon=True).start()

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

        try:
            start_discord_bot()
            logger.info("Discord bot started")
        except Exception as e:
            logger.error(f"Error starting Discord bot: {str(e)}", exc_info=True)

    # Uruchom aplikację Flask
    logger.info(f"Starting Flask application on port {app.config['PORT']}")
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=app.config['PORT'])