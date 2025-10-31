import logging
import os
import sys

# Conditional spacy import for AlwaysData
if not os.environ.get('DISABLE_SPACY'):
    import spacy
else:
    spacy = None

from app.nlp.expense_extractor import (
    extract_with_llm,
    enhance_with_llm,
    enhance_with_openai,
    parse_relative_date
)

from app.nlp.nlp_category_parser import (
    extract_date_range_from_text,
    extract_category_from_text
)

from app.nlp.report_parser import (
    parse_report_command,
    category_patterns
)


__all__ = [
    # Expense extraction
    'extract_with_llm',
    'enhance_with_llm',
    'enhance_with_openai',

    # Processing dates and categories
    'parse_relative_date',
    'extract_date_range_from_text',
    'extract_category_from_text',

    # Parsing report commands
    'parse_report_command',
    'category_patterns'
]

__version__ = '1.0.0'
__author__ = 'Expense Tracker Team'

logger = logging.getLogger(__name__)


def _check_spacy_models():
    """
    Checks the availability of required spaCy models.

    The application uses language models for both English and Polish.
    This function verifies whether they are correctly installed.
    """
    if os.environ.get('DISABLE_SPACY') or spacy is None:
        logger.info("spaCy disabled - skipping model checks")
        return

    try:
        required_models = [
            ('en_core_web_sm', 'English'),
            ('pl_core_news_sm', 'Polish')
        ]

        for model_name, language in required_models:
            try:
                # Attempting to load the model
                spacy.load(model_name)
                logger.info(f"spaCy {language} model ({model_name}) loaded successfully")
            except OSError:
                logger.warning(
                    f"spaCy {language} model ({model_name}) not found. "
                    f"Download it using: python -m spacy download {model_name}"
                )

    except ImportError:
        logger.warning("spaCy library not found. NLP functionality may be limited")


def _check_openai_configuration():
    """Checks the availability of the OpenAI API key"""
    from app.config import Config

    if not Config.OPENAI_API_KEY:
        logger.warning(
            "OpenAI API key is not set. LLM-based extraction and enhancement "
            "will not work. Set OPENAI_API_KEY in your configuration."
        )
    else:
        logger.info("OpenAI API key is configured")

# Executed during package initialization
try:
    logger.info("Initializing NLP module")
    _check_spacy_models()
    _check_openai_configuration()
except Exception as e:
    logger.error(f"Error during NLP module initialization: {e}")