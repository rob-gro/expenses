import logging
import spacy
import os
import sys

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

"""
Moduł NLP (Natural Language Processing) zawiera komponenty odpowiedzialne za przetwarzanie
i analizę tekstu w aplikacji Expense Tracker.

Moduł ten dostarcza funkcjonalności ekstrakcji informacji o wydatkach z tekstu, parsowania
kategorii wydatków, rozpoznawania zakresów dat oraz interakcji z modelami AI dla
lepszego zrozumienia danych tekstowych.
"""

# Eksportowane funkcjonalności
__all__ = [
    # Ekstrakcja wydatków
    'extract_with_llm',
    'enhance_with_llm',
    'enhance_with_openai',

    # Przetwarzanie dat i kategorii
    'parse_relative_date',
    'extract_date_range_from_text',
    'extract_category_from_text',

    # Parsowanie komend raportowych
    'parse_report_command',
    'category_patterns'
]

# Metadane pakietu
__version__ = '1.0.0'
__author__ = 'Expense Tracker Team'

# Inicjalizacja logera
logger = logging.getLogger(__name__)


def _check_spacy_models():
    """
    Sprawdza dostępność wymaganych modeli spaCy.

    Aplikacja wykorzystuje modele językowe dla języka angielskiego i polskiego.
    Ta funkcja sprawdza czy są one poprawnie zainstalowane.
    """
    try:
        required_models = [
            ('en_core_web_sm', 'English'),
            ('pl_core_news_sm', 'Polish')
        ]

        for model_name, language in required_models:
            try:
                # Próba załadowania modelu
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
    """Sprawdza dostępność klucza API OpenAI"""
    from app.config import Config

    if not Config.OPENAI_API_KEY:
        logger.warning(
            "OpenAI API key is not set. LLM-based extraction and enhancement "
            "will not work. Set OPENAI_API_KEY in your configuration."
        )
    else:
        logger.info("OpenAI API key is configured")

# Uruchamiane przy inicjalizacji pakietu
try:
    logger.info("Initializing NLP module")
    _check_spacy_models()
    _check_openai_configuration()
except Exception as e:
    logger.error(f"Error during NLP module initialization: {e}")