from flask import render_template

def register_view_routes(app):
    @app.route('/confirm-category/<int:expense_id>/<category>', methods=['GET'])
    def confirm_category_page(expense_id, category):
        """Show category confirmation page"""
        return render_template('confirm_category.html', expense_id=expense_id, suggested_category=category)

    @app.route('/')
    def index():
        """Endpoint do wyświetlenia strony głównej"""
        return render_template('index.html')

    @app.route('/index')
    def index_alt():
        """Alternatywny endpoint dla /index"""
        return render_template('index.html')

    @app.route('/model-metrics')
    def model_metrics_page():
        """Endpoint do wyświetlenia strony z metrykami modelu"""
        return render_template('model_metrics.html')