import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ENVIRONMENT = os.environ.get('ENVIRONMENT', 'prod')

    # Flask settings
    DEBUG = os.environ.get('DEBUG', 'False') == 'True'
    PORT = int(os.environ.get('PORT', 5000))
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # Application root for subdirectory mounting
    APPLICATION_ROOT = '/expenses' if os.environ.get('ALWAYSDATA_ENV') else None

    # Database settings
    DB_HOST = os.environ.get('DB_HOST', 'mysql-robgro.alwaysdata.net')
    DB_USER = os.environ.get('DB_USER', 'robgro')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')

    # Database name based on environment
    DB_NAME = 'robgro_expenses' if ENVIRONMENT in ['prod', 'production'] else 'robgro_test_expenses'

    # Paths based on environment - POPRAWIONE ŚCIEŻKI BEZ /
    if ENVIRONMENT in ['prod', 'production']:
        UPLOAD_FOLDER = '/home/robgro/expenses/uploads'
        REPORT_FOLDER = '/home/robgro/expenses/reports'
        APP_URL = 'https://robgro.dev/expenses'
    else:
        UPLOAD_FOLDER = 'uploads'
        REPORT_FOLDER = 'reports'
        APP_URL = 'http://localhost:5000'

    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # API settings
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')

    # Email settings
    EMAIL_SENDER = os.environ.get('EMAIL_SENDER')
    EMAIL_USER = os.environ.get('EMAIL_USER')
    EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
    SMTP_SERVER = os.environ.get('SMTP_SERVER')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    DEFAULT_EMAIL_RECIPIENT = os.environ.get('DEFAULT_EMAIL_RECIPIENT')

    # Predefined expense categories
    DEFAULT_CATEGORIES = [
        'Fuel',
        'Cosmetics',
        'Groceries',
        'Utilities',
        'Rent',
        'Entertainment',
        'Transportation',
        'Healthcare',
        'Clothing',
        'Education',
        'Other',
        'Office supplies',
        'Alcohol'
    ]

    @classmethod
    def get_db_config(cls):
        if cls.ENVIRONMENT in ['prod', 'production']:
            return {
                'host': 'mysql-robgro.alwaysdata.net',
                'user': 'robgro',
                'password': cls.DB_PASSWORD,
                'database': cls.DB_NAME
            }
        else:
            return {
                'host': cls.DB_HOST,
                'user': cls.DB_USER,
                'password': cls.DB_PASSWORD,
                'database': cls.DB_NAME
            }

    @classmethod
    def validate_config(cls):
        required_vars = [
            'DB_PASSWORD',
            'OPENAI_API_KEY',
            'SECRET_KEY'
        ]
        missing_vars = [var for var in required_vars if not getattr(cls, var)]
        if missing_vars:
            raise EnvironmentError(f"Brak wymaganych zmiennych: {', '.join(missing_vars)}")