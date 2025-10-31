from flask import render_template

def register_view_routes(app):
    @app.route('/confirm-category/<int:expense_id>/<category>', methods=['GET'])
    def confirm_category_page(expense_id, category):
        return render_template('confirm_category.html', expense_id=expense_id, suggested_category=category)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/index')
    def index_alt():
        return render_template('index.html')

    @app.route('/model-metrics')
    def model_metrics_page():
        return render_template('model_metrics.html')