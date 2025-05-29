"""
Moduł services zawiera usługi pomocnicze i integracje zewnętrzne używane przez aplikację Expense Tracker.

Ten moduł udostępnia funkcjonalności takie jak wysyłanie e-maili, przetwarzanie audio,
zarządzanie kategoriami, transkrypcję nagrań oraz integrację z Discordem.
"""

import logging

# Importujemy główne funkcjonalności z podmodułów
from app.services.audio_processor import process_audio_file
from app.services.category_service import detect_category_command, translate_category_with_llm, add_category
from app.services.email_service import (
    send_email,
    send_confirmation_email,
    send_category_addition_email,
    send_category_confirmation_notification,
    try_generate_report_from_text
)
from app.services.transcription import transcribe_audio, convert_audio_to_wav


# Eksportujemy funkcje, które powinny być dostępne z poziomu pakietu
__all__ = [
    # Audio processing
    'process_audio_file',

    # Category services
    'detect_category_command',
    'translate_category_with_llm',
    'add_category',

    # Email services
    'send_email',
    'send_confirmation_email',
    'send_category_addition_email',
    'send_category_confirmation_notification',
    'try_generate_report_from_text',

    # Transcription
    'transcribe_audio',
    'convert_audio_to_wav',

    # Discord
    'run_discord_bot'
]

# Metadane pakietu
__version__ = '1.0.0'

# Konfiguracja usług w momencie importu


logger = logging.getLogger(__name__)
logger.info("Initializing services module")


# Opcjonalnie możesz dodać kod inicjalizujący dla usług
# Na przykład, sprawdzenie dostępności kluczy API lub konfiguracji
def _validate_service_requirements():
    """
    Sprawdza, czy wszystkie wymagane konfiguracje usług są dostępne.
    Loguje ostrzeżenia, jeśli któraś wymagana konfiguracja jest brakująca.
    """
    from app.config import Config

    required_configs = {
        'email_service': [
            ('EMAIL_SENDER', Config.EMAIL_SENDER),
            ('EMAIL_USER', Config.EMAIL_USER),
            ('EMAIL_PASSWORD', Config.EMAIL_PASSWORD),
            ('SMTP_SERVER', Config.SMTP_SERVER),
            ('SMTP_PORT', Config.SMTP_PORT)
        ],
        'openai_service': [
            ('OPENAI_API_KEY', Config.OPENAI_API_KEY)
        ],
        'discord_service': [
            ('DISCORD_BOT_TOKEN', Config.DISCORD_BOT_TOKEN)
        ]
    }

    for service_name, configs in required_configs.items():
        missing_configs = [name for name, value in configs if not value]

        if missing_configs:
            logger.warning(f"Service '{service_name}' is missing required configurations: {', '.join(missing_configs)}")
        else:
            logger.info(f"Service '{service_name}' configuration validated successfully")


# Walidacja wymagań usług podczas inicjalizacji
try:
    _validate_service_requirements()
except Exception as e:
    logger.warning(f"Could not validate service requirements: {e}")