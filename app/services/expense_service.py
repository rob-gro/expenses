"""
ExpenseService - Service layer for expense processing business logic
"""
import os
import uuid
import datetime
import logging
from typing import Dict, List, Optional
from werkzeug.utils import secure_filename

from app.services.transcription import transcribe_audio
from app.nlp.expense_extractor import extract_expenses_with_ai
from app.services.category_service import detect_category_command
from app.services.email_service import send_email, send_category_confirmation_notification
from app.database.db_manager import DBManager

logger = logging.getLogger(__name__)


class ExpenseService:
    """Service for handling expense processing business logic"""

    def __init__(self, db_manager: DBManager, upload_folder: str):
        self.db_manager = db_manager
        self.upload_folder = upload_folder

    def process_audio_expense(self, file_object, email: Optional[str] = None) -> Dict:
        """
        Process audio file containing expense information

        Args:
            file_object: Uploaded audio file
            email: Optional email for confirmation

        Returns:
            Dict with success status and processed data
        """
        try:
            # Save uploaded file
            filename = secure_filename(f"{uuid.uuid4()}_{file_object.filename}")
            file_path = os.path.join(self.upload_folder, filename)
            file_object.save(file_path)
            logger.info(f"Saved audio file: {file_path}")

            # Transcribe audio
            transcription = transcribe_audio(file_path)
            logger.info(f"Transcription: {transcription}")

            # Check for category commands
            is_category_command, category_name = detect_category_command(transcription)
            if is_category_command and category_name:
                return self._process_category_command(category_name, transcription, email)

            # Extract expenses
            expenses = extract_expenses_with_ai(transcription)
            if not expenses:
                return {"success": False, "error": "Could not recognize expenses in the recording."}

            # Save expenses to database
            expense_ids, expense_details = self._save_expenses(expenses, file_path, transcription)

            # Send confirmation email
            if email:
                self._send_confirmation_email(email, transcription, expenses)

            return {
                "success": True,
                "message": "Audio processed successfully",
                "expense_ids": expense_ids,
                "transcription": transcription,
                "expenses": expense_details
            }

        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Failed to process audio: {str(e)}"}

    def process_manual_expense(self, expense_data: Dict) -> Dict:
        """
        Process manually entered expense data

        Args:
            expense_data: Dictionary containing expense information

        Returns:
            Dict with success status and expense ID
        """
        try:
            # Validate required fields
            if not expense_data.get('date') or not expense_data.get('amount'):
                return {"success": False, "error": "Date and amount are required fields"}

            # Parse and validate date
            try:
                if isinstance(expense_data.get('date'), str):
                    expense_date = datetime.datetime.strptime(expense_data.get('date'), '%Y-%m-%d')
                else:
                    expense_date = expense_data.get('date')
            except ValueError:
                return {"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}

            # Parse and validate amount
            try:
                amount = float(expense_data.get('amount'))
            except ValueError:
                return {"success": False, "error": "Invalid amount value"}

            # Save expense
            expense_id = self.db_manager.add_expense(
                date=expense_date,
                amount=amount,
                vendor=expense_data.get('vendor', ''),
                category=expense_data.get('category', 'Other'),
                description=expense_data.get('description', ''),
                needs_confirmation=False,
                predicted_category=None,
                alternative_categories=[],
                notification_callback=None
            )

            if expense_id:
                return {
                    "success": True,
                    "message": "Expense saved successfully",
                    "expense_id": expense_id
                }
            else:
                return {"success": False, "error": "Failed to save expense"}

        except Exception as e:
            logger.error(f"Error processing manual expense: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Failed to process expense: {str(e)}"}

    def confirm_category(self, expense_id: int, confirmed_category: str) -> Dict:
        """
        Confirm and update expense category

        Args:
            expense_id: ID of expense to update
            confirmed_category: Confirmed category name

        Returns:
            Dict with success status
        """
        try:
            if not expense_id or not confirmed_category:
                return {"success": False, "error": "Missing expense_id or category"}

            # Update expense category
            success = self.db_manager.update_expense(expense_id, category=confirmed_category)
            if not success:
                return {"success": False, "error": "Failed to update expense"}

            # Update categorization status
            self.db_manager.update_pending_categorization(expense_id, status='confirmed')

            # Train model incrementally
            from app.core.expense_learner import ExpenseLearner
            learner = ExpenseLearner(self.db_manager)
            learner.incremental_train(expense_id, confirmed_category)

            return {"success": True, "message": "Category confirmed successfully"}

        except Exception as e:
            logger.error(f"Error confirming category: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Failed to confirm category: {str(e)}"}

    def get_expense_details(self, expense_id: int) -> Optional[Dict]:
        """
        Get expense details with pending categorization info

        Args:
            expense_id: ID of expense to retrieve

        Returns:
            Dict with expense details or None if not found
        """
        try:
            expense = self.db_manager.get_expense(expense_id)
            if not expense:
                return None

            # Get pending categorization
            pending = self.db_manager.get_pending_categorization(expense_id)

            # Get available categories
            categories = self.db_manager.get_all_categories()

            return {
                "expense": expense,
                "pending": pending,
                "available_categories": categories
            }

        except Exception as e:
            logger.error(f"Error getting expense details: {str(e)}", exc_info=True)
            return None

    def train_expense_model(self) -> Dict:
        """
        Train expense categorization model

        Returns:
            Dict with training result
        """
        try:
            from app.core.expense_learner import ExpenseLearner
            learner = ExpenseLearner(self.db_manager)
            success = learner.train_model()

            if success:
                return {"success": True, "message": "Model trained successfully"}
            else:
                return {"success": False, "message": "Not enough data to train model"}

        except Exception as e:
            logger.error(f"Error training model: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Failed to train model: {str(e)}"}

    def _process_category_command(self, category_name: str, transcription: str, email: Optional[str]) -> Dict:
        """Process category addition command"""
        success, message = self.db_manager.add_category(category_name)

        # Send email notification
        if email:
            send_email(
                recipient=email,
                subject="Expense Category Action",
                body=f"""
                <html>
                    <body>
                        <h2>Category Action</h2>
                        <p>Your audio command has been processed.</p>
                        <p>Transcription: <em>{transcription}</em></p>
                        <p>Result: {message}</p>
                    </body>
                </html>
                """
            )

        return {
            "success": success,
            "message": message,
            "transcription": transcription,
            "command_type": "add_category",
            "category_name": category_name
        }

    def _save_expenses(self, expenses: List[Dict], file_path: str, transcription: str) -> tuple:
        """Save expenses to database and return IDs and details"""
        expense_ids = []
        expense_details = []

        for expense in expenses:
            # Determine if category confirmation is needed
            needs_confirmation = False
            predicted_category = None
            category_confidence = 0.0
            alternative_categories = []

            # Logic for confirmation (can be enhanced later)
            if hasattr(expense, 'category_confidence') and expense.category_confidence < 0.8:
                needs_confirmation = True
                predicted_category = expense.get('category')
                category_confidence = expense.get('category_confidence', 0.0)
                if hasattr(expense, 'alternative_categories'):
                    alternative_categories = expense.alternative_categories

            expense_id = self.db_manager.add_expense(
                date=expense.get('date', datetime.datetime.now()),
                amount=expense.get('amount'),
                vendor=expense.get('vendor', ''),
                category=expense.get('category', ''),
                description=expense.get('description', ''),
                audio_file_path=file_path,
                transcription=transcription,
                needs_confirmation=needs_confirmation,
                predicted_category=predicted_category,
                category_confidence=category_confidence,
                alternative_categories=alternative_categories,
                notification_callback=send_category_confirmation_notification if needs_confirmation else None
            )

            if expense_id:
                expense_ids.append(expense_id)
                expense_details.append({
                    "date": expense.get('date').isoformat() if isinstance(expense.get('date'),
                                                                          datetime.datetime) else expense.get('date'),
                    "amount": expense.get('amount'),
                    "vendor": expense.get('vendor', ''),
                    "category": expense.get('category', ''),
                    "description": expense.get('description', '')
                })

        return expense_ids, expense_details

    def _send_confirmation_email(self, email: str, transcription: str, expenses: List[Dict]):
        """Send confirmation email for processed expenses"""
        try:
            email_body = f"""
            <html>
                <body>
                    <h2>Expense Recording Confirmation</h2>
                    <p>Your audio message has been processed successfully.</p>
                    <p>Transcription: <em>{transcription}</em></p>
                    <h3>Recorded Expenses:</h3>
                    <ul>
                        {"".join(f"<li>{expense['date'].strftime('%Y-%m-%d') if isinstance(expense['date'], datetime.datetime) else expense['date']}: {expense.get('vendor', 'Unknown')} - £{expense.get('amount', 0)} ({expense.get('category', 'Uncategorized')})</li>" for expense in expenses)}
                    </ul>
                </body>
            </html>
            """

            send_email(
                recipient=email,
                subject="Expense(s) Recorded Successfully",
                body=email_body
            )

        except Exception as e:
            logger.error(f"Error sending confirmation email: {str(e)}")