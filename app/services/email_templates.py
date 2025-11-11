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
                    <td>£{amount:.2f}</td>
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

        cv_scores = confusion_data.get('cv_scores', [])

        # Calculate CV statistics
        if cv_scores:
            cv_min = min(cv_scores) * 100
            cv_max = max(cv_scores) * 100
            cv_avg = (sum(cv_scores) / len(cv_scores)) * 100
            cv_std = (sum((x - cv_avg/100)**2 for x in cv_scores) / len(cv_scores)) ** 0.5 * 100

            # Format individual scores
            cv_scores_formatted = []
            for i, score in enumerate(cv_scores, 1):
                cv_scores_formatted.append(f"Test {i}: {score:.4f} ({score*100:.2f}%)")
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
        subject = f"Model Training Completed - Accuracy: {accuracy*100:.2f}%"

        # Build HTML body
        html = f"""
        <html>
        <head>
            {EmailTemplates.COMMON_STYLES}
        </head>
        <body>
            <div class="container">
                <h2>Model Training Completed Successfully</h2>
                <p>The model has been trained and validated using your expense data.</p>

                <h3>Overall Performance:</h3>
                <table class="detail-table">
                    <tr>
                        <td>Training Type:</td>
                        <td>{metrics.get('training_type', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td>Average Accuracy:</td>
                        <td>{accuracy:.4f} ({accuracy*100:.2f}%)</td>
                    </tr>
                    <tr>
                        <td>Training Samples:</td>
                        <td>{metrics.get('samples_count', 0)} expenses</td>
                    </tr>
                    <tr>
                        <td>Categories:</td>
                        <td>{metrics.get('categories_count', 0)} different categories</td>
                    </tr>
                    <tr>
                        <td>Training Date:</td>
                        <td>{metrics.get('created_at', 'N/A')}</td>
                    </tr>
                </table>

                <h3>Cross-Validation Analysis:</h3>
                <div class="info-box">
                    <strong>What is Cross-Validation?</strong><br/>
                    The model was tested 5 times on different subsets of your data. Each test uses 80% for training and 20% for validation.
                    This helps ensure the model works well on expenses it hasn't seen before.
                </div>

                <table class="detail-table">
                    <tr>
                        <td>Individual Test Results:</td>
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
                        <td>Stability Assessment:</td>
                        <td><strong>{stability}</strong></td>
                    </tr>
                </table>

                <h4>What These Numbers Mean:</h4>
                <ul>
                    <li><strong>Average Accuracy ({accuracy*100:.2f}%):</strong>
                        The model correctly predicts categories for about {int(accuracy*100)} out of 100 expenses.</li>
                    <li><strong>Variability (±{cv_std:.2f}%):</strong>
                        How much the accuracy changes between tests. Lower is better - means the model is consistent.</li>
                    <li><strong>Best vs Worst ({cv_max:.2f}% vs {cv_min:.2f}%):</strong>
                        Shows the range of performance. A smaller gap means more reliable predictions.</li>
                </ul>

                <h4>How to Improve the Model:</h4>
                <ul>
                    <li>Add more expenses to each category (aim for at least 20-30 per category)</li>
                    <li>Correct wrong categories when you see them in "View Expenses" tab</li>
                    <li>Use consistent vendor names and descriptions</li>
                    <li>Retrain the model periodically as you add more data</li>
                </ul>

                <div class="warning-box">
                    <strong>Note:</strong> {metrics.get('notes', 'Model training completed successfully.')}
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
        category = params.get('category', 'All categories')
        start_date = params.get('start_date', 'Beginning')
        end_date = params.get('end_date', 'Present')

        subject = f"Expense Report Generated - {category}"

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
                        <td>{category}</td>
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