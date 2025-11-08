#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WSGI entry point for AlwaysData hosting
"""

import sys
import os
import warnings
import logging

warnings.filterwarnings('ignore')

# Add project path to Python path
sys.path.insert(0, '/home/robgro/expenses')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/robgro/expenses/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# DISABLE HEAVY MODULES FOR ALWAYSDATA (keep Qdrant enabled for vector model)
os.environ['DISABLE_SPACY'] = 'true'
os.environ['DISABLE_DISCORD'] = 'true'
os.environ['ALWAYSDATA_ENV'] = 'true'
os.environ['MINIMAL_MODE'] = 'true'

logger.info("=" * 60)
logger.info("Starting AlwaysData WSGI application")
logger.info("=" * 60)

# Environment variables are set in AlwaysData configuration
# No need to load from .env file
logger.info("Using environment variables from AlwaysData configuration")

# Import the real application
try:
    from app import create_app
    app = create_app()

    # Middleware to fix SCRIPT_NAME for AlwaysData subdirectory mounting
    class PrefixMiddleware:
        def __init__(self, app, prefix=''):
            self.app = app
            self.prefix = prefix

        def __call__(self, environ, start_response):
            # Set SCRIPT_NAME so Flask generates correct URLs
            environ['SCRIPT_NAME'] = self.prefix
            return self.app(environ, start_response)

    # Wrap application with middleware
    application = PrefixMiddleware(app, prefix='/expenses')
    logger.info("✅ Application created successfully with /expenses prefix")
except Exception as e:
    logger.error(f"❌ Failed to create application: {e}", exc_info=True)

    # Fallback minimal application
    from flask import Flask, jsonify
    application = Flask(__name__)

    error_message = str(e)

    @application.route('/')
    def fallback_index():
        return jsonify({
            'status': 'error',
            'message': 'Application failed to initialize',
            'error': error_message,
            'help': 'Check logs at /home/robgro/expenses/app.log'
        }), 500

    logger.error("Using fallback application")

logger.info("=" * 60)
logger.info("WSGI application ready")
logger.info("=" * 60)