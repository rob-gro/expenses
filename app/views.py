from flask import Blueprint, render_template

# Create Blueprint for views
views_bp = Blueprint('views', __name__)


@views_bp.route('/confirm-category/<int:expense_id>/<category>', methods=['GET'])
def confirm_category_page(expense_id, category):
    return render_template('confirm_category.html', expense_id=expense_id, suggested_category=category)


@views_bp.route('/')
def index():
    return render_template('index.html')


@views_bp.route('/index')
def index_alt():
    return render_template('index.html')


@views_bp.route('/model-metrics')
def model_metrics():
    return render_template('model_metrics.html')


# Legacy compatibility function
def register_view_routes(app):
    """Legacy function for backward compatibility"""
    pass