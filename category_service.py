import re
import logging

from openai import OpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam
from config import Config

logger = logging.getLogger(__name__)

def translate_category_with_llm(category_name):
    """
    Translate a category name to English using OpenAI

    Args:
        category_name (str): Category name in any language

    Returns:
        str: English category name
    """
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=Config.OPENAI_API_KEY)

        system_prompt = """
        You are a translator specialized in expense categories. 
        Your task is to translate expense category names from any language to English.
        Do NOT include any explanations or additional text, just provide the ENGLISH name of the category.
        Always capitalize the first letter of each word in the result.
        """

        user_prompt = f"""
        Translate this expense category name to English: "{category_name}"
        Only output the translated category name, nothing else.
        """

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                ChatCompletionSystemMessageParam(role="system", content=system_prompt),
                ChatCompletionUserMessageParam(role="user", content=user_prompt)
            ],
            temperature=0.1,
            max_tokens=10  # Limit to short response
        )

        translated_name = response.choices[0].message.content.strip()
        logger.info(f"LLM translated '{category_name}' to '{translated_name}'")

        return translated_name

    except Exception as e:
        logger.error(f"Translation error: {str(e)}", exc_info=True)
        # Simple fallback - just capitalize the first letter of each word
        capitalized = " ".join(word.capitalize() for word in category_name.split())
        logger.warning(f"LLM translation failed, using capitalized original: '{capitalized}'")
        return capitalized


def detect_category_command(text):
    """
    Detect if text contains a command to add a new expense category and translate it to English

    Args:
        text (str): Transcribed text to analyze

    Returns:
        tuple: (is_category_command, category_name) or (False, None) if not a category command
    """
    if not text:
        return False, None

    # Debug log
    logger.debug(f"Analyzing text for category command: '{text}'")

    # Convert text to lowercase for case-insensitive matching
    text_lower = text.lower()

    # Simple check for add category keywords
    category_keywords = ['kategori', 'category']
    add_keywords = ['dodaj', 'nowa', 'utwórz', 'add', 'new', 'create']

    has_category = any(keyword in text_lower for keyword in category_keywords)
    has_add = any(keyword in text_lower for keyword in add_keywords)

    if has_category and has_add:
        logger.debug(f"Category command keywords detected in: '{text}'")

        # Simple splitting approach - more robust than regex
        # Look for category name after a separator like dash, colon or space
        category_name = None
        separators = [':', '-', '–', ' ']  # Include em dash

        for separator in separators:
            if separator in text:
                parts = text.split(separator, 1)
                if len(parts) > 1 and parts[1].strip():
                    # Get everything after the separator and clean it
                    candidate = parts[1].strip()

                    # Remove trailing punctuation if any
                    candidate = re.sub(r'[.,:;!?]$', '', candidate)

                    # Check if there's any content after cleaning
                    if candidate:
                        category_name = candidate
                        logger.debug(f"Extracted raw category name: '{category_name}'")
                        break

        # If we couldn't extract the category name using separators, try to extract the last word
        if not category_name:
            words = text.split()
            if len(words) > 0:
                candidate = words[-1].strip()
                # Remove trailing punctuation
                candidate = re.sub(r'[.,:;!?]$', '', candidate)

                if candidate and not any(keyword in candidate.lower() for keyword in category_keywords + add_keywords):
                    category_name = candidate
                    logger.debug(f"Extracted category from last word: '{category_name}'")

        if category_name:
            # Filter out any remaining category keywords
            category_name = re.sub(r'kategori[ęea]\s*', '', category_name, flags=re.IGNORECASE)
            category_name = re.sub(r'category\s*', '', category_name, flags=re.IGNORECASE)
            category_name = category_name.strip()

            # Translate to English using LLM
            translated_name = translate_category_with_llm(category_name)

            logger.info(
                f"Detected category command: '{text}' -> raw: '{category_name}' -> translated: '{translated_name}'")
            return True, translated_name

    logger.debug(f"No category command detected in: '{text}'")
    return False, None


def add_category(name, db_manager):
    """
    Process and add a new category

    Args:
        name (str): Category name to add
        db_manager: Database manager instance

    Returns:
        tuple: (success, message)
    """
    # Normalize category name
    normalized_name = name.strip()
    if not normalized_name:
        return False, "Category name cannot be empty"

    # Always capitalize first letter of each word for consistency
    category_name = " ".join(word.capitalize() for word in normalized_name.split())

    # Use the database manager to add the category
    return db_manager.add_category(category_name)