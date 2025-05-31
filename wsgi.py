# import sys
# import os
#
# # Ścieżka do aplikacji
# sys.path.insert(0, '/home/robgro/www/expenses')
#
# # Zmienne środowiskowe dla AlwaysData
# os.environ.setdefault('ENVIRONMENT', 'production')
# os.environ.setdefault('ALWAYSDATA_ENV', '1')
#
# try:
#     from app import create_app
#     from app.config import Config
#
#     application = create_app(Config)
#
# except Exception as e:
#     from flask import Flask
#
#     application = Flask(__name__)
#
#
#     @application.route('/')
#     def debug():
#         return f"Error: {str(e)}"

import sys
import os

sys.path.insert(0, '/home/robgro/www/expenses')
os.environ.setdefault('ENVIRONMENT', 'production')
os.environ.setdefault('ALWAYSDATA_ENV', '1')

try:
    # Test podstawowych importów
    import flask
    import pymysql

    # Test problematycznych (bez ładowania)
    available_libs = []
    try:
        import spacy

        available_libs.append(f"spaCy: {spacy.__version__}")
    except:
        available_libs.append("spaCy: ERROR")

    try:
        import discord

        available_libs.append(f"Discord: {discord.__version__}")
    except:
        available_libs.append("Discord: ERROR")

    # Minimalna aplikacja Flask bez problematycznych importów
    from flask import Flask

    application = Flask(__name__)


    @application.route('/')
    def status():
        return f"Python: {sys.version}<br>Flask: {flask.__version__}<br>" + "<br>".join(available_libs)


    @application.route('/test')
    def test():
        return "Basic Flask app works!"

except Exception as e:
    from flask import Flask

    application = Flask(__name__)


    @application.route('/')
    def error():
        return f"Import Error: {str(e)}<br>Python: {sys.version}"