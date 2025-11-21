"""
Centralized email templates for Expense Tracker
All email formatting in one place for consistency and maintainability
"""

import datetime
from typing import List, Dict, Optional
from app.config import Config


class EmailTemplates:
    """Unified email templates for all notifications"""

    # Common CSS styles
    COMMON_STYLES = """
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            h2 { color: #2196F3; margin-bottom: 20px; }
            h3 { color: #333; margin-top: 20px; margin-bottom: 10px; }
            h4 { color: #666; margin-top: 15px; margin-bottom: 8px; }
            .transcription {
                background-color: #f5f5f5;
                padding: 15px;
                margin: 15px 0;
                border-left: 4px solid #2196F3;
            }
            .detail-table {
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
                background-color: #fafafa;
            }
            .detail-table td {
                padding: 10px;
                border-bottom: 1px solid #e0e0e0;
            }
            .detail-table td:first-child {
                font-weight: bold;
                width: 30%;
                color: #666;
            }
            .expense-separator { height: 20px; }
            .footer {
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #e0e0e0;
                color: #666;
                font-size: 12px;
                text-align: center;
            }
            .warning-box {
                margin-top: 20px;
                padding: 15px;
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
            }
            .info-box {
                margin-top: 10px;
                margin-bottom: 10px;
                padding: 10px;
                background-color: #e3f2fd;
                border-left: 4px solid #2196F3;
            }
            ul { margin-top: 5px; }
            li { margin-bottom: 5px; }
        </style>
    """

    # Common footer
    FOOTER = """
        <p class="footer">
            This is an automated message from your Expense Tracking System.
        </p>
    """

    @staticmethod
    def _format_date(date) -> str:
        """Helper to format date consistently"""
        if isinstance(date, datetime.datetime):
            return date.strftime('%Y-%m-%d')
        return str(date)

    @staticmethod
    def expense_confirmation(
        expenses: List[Dict],
        transcription: Optional[str] = None,
        source: str = "web"  # "web", "discord", "audio"
    ) -> tuple[str, str]:
        """
        Unified template for expense confirmation emails

        Args:
            expenses: List of expense dicts with keys: date, amount, vendor, category, description
            transcription: Optional audio transcription text
            source: Source of the expense (for internal tracking)

        Returns:
            tuple: (subject, html_body)
        """
        if not expenses:
            return ("", "")

        first = expenses[0]
        first_date = EmailTemplates._format_date(first.get('date'))
        first_amount = first.get('amount', 0)
        first_category = first.get('category', 'Uncategorized')

        # Subject line - unified format
        if len(expenses) == 1:
            subject = f"Expense Added: {first_date} - £{first_amount} ({first_category})"
        else:
            subject = f"{len(expenses)} Expenses Added on {first_date}"

        # Build expense rows
        expense_rows = []
        for exp in expenses:
            date = EmailTemplates._format_date(exp.get('date'))
            amount = exp.get('amount', 0)
            vendor = exp.get('vendor', 'Unknown')
            category = exp.get('category', 'Uncategorized')
            description = exp.get('description', '')

            row = f"""
                <tr>
                    <td>Date:</td>
                    <td>{date}</td>
                </tr>
                <tr>
                    <td>Amount:</td>
                    <td>£{amount}</td>
                </tr>
                <tr>
                    <td>Merchant:</td>
                    <td>{vendor}</td>
                </tr>
                <tr>
                    <td>Category:</td>
                    <td>{category}</td>
                </tr>
            """

            if description:
                row += f"""
                <tr>
                    <td>Description:</td>
                    <td>{description}</td>
                </tr>
                """

            expense_rows.append(row)

        # Transcription section (optional)
        transcription_html = ""
        if transcription:
            transcription_html = f"""
            <div class="transcription">
                <strong>Transcription:</strong> <em>"{transcription}"</em>
            </div>
            """

        # Build expense tables HTML
        expense_tables = []
        for row in expense_rows:
            expense_tables.append(f'<table class="detail-table">{row}</table>')

        expenses_html = '<div class="expense-separator"></div>'.join(expense_tables)

        # Build complete HTML
        html = f"""
        <html>
        <head>
            {EmailTemplates.COMMON_STYLES}
        </head>
        <body>
            <div class="container">
                <h2>Expense Recording Confirmation</h2>
                <p>Your expense{'s have' if len(expenses) > 1 else ' has'} been recorded successfully.</p>

                {transcription_html}

                <h3>Recorded Expense{'s' if len(expenses) > 1 else ''}:</h3>

                {expenses_html}

                {EmailTemplates.FOOTER}
            </div>
        </body>
        </html>
        """

        return (subject, html)

    @staticmethod
    def training_complete(metrics: Dict) -> tuple[str, str]:
        """
        Training completion notification with detailed metrics

        Args:
            metrics: Dictionary with training metrics from database

        Returns:
            tuple: (subject, html_body)
        """
        if not metrics:
            return ("Model Training Completed", "<p>Training completed but metrics not available.</p>")

        # Extract confusion matrix data
        confusion_data = metrics.get('confusion_matrix', {})
        if isinstance(confusion_data, str):
            import json
            confusion_data = json.loads(confusion_data)

        # The saved JSON has structure: {'confusion_matrix': {...actual data...}, 'cv_scores': [...], ...}
        # We need to extract the actual nested confusion_matrix
        actual_cm_data = confusion_data.get('confusion_matrix', {})

        # Extract data from the nested structure
        cv_scores = confusion_data.get('cv_scores', [])
        per_category_metrics = actual_cm_data.get('per_category_metrics', {})
        best_category = actual_cm_data.get('best_category')
        worst_category = actual_cm_data.get('worst_category')
        top_3_categories = actual_cm_data.get('top_3_categories', [])
        confused_pairs = actual_cm_data.get('confused_pairs', [])

        # Calculate CV statistics
        if cv_scores:
            cv_min = min(cv_scores) * 100
            cv_max = max(cv_scores) * 100
            cv_avg = (sum(cv_scores) / len(cv_scores)) * 100
            cv_std = (sum((x - cv_avg/100)**2 for x in cv_scores) / len(cv_scores)) ** 0.5 * 100

            # Format individual scores
            cv_scores_formatted = []
            for i, score in enumerate(cv_scores, 1):
                cv_scores_formatted.append(f"Fold {i}: {score:.4f} ({score*100:.2f}%)")
            cv_scores_str = '<br/>'.join(cv_scores_formatted)

            # Interpretation
            if cv_std < 5:
                stability = "Excellent - very stable performance"
            elif cv_std < 10:
                stability = "Good - consistent performance"
            elif cv_std < 15:
                stability = "Fair - moderate variability"
            else:
                stability = "Poor - high variability, more data needed"
        else:
            cv_scores_str = 'N/A'
            cv_min = cv_max = cv_avg = cv_std = 0
            stability = 'N/A'

        accuracy = metrics.get('accuracy', 0)
        subject = f"ML Training Complete - {accuracy*100:.2f}% Accuracy"

        # Build per-category performance table
        per_category_html = ""
        if per_category_metrics:
            category_rows = []
            for category, cat_metrics in sorted(per_category_metrics.items(), key=lambda x: x[1]['f1_score'], reverse=True):
                row = f"""
                <tr>
                    <td style="font-weight: bold; color: #2196F3;">{category}</td>
                    <td>{cat_metrics['samples']}</td>
                    <td>{cat_metrics['precision']*100:.1f}%</td>
                    <td>{cat_metrics['recall']*100:.1f}%</td>
                    <td style="font-weight: bold;">{cat_metrics['f1_score']*100:.1f}%</td>
                    <td>{cat_metrics['accuracy']*100:.1f}%</td>
                    <td>{cat_metrics['confidence']*100:.1f}%</td>
                </tr>
                """
                category_rows.append(row)

            per_category_html = f"""
                <h3>📊 Per-Category Performance Metrics</h3>
                <table class="detail-table" style="font-size: 13px;">
                    <tr style="background-color: #2196F3; color: white;">
                        <th style="padding: 10px; text-align: left;">Category</th>
                        <th style="padding: 10px; text-align: center;">Samples</th>
                        <th style="padding: 10px; text-align: center;">Precision</th>
                        <th style="padding: 10px; text-align: center;">Recall</th>
                        <th style="padding: 10px; text-align: center;">F1-Score</th>
                        <th style="padding: 10px; text-align: center;">Accuracy</th>
                        <th style="padding: 10px; text-align: center;">Confidence</th>
                    </tr>
                    {''.join(category_rows)}
                </table>
            """

        # Build best/worst categories section
        best_worst_html = ""
        if best_category and worst_category:
            best_worst_html = f"""
                <div style="display: flex; gap: 20px; margin: 20px 0;">
                    <div style="flex: 1; padding: 15px; background-color: #e8f5e9; border-left: 4px solid #4caf50;">
                        <strong style="color: #4caf50;">🏆 Best Category:</strong><br/>
                        <span style="font-size: 16px; font-weight: bold;">{best_category['name']}</span><br/>
                        <span style="color: #666;">F1-Score: {best_category['f1_score']*100:.1f}%</span>
                    </div>
                    <div style="flex: 1; padding: 15px; background-color: #ffebee; border-left: 4px solid #f44336;">
                        <strong style="color: #f44336;">⚠️ Needs Improvement:</strong><br/>
                        <span style="font-size: 16px; font-weight: bold;">{worst_category['name']}</span><br/>
                        <span style="color: #666;">F1-Score: {worst_category['f1_score']*100:.1f}%</span>
                    </div>
                </div>
            """

        # Build top 3 categories section
        top_3_html = ""
        if top_3_categories:
            medals = ['🥇', '🥈', '🥉']
            top_3_items = []
            for i, cat in enumerate(top_3_categories[:3]):
                medal = medals[i] if i < 3 else '•'
                top_3_items.append(f"<li>{medal} <strong>{cat['name']}</strong> - F1: {cat['f1_score']*100:.1f}%</li>")
            top_3_html = f"""
                <div class="info-box">
                    <strong>🌟 Top 3 Categories:</strong>
                    <ul style="margin: 5px 0;">
                        {''.join(top_3_items)}
                    </ul>
                </div>
            """

        # Build confused pairs section
        confused_html = ""
        if confused_pairs:
            confused_items = []
            for pair in confused_pairs[:5]:
                confused_items.append(
                    f"<li><strong>{pair['true_category']}</strong> → <em>{pair['predicted_category']}</em> "
                    f"({pair['count']} {'time' if pair['count'] == 1 else 'times'})</li>"
                )
            confused_html = f"""
                <h4>🔄 Most Confused Category Pairs</h4>
                <ul style="margin: 5px 0; color: #666;">
                    {''.join(confused_items)}
                </ul>
            """

        # Build confidence analysis section
        confidence_html = ""
        high_conf_cats = []
        low_conf_cats = []

        if per_category_metrics:
            avg_confidence = sum(m['confidence'] for m in per_category_metrics.values()) / len(per_category_metrics) * 100
            high_conf_cats = [cat for cat, m in per_category_metrics.items() if m['confidence'] > 0.8]
            low_conf_cats = [cat for cat, m in per_category_metrics.items() if m['confidence'] < 0.6]

            confidence_html = f"""
                <h3>💡 Confidence Analysis</h3>
                <table class="detail-table">
                    <tr>
                        <td>Average Confidence:</td>
                        <td><strong>{avg_confidence:.1f}%</strong></td>
                    </tr>
                    <tr style="background-color: #e8f5e9;">
                        <td>High Confidence Categories (>80%):</td>
                        <td>{len(high_conf_cats)} categories{': ' + ', '.join(high_conf_cats[:5]) if high_conf_cats else ''}</td>
                    </tr>
                    <tr style="background-color: #fff3e0;">
                        <td>Low Confidence Categories (<60%):</td>
                        <td>{len(low_conf_cats)} categories{': ' + ', '.join(low_conf_cats[:5]) if low_conf_cats else ''}</td>
                    </tr>
                </table>
            """

        # Build actionable recommendations
        recommendations = []
        if worst_category and worst_category['f1_score'] < 0.6:
            recommendations.append(f"• Add more training samples for <strong>{worst_category['name']}</strong> category")
        if low_conf_cats:
            recommendations.append(f"• Review and clarify category definitions for: {', '.join(low_conf_cats[:3])}")
        if confused_pairs:
            top_confused = confused_pairs[0]
            recommendations.append(f"• Categories <strong>{top_confused['true_category']}</strong> and <strong>{top_confused['predicted_category']}</strong> are frequently confused - consider merging or clarifying")
        if cv_std > 10:
            recommendations.append("• Model variability is high - add more diverse training samples")
        if not recommendations:
            recommendations.append("✅ Model performance is good - continue collecting diverse expense data")

        recommendations_html = f"""
            <h3>🎯 Actionable Recommendations</h3>
            <div style="background-color: #fff3e0; padding: 15px; border-left: 4px solid #ff9800;">
                {'<br/>'.join(recommendations)}
            </div>
        """

        # Build HTML body
        html = f"""
        <html>
        <head>
            {EmailTemplates.COMMON_STYLES}
            <style>
                .metric-card {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    text-align: center;
                }}
                .metric-value {{
                    font-size: 36px;
                    font-weight: bold;
                    margin: 10px 0;
                }}
                th {{
                    font-weight: bold;
                    text-align: left;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div style="background-color: #2196F3; color: white; padding: 20px; margin: -20px -20px 20px -20px; border-radius: 8px 8px 0 0;">
                    <h2 style="color: white; margin: 0;">🤖 ML Model Training Completed</h2>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Vector-based expense classification model</p>
                </div>

                <div class="metric-card">
                    <div style="opacity: 0.9; font-size: 14px;">OVERALL ACCURACY</div>
                    <div class="metric-value">{accuracy*100:.2f}%</div>
                    <div style="opacity: 0.9; font-size: 12px;">{metrics.get('samples_count', 0)} samples • {metrics.get('categories_count', 0)} categories</div>
                </div>

                <h3>📈 Cross-Validation Results</h3>
                <table class="detail-table">
                    <tr>
                        <td>Fold Results:</td>
                        <td>{cv_scores_str}</td>
                    </tr>
                    <tr style="background-color: #f0f0f0;">
                        <td>Best Performance:</td>
                        <td>{cv_max:.2f}%</td>
                    </tr>
                    <tr style="background-color: #f0f0f0;">
                        <td>Worst Performance:</td>
                        <td>{cv_min:.2f}%</td>
                    </tr>
                    <tr style="background-color: #f0f0f0;">
                        <td>Average:</td>
                        <td>{cv_avg:.2f}%</td>
                    </tr>
                    <tr style="background-color: #f0f0f0;">
                        <td>Variability (Std Dev):</td>
                        <td>±{cv_std:.2f}%</td>
                    </tr>
                    <tr style="background-color: #e3f2fd;">
                        <td>Stability:</td>
                        <td><strong>{stability}</strong></td>
                    </tr>
                </table>

                {per_category_html}

                {best_worst_html}

                {top_3_html}

                {confused_html}

                {confidence_html}

                {recommendations_html}

                <div style="margin-top: 30px; padding: 15px; background-color: #f5f5f5; border-radius: 4px; font-size: 12px; color: #666;">
                    <strong>Training Info:</strong><br/>
                    Type: {metrics.get('training_type', 'Vector (Qdrant + SentenceTransformers)')}<br/>
                    Date: {metrics.get('created_at', 'N/A')}<br/>
                    Model: all-MiniLM-L6-v2 embeddings with cosine similarity
                </div>

                {EmailTemplates.FOOTER}
            </div>
        </body>
        </html>
        """

        return (subject, html)

    @staticmethod
    def category_confirmation_required(
        expense: Dict,
        current_category: str,
        predicted_category: Optional[str],
        alternatives: List[Dict]
    ) -> tuple[str, str]:
        """
        Notification requiring user to confirm expense category

        Args:
            expense: Expense dict with id, date, amount, vendor, description
            current_category: Currently assigned category
            predicted_category: Model's prediction (if confident)
            alternatives: List of alternative category suggestions with confidence

        Returns:
            tuple: (subject, html_body)
        """
        subject = "Category Confirmation Required"

        # Build alternatives HTML
        alternatives_html = ""
        if alternatives:
            alt_items = []
            for alt in alternatives:
                confidence = alt.get('confidence', 0)
                category = alt.get('category', 'Unknown')
                alt_items.append(
                    f'<li><a href="{Config.APP_URL}/confirm-category/{expense["id"]}/{category}">'
                    f'Use category: {category} (confidence: {confidence:.0%})</a></li>'
                )
            alternatives_html = ''.join(alt_items)

        # Predicted category link
        predicted_html = ""
        if predicted_category:
            predicted_html = f'''
                <li><a href="{Config.APP_URL}/confirm-category/{expense["id"]}/{predicted_category}">
                    Confirm predicted category: {predicted_category}</a></li>
            '''

        html = f"""
        <html>
        <head>
            {EmailTemplates.COMMON_STYLES}
        </head>
        <body>
            <div class="container">
                <h2>Expense Category Confirmation</h2>
                <p>The system is uncertain about the category for your recent expense:</p>

                <table class="detail-table">
                    <tr>
                        <td>Date:</td>
                        <td>{expense.get('date', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td>Amount:</td>
                        <td>£{expense.get('amount', 0)}</td>
                    </tr>
                    <tr>
                        <td>Vendor:</td>
                        <td>{expense.get('vendor') or 'Not specified'}</td>
                    </tr>
                    <tr>
                        <td>Description:</td>
                        <td>{expense.get('description') or 'None'}</td>
                    </tr>
                </table>

                <p><strong>Currently assigned category:</strong> {current_category}</p>
                <p><strong>Predicted category:</strong> {predicted_category or 'No confident prediction'}</p>

                <h3>Actions:</h3>
                <p>To confirm the category, click on one of the links below:</p>
                <ul>
                    <li><a href="{Config.APP_URL}/confirm-category/{expense['id']}/{current_category}">
                        Confirm current category: {current_category}</a></li>
                    {predicted_html}
                    {alternatives_html}
                    <li><a href="{Config.APP_URL}/edit-expense/{expense['id']}">
                        Edit expense details</a></li>
                </ul>

                {EmailTemplates.FOOTER}
            </div>
        </body>
        </html>
        """

        return (subject, html)

    @staticmethod
    def category_action(
        category_name: str,
        action: str,  # "added", "deleted", "modified"
        success: bool,
        message: str,
        transcription: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Category management action confirmation

        Args:
            category_name: Name of the category
            action: Type of action performed
            success: Whether the action was successful
            message: Detailed message about the result
            transcription: Optional voice command transcription

        Returns:
            tuple: (subject, html_body)
        """
        status = "Success" if success else "Failed"
        action_title = action.capitalize()

        subject = f"Category {action_title} {status}: {category_name}"

        # Transcription section
        transcription_html = ""
        if transcription:
            transcription_html = f"""
            <div class="transcription">
                <strong>Voice Command:</strong> <em>"{transcription}"</em>
            </div>
            """

        # Status-dependent message
        followup_message = ""
        if success:
            if action == "added":
                followup_message = "The new category is now available for expense categorization."
            elif action == "deleted":
                followup_message = "The category has been removed from the system."
            elif action == "modified":
                followup_message = "The category has been updated successfully."
        else:
            followup_message = "Please try again or contact support if the issue persists."

        html = f"""
        <html>
        <head>
            {EmailTemplates.COMMON_STYLES}
        </head>
        <body>
            <div class="container">
                <h2>Category {action_title} {status}</h2>

                {transcription_html}

                <p>Result of {action} category <strong>"{category_name}"</strong>:</p>

                <div class="{'info-box' if success else 'warning-box'}">
                    {message}
                </div>

                <p>{followup_message}</p>

                {EmailTemplates.FOOTER}
            </div>
        </body>
        </html>
        """

        return (subject, html)

    @staticmethod
    def report_generated(
        report_type: str,
        params: Dict
    ) -> tuple[str, str]:
        """
        Report generation confirmation (body only, attachment added separately)

        Args:
            report_type: Type of report (excel, pdf, csv)
            params: Report parameters (category, date_range, etc.)

        Returns:
            tuple: (subject, html_body)
        """
        # Handle both old 'category' (single) and new 'categories' (list)
        categories = params.get('categories')
        if not categories:
            categories = params.get('category')
            if categories:
                categories = [categories]

        # Format for subject (count or "All categories")
        if categories and len(categories) > 0:
            subject_category = f"{len(categories)} {'category' if len(categories) == 1 else 'categories'}"
            body_category = ', '.join(categories)
        else:
            subject_category = "All categories"
            body_category = "All categories"

        start_date = params.get('start_date', 'Beginning')
        end_date = params.get('end_date', 'Present')

        subject = f"Expense Report Generated - {subject_category}"

        html = f"""
        <html>
        <head>
            {EmailTemplates.COMMON_STYLES}
        </head>
        <body>
            <div class="container">
                <h2>Expense Report Generated</h2>
                <p>Your expense report has been generated successfully.</p>

                <h3>Report Parameters:</h3>
                <table class="detail-table">
                    <tr>
                        <td>Report Type:</td>
                        <td>{report_type.upper()}</td>
                    </tr>
                    <tr>
                        <td>Category:</td>
                        <td>{body_category}</td>
                    </tr>
                    <tr>
                        <td>Date Range:</td>
                        <td>{start_date} to {end_date}</td>
                    </tr>
                    <tr>
                        <td>Generated:</td>
                        <td>{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
                    </tr>
                </table>

                <p>The report is attached to this email.</p>

                {EmailTemplates.FOOTER}
            </div>
        </body>
        </html>
        """

        return (subject, html)