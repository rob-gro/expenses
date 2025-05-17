import logging
import datetime

from expense_extractor import enhance_with_llm
from transcription import transcribe_audio
from email_service import send_email, send_confirmation_email

logger = logging.getLogger(__name__)


def process_audio_file(file_path, db_manager, email=None):
    """Process audio file, extract expense information and save to database"""
    try:
        # Transcribe audio using Whisper API
        transcription = transcribe_audio(file_path)

        # Extract expense information
        expenses = enhance_with_llm(transcription)

        # Save to database
        expense_ids = []
        for expense in expenses:
            expense_id = db_manager.add_expense(
                date=expense.get('date', datetime.datetime.now()),
                amount=expense.get('amount'),
                vendor=expense.get('vendor', ''),
                category=expense.get('category', ''),
                description=expense.get('description', ''),
                audio_file_path=file_path,
                transcription=transcription
            )
            expense_ids.append(expense_id)
            if expenses:
                send_confirmation_email(expenses)

        # Send confirmation email if email provided
        if email:
            send_email(
                recipient=email,
                subject="Expense(s) Recorded Successfully",
                body=f"""
                <html>
                    <body>
                        <h2>Expense Recording Confirmation</h2>
                        <p>Your audio message has been processed successfully.</p>
                        <p>Transcription: <em>{transcription}</em></p>
                        <h3>Recorded Expenses:</h3>
                        <ul>
                            {"".join(f"<li>{expense['date'].strftime('%Y-%m-%d')}: {expense.get('vendor', 'Unknown')} - £{expense.get('amount', 0)} ({expense.get('category', 'Uncategorized')})</li>" for expense in expenses)}
                        </ul>
                    </body>
                </html>
                """
            )

        return {
            "success": True,
            "message": "Audio processed successfully",
            "expense_ids": expense_ids,
            "transcription": transcription,
            "expenses": [
                {
                    "date": expense.get('date').isoformat() if isinstance(expense.get('date'),
                                                                          datetime.datetime) else expense.get('date'),
                    "amount": expense.get('amount'),
                    "vendor": expense.get('vendor', ''),
                    "category": expense.get('category', ''),
                    "description": expense.get('description', '')
                } for expense in expenses
            ]
        }

    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}", exc_info=True)
        return {"error": f"Failed to process audio: {str(e)}"}

