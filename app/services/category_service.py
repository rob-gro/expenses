"""
Enhanced CategoryService - Service layer for category management
"""
import re
import logging
from typing import List, Dict, Optional, Tuple

from openai import OpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam

from app.config import Config
from app.database.db_manager import DBManager

logger = logging.getLogger(__name__)


class CategoryServiceError(Exception):
    """Custom exception for category service errors"""
    pass


class CategoryService:
    """Service for handling category management business logic"""

    def __init__(self, db_manager: DBManager, openai_client: Optional[OpenAI] = None):
        self.db_manager = db_manager
        self.openai_client = openai_client or OpenAI(api_key=Config.OPENAI_API_KEY)
        self._categories_cache: Optional[List[str]] = None

    def get_all_categories(self, use_cache: bool = True) -> List[str]:
        """
        Get all available expense categories with optional caching

        Args:
            use_cache: Whether to use cached categories

        Returns:
            List of category names
        """
        try:
            if use_cache and self._categories_cache is not None:
                return self._categories_cache

            categories = self.db_manager.get_all_categories()
            self._categories_cache = categories
            return categories

        except Exception as e:
            logger.error(f"Error retrieving categories: {str(e)}", exc_info=True)
            return Config.DEFAULT_CATEGORIES

    def add_category(self, name: str) -> Dict:
        """
        Add new expense category with validation and translation

        Args:
            name: Category name to add

        Returns:
            Dict with success status and message

        Raises:
            CategoryServiceError: If validation fails
        """
        try:
            # Input validation
            if not name or not name.strip():
                return {"success": False, "message": "Category name cannot be empty"}

            # Normalize and validate
            normalized_name = self._normalize_category_name(name)
            if len(normalized_name) > 50:
                return {"success": False, "message": "Category name too long (max 50 characters)"}

            # Check for invalid characters
            if not re.match(r'^[a-zA-Z0-9\s\-_]+$', normalized_name):
                return {"success": False, "message": "Category name contains invalid characters"}

            # Translate to English if needed
            english_name = self._translate_category_with_llm(normalized_name)

            # Add to database
            success, message = self.db_manager.add_category(english_name)

            # Clear cache on successful addition
            if success:
                self._categories_cache = None

            return {"success": success, "message": message}

        except Exception as e:
            logger.error(f"Error adding category: {str(e)}", exc_info=True)
            raise CategoryServiceError(f"Failed to add category: {str(e)}") from e

    def get_category_stats(self) -> Dict:
        """
        Get comprehensive statistics about category usage

        Returns:
            Dict with detailed category usage statistics
        """
        try:
            # Get all expenses efficiently
            expenses, total_count = self.db_manager.get_expenses(page=1, per_page=10000)

            if not expenses:
                return {
                    "success": True,
                    "stats": {},
                    "total_amount": 0,
                    "total_expenses": 0,
                    "categories_count": len(self.get_all_categories())
                }

            stats = {}
            total_amount = 0

            # Process expenses
            for expense in expenses:
                category = expense.get('category', 'Other')
                amount = float(expense.get('amount', 0))

                if category not in stats:
                    stats[category] = {
                        'count': 0,
                        'total_amount': 0,
                        'avg_amount': 0,
                        'min_amount': float('inf'),
                        'max_amount': 0
                    }

                stats[category]['count'] += 1
                stats[category]['total_amount'] += amount
                stats[category]['min_amount'] = min(stats[category]['min_amount'], amount)
                stats[category]['max_amount'] = max(stats[category]['max_amount'], amount)
                total_amount += amount

            # Calculate derived metrics
            for category in stats:
                cat_stats = stats[category]
                cat_stats['avg_amount'] = cat_stats['total_amount'] / cat_stats['count']
                cat_stats['percentage'] = (cat_stats['total_amount'] / total_amount * 100) if total_amount > 0 else 0

                # Fix min_amount for single-item categories
                if cat_stats['min_amount'] == float('inf'):
                    cat_stats['min_amount'] = cat_stats['max_amount']

            # Sort by total amount descending
            sorted_stats = dict(sorted(stats.items(), key=lambda x: x[1]['total_amount'], reverse=True))

            return {
                "success": True,
                "stats": sorted_stats,
                "total_amount": round(total_amount, 2),
                "total_expenses": len(expenses),
                "categories_count": len(stats),
                "avg_expense_amount": round(total_amount / len(expenses), 2) if expenses else 0
            }

        except Exception as e:
            logger.error(f"Error getting category stats: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Failed to get statistics: {str(e)}"}

    def detect_category_command(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Detect if text contains a command to add a new expense category

        Args:
            text: Transcribed text to analyze

        Returns:
            Tuple of (is_category_command, category_name)
        """
        if not text or not text.strip():
            return False, None

        logger.debug(f"Analyzing text for category command: '{text}'")
        text_lower = text.lower().strip()

        # Enhanced keyword detection
        category_keywords = ['kategori', 'category', 'kategorię']
        add_keywords = ['dodaj', 'nowa', 'nową', 'utwórz', 'add', 'new', 'create']

        has_category = any(keyword in text_lower for keyword in category_keywords)
        has_add = any(keyword in text_lower for keyword in add_keywords)

        if has_category and has_add:
            logger.debug(f"Category command keywords detected in: '{text}'")

            # Extract category name
            category_name = self._extract_category_name_from_command(text)

            if category_name:
                # Validate extracted name
                if len(category_name) > 50:
                    logger.warning(f"Category name too long: '{category_name}'")
                    return False, None

                # Translate to English
                try:
                    translated_name = self._translate_category_with_llm(category_name)
                    logger.info(f"Detected category command: '{text}' -> '{translated_name}'")
                    return True, translated_name
                except Exception as e:
                    logger.error(f"Translation failed for category command: {e}")
                    return False, None

        logger.debug(f"No category command detected in: '{text}'")
        return False, None

    def clear_cache(self):
        """Clear categories cache"""
        self._categories_cache = None
        logger.debug("Categories cache cleared")

    def _extract_category_name_from_command(self, text: str) -> Optional[str]:
        """Extract category name from command text with improved parsing"""
        # Try multiple separators
        separators = [':', '-', '–', '—', ' jako ', ' as ']

        for separator in separators:
            if separator in text:
                parts = text.split(separator, 1)
                if len(parts) > 1 and parts[1].strip():
                    candidate = parts[1].strip()
                    cleaned = self._clean_category_name(candidate)
                    if cleaned:
                        return cleaned

        # Fallback: pattern matching for "dodaj kategorię X" or "add category X"
        patterns = [
            r'(?:dodaj|add)\s+(?:kategori[ęe]|category)\s+([a-zA-Z0-9\s\-_]+)',
            r'(?:nowa|new)\s+(?:kategori[ęe]|category)\s+([a-zA-Z0-9\s\-_]+)',
            r'(?:kategori[ęe]|category)\s+([a-zA-Z0-9\s\-_]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                cleaned = self._clean_category_name(candidate)
                if cleaned:
                    return cleaned

        return None

    def _clean_category_name(self, name: str) -> str:
        """Clean and validate category name"""
        # Remove category keywords and punctuation
        name = re.sub(r'kategori[ęea]?\s*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'category\s*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'[.,:;!?]+$', '', name)

        # Remove command keywords
        command_words = ['dodaj', 'add', 'new', 'nowa', 'nową', 'create', 'utwórz']
        for word in command_words:
            name = re.sub(rf'\b{word}\b', '', name, flags=re.IGNORECASE)

        # Clean whitespace
        name = ' '.join(name.split())

        return name.strip()

    def _normalize_category_name(self, name: str) -> str:
        """Normalize category name for consistency"""
        if not name or not name.strip():
            return ""

        # Clean and normalize
        normalized = name.strip()
        # Capitalize first letter of each word
        normalized = " ".join(word.capitalize() for word in normalized.split())

        return normalized

    def _translate_category_with_llm(self, category_name: str) -> str:
        """
        Translate category name to English using OpenAI with error handling

        Args:
            category_name: Category name in any language

        Returns:
            English category name

        Raises:
            CategoryServiceError: If translation fails
        """
        try:
            system_prompt = """
            You are a financial category translator. Translate expense category names to English.
            Rules:
            - Output ONLY the translated category name
            - Capitalize first letter of each word
            - Keep it concise (1-3 words max)
            - Use common expense category terms

            Common translations:
            - żywność/jedzenie -> Groceries
            - transport -> Transportation  
            - rozrywka -> Entertainment
            - odzież -> Clothing
            """

            user_prompt = f"Translate to English: '{category_name}'"

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    ChatCompletionSystemMessageParam(role="system", content=system_prompt),
                    ChatCompletionUserMessageParam(role="user", content=user_prompt)
                ],
                temperature=0.1,
                max_tokens=15
            )

            translated_name = response.choices[0].message.content.strip()

            # Validate translation result
            if not translated_name or len(translated_name) > 50:
                raise CategoryServiceError("Invalid translation result")

            logger.info(f"LLM translated '{category_name}' to '{translated_name}'")
            return translated_name

        except Exception as e:
            logger.error(f"Translation error: {str(e)}", exc_info=True)
            # Smart fallback - normalize original
            fallback = self._normalize_category_name(category_name)
            logger.warning(f"Using fallback translation: '{fallback}'")

            if not fallback:
                raise CategoryServiceError("Translation failed and no valid fallback") from e

            return fallback


# Legacy functions for backward compatibility
def detect_category_command(text: str) -> Tuple[bool, Optional[str]]:
    """Legacy function for backward compatibility"""
    config = Config()
    db_manager = DBManager(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=config.DB_NAME
    )

    service = CategoryService(db_manager)
    return service.detect_category_command(text)


def translate_category_with_llm(category_name: str) -> str:
    """Legacy function for backward compatibility"""
    config = Config()
    db_manager = DBManager(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=config.DB_NAME
    )

    service = CategoryService(db_manager)
    return service._translate_category_with_llm(category_name)


def add_category(name: str, db_manager: DBManager) -> Tuple[bool, str]:
    """Legacy function for backward compatibility"""
    service = CategoryService(db_manager)
    result = service.add_category(name)
    return result["success"], result["message"]