import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, '/home/robgro/www/expenses')

try:
    from run import app as application

    if __name__ == "__main__":
        application.run()

except ImportError as e:
    # Fallback do prostej aplikacji w przypadku problemów z importem
    from flask import Flask

    application = Flask(__name__)


    @application.route('/')
    def error():
        return f"Import Error: {str(e)}<br>Check logs for details"

# load_dotenv()
#
# sys.path.insert(0, '/home/robgro/www/expenses')
#
# try:
#     # Test podstawowych importów
#     import flask
#     import pymysql
#
#     # Test problematycznych (bez ładowania)
#     available_libs = []
#     try:
#         import spacy
#
#         available_libs.append(f"spaCy: {spacy.__version__}")
#     except:
#         available_libs.append("spaCy: ERROR")
#
#     try:
#         import discord
#
#         available_libs.append(f"Discord: {discord.__version__}")
#     except:
#         available_libs.append("Discord: ERROR")
#
#     # Minimalna aplikacja Flask bez problematycznych importów
#     from flask import Flask
#
#     application = Flask(__name__)
#
#
#     @application.route('/')
#     def status():
#         return f"Python: {sys.version}<br>Flask: {flask.__version__}<br>" + "<br>".join(available_libs)
#
#
#     @application.route('/test')
#     def test():
#         return "Basic Flask app works!"
#
# except Exception as e:
#     from flask import Flask
#
#     application = Flask(__name__)
#
#
#     @application.route('/')
#     def error():
#         return f"Import Error: {str(e)}<br>Python: {sys.version}"