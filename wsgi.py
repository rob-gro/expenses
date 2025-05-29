import sys
import os

# Ścieżka do aplikacji na AlwaysData
sys.path.insert(0, '/home/robgro/expenses')

# Ustawienia dla AlwaysData
os.environ.setdefault('ENVIRONMENT', 'production')
os.environ.setdefault('ALWAYSDATA_ENV', '1')

try:
    from run import app as application

    # Upewnij się, że katalogi istnieją
    os.makedirs('/home/robgro/expenses/uploads', exist_ok=True)
    os.makedirs('/home/robgro/expenses/reports', exist_ok=True)
    os.makedirs('/home/robgro/expenses/models', exist_ok=True)

except Exception as e:
    # Fallback - stwórz minimalną aplikację dla debugowania
    from flask import Flask

    application = Flask(__name__)


    @application.route('/')
    def debug():
        return f"Import error: {str(e)}"