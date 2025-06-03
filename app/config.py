import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        load_dotenv()
        self.ENVIRONMENT = os.environ.get('ENVIRONMENT', 'prod')

        print(f"DEBUG: ENVIRONMENT = '{self.ENVIRONMENT}'")

        if self.ENVIRONMENT in ['prod', 'production']:
            self.DB_NAME = 'robgro_expenses'
            self.UPLOAD_FOLDER = '/home/robgro/www/expenses/uploads'
            self.REPORT_FOLDER = '/home/robgro/www/expenses/reports'
            self.APP_URL = 'https://robgro.dev/expenses'
            print(f"DEBUG: Using production DB: {self.DB_NAME}")
        else:
            self.DB_NAME = 'robgro_test_expenses'
            self.UPLOAD_FOLDER = 'uploads'
            self.REPORT_FOLDER = 'reports'
            self.APP_URL = 'http://localhost:5000'
            print(f"DEBUG: Using test DB: {self.DB_NAME}")

    # Flask settings (class variables)
    DEBUG = os.environ.get('DEBUG', 'True') == 'True'
    PORT = int(os.environ.get('PORT', 5000))
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # Database settings
    DB_HOST = os.environ.get('DB_HOST')
    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')

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
        'Fuel',  # Paliwo
        'Cosmetics',
        'Groceries',  # Żywność
        'Utilities',  # Media
        'Rent',  # Czynsz
        'Entertainment',  # Rozrywka
        'Transportation',  # Transport
        'Healthcare',  # Opieka zdrowotna
        'Clothing',  # Ubrania
        'Education',  # Edukacja
        'Other',  # Inne
        'Office supplies',  # mat. biurowe
        "Alcohol"  # Alk
    ]

    @classmethod
    def get_db_config(cls):
        config = cls()
        if config.ENVIRONMENT in ['prod', 'production']:
            return {
                'host': 'mysql-robgro.alwaysdata.net',
                'user': 'robgro',
                'password': cls.DB_PASSWORD,
                'database': config.DB_NAME
            }
        else:
            return {
                'host': cls.DB_HOST,
                'user': cls.DB_USER,
                'password': cls.DB_PASSWORD,
                'database': config.DB_NAME
            }

    @classmethod
    def validate_config(cls):
        required_vars = [
            'DB_HOST',
            'DB_USER',
            'DB_PASSWORD',
            'OPENAI_API_KEY',
            'SECRET_KEY',
            'EMAIL_PASSWORD',
            'DISCORD_BOT_TOKEN'
        ]
        missing_vars = [var for var in required_vars if not getattr(cls, var)]
        if missing_vars:
            raise EnvironmentError(f"Brak wymaganych zmiennych: {', '.join(missing_vars)}")