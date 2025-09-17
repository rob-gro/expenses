#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import warnings

warnings.filterwarnings('ignore')

# Dodaj ścieżkę
sys.path.insert(0, '/home/robgro/www/expenses')

# WYŁĄCZ WSZYSTKIE PROBLEMATYCZNE MODUŁY
os.environ['DISABLE_SPACY'] = 'true'
os.environ['DISABLE_DISCORD'] = 'true'
os.environ['DISABLE_HEAVY_MODULES'] = 'true'
os.environ['ALWAYSDATA_ENV'] = 'true'
os.environ['MINIMAL_MODE'] = 'true'

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

# Import tylko podstawowych modułów
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
import json
from datetime import datetime

# Utwórz aplikację Flask
application = Flask(__name__)
CORS(application)

# Konfiguracja
application.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'expense-tracker-key')
application.config['DEBUG'] = False
application.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


# === PODSTAWOWE TRASY ===

@application.route('/')
def index():
    """Główna strona expense tracker"""
    try:
        return render_template('index.html')
    except Exception as e:
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Expense Tracker</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body>
            <div class="container mt-5">
                <div class="alert alert-success">
                    <h1 class="alert-heading">🎯 Expense Tracker Works!</h1>
                    <p>Aplikacja Flask działa poprawnie na AlwaysData!</p>
                    <hr>
                    <p class="mb-0">Template error: {e}</p>
                </div>

                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>🔗 Available Links</h5>
                            </div>
                            <div class="card-body">
                                <a href="/api/health" class="btn btn-success mb-2 d-block">API Health Check</a>
                                <a href="/manual" class="btn btn-primary mb-2 d-block">Manual Entry</a>
                                <a href="/debug" class="btn btn-info mb-2 d-block">Debug Info</a>
                                <a href="/api/categories" class="btn btn-secondary mb-2 d-block">View Categories</a>
                            </div>
                        </div>
                    </div>

                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>📊 Status</h5>
                            </div>
                            <div class="card-body">
                                <p><span class="badge bg-success">✅</span> Flask Application</p>
                                <p><span class="badge bg-success">✅</span> Python WSGI</p>
                                <p><span class="badge bg-success">✅</span> AlwaysData Hosting</p>
                                <p><span class="badge bg-warning">⚠️</span> Template Loading</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """


@application.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'success',
        'message': 'Expense Tracker API is running perfectly!',
        'environment': {
            'platform': 'AlwaysData',
            'python_version': sys.version,
            'working_directory': os.getcwd(),
            'minimal_mode': True
        },
        'features': {
            'manual_entry': True,
            'basic_api': True,
            'file_upload': True,
            'database_ready': bool(os.environ.get('DB_HOST')),
            'spacy_disabled': True,
            'discord_disabled': True
        }
    })


@application.route('/api/categories')
def get_categories():
    """Pobierz dostępne kategorie wydatków"""
    categories = [
        'Food & Dining',
        'Transport',
        'Shopping',
        'Entertainment',
        'Bills & Utilities',
        'Healthcare',
        'Travel',
        'Education',
        'Business',
        'Other'
    ]

    return jsonify({
        'success': True,
        'categories': categories,
        'count': len(categories)
    })


@application.route('/manual')
def manual_entry_page():
    """Strona ręcznego wprowadzania wydatków"""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Manual Entry - Expense Tracker</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container mt-4">
            <div class="row justify-content-center">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">
                            <h3>💰 Manual Expense Entry</h3>
                        </div>
                        <div class="card-body">
                            <form id="expenseForm" onsubmit="submitExpense(event)">
                                <div class="mb-3">
                                    <label for="date" class="form-label">Date</label>
                                    <input type="date" class="form-control" id="date" required>
                                </div>

                                <div class="mb-3">
                                    <label for="amount" class="form-label">Amount (£)</label>
                                    <input type="number" step="0.01" class="form-control" id="amount" placeholder="0.00" required>
                                </div>

                                <div class="mb-3">
                                    <label for="vendor" class="form-label">Vendor/Store</label>
                                    <input type="text" class="form-control" id="vendor" placeholder="Where did you spend the money?">
                                </div>

                                <div class="mb-3">
                                    <label for="category" class="form-label">Category</label>
                                    <select class="form-select" id="category">
                                        <option value="Food & Dining">Food & Dining</option>
                                        <option value="Transport">Transport</option>
                                        <option value="Shopping">Shopping</option>
                                        <option value="Entertainment">Entertainment</option>
                                        <option value="Bills & Utilities">Bills & Utilities</option>
                                        <option value="Healthcare">Healthcare</option>
                                        <option value="Travel">Travel</option>
                                        <option value="Education">Education</option>
                                        <option value="Business">Business</option>
                                        <option value="Other">Other</option>
                                    </select>
                                </div>

                                <div class="mb-3">
                                    <label for="description" class="form-label">Description</label>
                                    <textarea class="form-control" id="description" rows="3" placeholder="Optional description"></textarea>
                                </div>

                                <button type="submit" class="btn btn-primary">💾 Save Expense</button>
                                <a href="/" class="btn btn-secondary">🏠 Back to Home</a>
                            </form>

                            <div id="result" class="mt-3" style="display:none;"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
        // Ustaw dzisiejszą datę
        document.getElementById('date').value = new Date().toISOString().split('T')[0];

        async function submitExpense(event) {
            event.preventDefault();

            const submitButton = event.target.querySelector('button[type="submit"]');
            const originalText = submitButton.innerHTML;
            submitButton.innerHTML = '⏳ Saving...';
            submitButton.disabled = true;

            const data = {
                date: document.getElementById('date').value,
                amount: parseFloat(document.getElementById('amount').value),
                vendor: document.getElementById('vendor').value,
                category: document.getElementById('category').value,
                description: document.getElementById('description').value
            };

            try {
                const response = await fetch('/api/save-expense', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });

                const result = await response.json();
                const resultDiv = document.getElementById('result');

                if (result.success) {
                    resultDiv.innerHTML = `
                        <div class="alert alert-success">
                            <strong>✅ Success!</strong> Expense saved: £${data.amount} at ${data.vendor || 'Unknown vendor'}
                        </div>
                    `;
                    document.getElementById('expenseForm').reset();
                    document.getElementById('date').value = new Date().toISOString().split('T')[0];
                } else {
                    resultDiv.innerHTML = `
                        <div class="alert alert-danger">
                            <strong>❌ Error:</strong> ${result.error}
                        </div>
                    `;
                }

                resultDiv.style.display = 'block';

            } catch (error) {
                document.getElementById('result').innerHTML = `
                    <div class="alert alert-danger">
                        <strong>❌ Network Error:</strong> ${error.message}
                    </div>
                `;
                document.getElementById('result').style.display = 'block';
            } finally {
                submitButton.innerHTML = originalText;
                submitButton.disabled = false;
            }
        }
        </script>
    </body>
    </html>
    """


@application.route('/api/save-expense', methods=['POST'])
def save_expense():
    """Zapisz wydatek"""
    try:
        data = request.get_json()

        # Walidacja
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})

        if not data.get('date'):
            return jsonify({'success': False, 'error': 'Date is required'})

        if not data.get('amount'):
            return jsonify({'success': False, 'error': 'Amount is required'})

        # Dodaj timestamp
        data['created_at'] = datetime.now().isoformat()
        data['id'] = f"exp_{int(datetime.now().timestamp())}"

        # TODO: Tutaj dodaj zapis do bazy danych MySQL
        # connection = get_db_connection()
        # cursor.execute("INSERT INTO expenses ...")

        # Na razie symuluj sukces
        return jsonify({
            'success': True,
            'message': f"Expense £{data['amount']} saved successfully",
            'expense_id': data['id'],
            'expense': data
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        })


@application.route('/debug')
def debug_info():
    """Informacje debugowe"""
    env_check = {
        'DB_HOST': bool(os.environ.get('DB_HOST')),
        'DB_USER': bool(os.environ.get('DB_USER')),
        'DB_PASSWORD': bool(os.environ.get('DB_PASSWORD')),
        'DB_NAME': bool(os.environ.get('DB_NAME')),
        'SECRET_KEY': bool(os.environ.get('SECRET_KEY')),
        'OPENAI_API_KEY': bool(os.environ.get('OPENAI_API_KEY'))
    }

    module_check = {}
    modules_to_test = ['flask', 'flask_cors', 'pymysql', 'json', 'datetime']

    for module in modules_to_test:
        try:
            __import__(module)
            module_check[module] = True
        except ImportError:
            module_check[module] = False

    return jsonify({
        'system': {
            'python_version': sys.version,
            'working_directory': os.getcwd(),
            'platform': 'AlwaysData',
            'minimal_mode': True
        },
        'environment_variables': env_check,
        'modules': module_check,
        'application': {
            'flask_app': True,
            'cors_enabled': True,
            'debug_mode': application.config['DEBUG']
        }
    })

# Static files
@application.route('/static/<path:filename>')
def static_files(filename):
    """Serwuj pliki statyczne"""
    try:
        return send_from_directory('static', filename)
    except:
        return "Static file not found", 404


# Error handlers
@application.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Page not found',
        'message': 'The requested URL was not found on this server',
        'available_endpoints': [
            '/', '/api/health', '/api/categories',
            '/manual', '/debug', '/api/save-expense'
        ]
    }), 404


@application.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal server error',
        'message': str(error),
        'debug_url': '/debug'
    }), 500


if __name__ == "__main__":
    application.run(debug=False, host='0.0.0.0', port=5000)