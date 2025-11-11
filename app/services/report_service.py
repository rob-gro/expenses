"""
ReportService - Service layer for report generation and distribution
"""
import os
import uuid
import json
import logging
from typing import Dict, Optional
from werkzeug.utils import secure_filename

from app.services.transcription import transcribe_audio
from app.services.email_service import send_email
from app.services.email_templates import EmailTemplates
from app.core.report_generator import generate_report
from app.nlp.report_parser import parse_report_command
from app.database.db_manager import DBManager

logger = logging.getLogger(__name__)


class ReportService:
    """Service for handling report generation and distribution"""

    def __init__(self, db_manager: DBManager, upload_folder: str):
        self.db_manager = db_manager
        self.upload_folder = upload_folder

    def generate_report_from_voice(self, file_object, email: Optional[str] = None) -> Dict:
        """
        Generate report from voice command

        Args:
            file_object: Uploaded audio file with report command
            email: Optional email for report delivery

        Returns:
            Dict with success status and report info
        """
        try:
            # Save uploaded file
            filename = secure_filename(f"{uuid.uuid4()}_{file_object.filename}")
            file_path = os.path.join(self.upload_folder, filename)
            file_object.save(file_path)

            # Transcribe audio
            transcription = transcribe_audio(file_path)
            logger.info(f"Report request transcription: {transcription}")

            # Parse report parameters
            report_params = parse_report_command(transcription)

            # Generate report
            return self._generate_and_send_report(report_params, email)

        except Exception as e:
            logger.error(f"Error processing voice report request: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Failed to process voice command: {str(e)}"}

    def generate_report_from_params(self, report_params: Dict, email: Optional[str] = None) -> Dict:
        """
        Generate report from parameters

        Args:
            report_params: Dictionary with report parameters
            email: Optional email for report delivery

        Returns:
            Dict with success status and report info
        """
        try:
            return self._generate_and_send_report(report_params, email)

        except Exception as e:
            logger.error(f"Error generating report from params: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Failed to generate report: {str(e)}"}

    def _generate_and_send_report(self, report_params: Dict, email: Optional[str]) -> Dict:
        """
        Internal method to generate report and send via email

        Args:
            report_params: Report generation parameters
            email: Email recipient

        Returns:
            Dict with generation result
        """
        # Generate the report
        report_file, report_type, format_type = generate_report(
            self.db_manager,
            report_params.get('category'),
            report_params.get('start_date'),
            report_params.get('end_date'),
            report_params.get('group_by', 'month'),
            report_params.get('format', 'excel')
        )

        # Save report info to database
        report_id = self.db_manager.add_report(
            report_type=report_type,
            parameters=json.dumps(report_params),
            file_path=report_file
        )

        # Send email if recipient provided
        if email:
            self._send_report_email(email, report_file, report_type, report_params)

        return {
            "success": True,
            "message": "Report generated and sent successfully",
            "report_id": report_id,
            "report_file": report_file
        }

    def _send_report_email(self, recipient: str, report_file: str, report_type: str, params: Dict):
        """
        Send report via email - uses unified template

        Args:
            recipient: Email recipient
            report_file: Path to generated report file
            report_type: Type of report generated
            params: Report parameters for email body
        """
        try:
            # Read report file
            with open(report_file, 'rb') as f:
                file_content = f.read()

            # Use unified email template
            subject, email_body = EmailTemplates.report_generated(
                report_type=params.get('format', 'excel'),
                params=params
            )

            # Send email with attachment
            send_email(
                recipient=recipient,
                subject=subject,
                body=email_body,
                attachments={os.path.basename(report_file): file_content}
            )

            logger.info(f"Report email sent to {recipient}")

        except Exception as e:
            logger.error(f"Error sending report email: {str(e)}", exc_info=True)
            raise