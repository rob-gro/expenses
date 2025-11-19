import re
import datetime
import logging
import json
import os
from typing import List, Dict, Optional, Tuple

from openai import OpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam
from dateutil.relativedelta import relativedelta

from app.services import category_service
from app.database.db_manager import DBManager
from app.config import Config

# Configure logging
logger = logging.getLogger(__name__)

def extract_expenses_with_ai(text: str) -> Optional[List[Dict]]:
    """
    Main function to extract expense information from text using AI.

    Args:
        text: Raw transcription text containing expense information

    Returns:
        List of expense dictionaries or None if extraction fails
    """
    try:
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        config = Config()
        db = DBManager(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=config.DB_NAME
        )

        # Check if this is a category addition command
        is_category_command, category_name = category_service.detect_category_command(text)
        if is_category_command and category_name:
            logger.info(f"Detected category addition command: '{category_name}'")
            return None

        # Get available categories
        all_categories = db.get_all_categories()
        categories_str = ", ".join(all_categories)

        # Parse relative date
        relative_date = parse_relative_date(text)
        date_context = _build_date_context(relative_date)

        # Build enhanced prompt with Chain of Thought
        system_prompt = _build_system_prompt(all_categories)
        user_prompt = _build_user_prompt(text, categories_str, date_context)

        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                ChatCompletionSystemMessageParam(role="system", content=system_prompt),
                ChatCompletionUserMessageParam(role="user", content=user_prompt)
            ],
            temperature=0.1
        )

        # Parse response
        expenses = _parse_ai_response(response.choices[0].message.content.strip())
        if not expenses:
            return None

        # Post-process and validate
        expenses = _post_process_expenses(expenses, relative_date)
        expenses = _validate_categorization(expenses)

        # VENDOR CORRECTION - before ML categorization (so ML has correct vendor)
        for expense in expenses:
            if expense.get('vendor'):
                corrected_vendor = _correct_vendor_name(expense['vendor'], db)
                expense['vendor'] = corrected_vendor

        # Use ML model for category prediction if available
        expenses = _apply_ml_categorization(expenses, db)

        logger.info(f"Successfully extracted {len(expenses)} expenses")
        return expenses

    except Exception as e:
        logger.error(f"Error in extract_expenses_with_ai: {str(e)}", exc_info=True)
        return None

def _build_system_prompt(categories: List[str]) -> str:
    """Build enhanced system prompt with Chain of Thought reasoning and dynamic categories"""

    # Category descriptions with examples
    category_descriptions = {
        'Groceries': 'Food & Beverages (vegetables, fruits, bread, milk, snacks, non-alcoholic drinks)',
        'Alcohol': 'Alcoholic Drinks (beer, wine, spirits, cocktails)',
        'Cleaning Supplies': 'Cleaning Products (detergents, bleach, floor cleaner, toilet block, insecticide)',
        'Household Items': 'Household Articles (lightbulbs, batteries, trash bags, paper towels, windscreen fluid)',
        'Hygiene Products': 'Personal Hygiene (toilet paper, soap, toothpaste, shampoo, tissues)',
        'Fuel': 'Vehicle Fuel (petrol, diesel, gas)',
        'Healthcare': 'Health Items (medicines, vitamins, supplements, medical supplies, pharmacy items)',
        'Clothing': 'Apparel (clothes, shoes, accessories)',
        'Entertainment': 'Leisure (games, movies, events, subscriptions)',
        'Transportation': 'Travel (public transport, taxi, parking)',
        'Utilities': 'Bills (electricity, water, gas, internet)',
        'Rent': 'Housing (rent, mortgage, property fees)',
        'Education': 'Learning (books, courses, school supplies)',
        'Cosmetics': 'Beauty (makeup, skincare, toiletries)',
        'Office supplies': 'Work Items (stationery, equipment)',
        'Tools': 'Hardware & Tools (hammer, screwdriver, drill, torch/flashlight, ladder)',
        'Car': 'Car Maintenance (oil, repairs, car wash, parts)',
        'Furniture': 'Furniture & Home Decor (chairs, tables, lamps, decorations)',
        'Insurance': 'Insurance Payments (car, health, home, life insurance)',
        'Materials': 'Building Materials (wood, cement, paint, tiles)',
        'Pets': 'Pet Supplies (food, toys, vet visits)',
        'Other': 'Everything Else (uncategorized items)'
    }

    # Build category rules from available categories
    category_rules = []
    for cat in sorted(categories):
        description = category_descriptions.get(cat, f'{cat} items')
        category_rules.append(f"• '{cat}' → {description}")

    return f"""
You are an expert financial assistant specializing in expense categorization from shopping receipts.

CORE METHODOLOGY - CHAIN OF THOUGHT:
Step 1: PARSE - Break down the text into individual products/services
Step 2: ANALYZE - For each item, determine what it actually IS (not context)
Step 3: CATEGORIZE - Assign category based on the item's true nature
Step 4: PRICE - Match each item with its specific price

CATEGORIZATION RULES:
{chr(10).join(category_rules)}

CRITICAL INDEPENDENCE RULE:
Each product is categorized INDEPENDENTLY. A cucumber is ALWAYS Groceries, even if bought with beer.

EXAMPLES:
Input: "cucumber £2.50, beer £3.50"
Step 1: Parse → [cucumber, beer]
Step 2: Analyze → cucumber=vegetable, beer=alcohol
Step 3: Categorize → cucumber=Groceries, beer=Alcohol
Step 4: Price → cucumber=£2.50, beer=£3.50

Input: "bread, milk, Domestos"
Step 1: Parse → [bread, milk, Domestos]
Step 2: Analyze → bread=food, milk=food, Domestos=cleaner
Step 3: Categorize → bread=Groceries, milk=Groceries, Domestos=Household Chemicals

Input: "hammer, torch"
Step 1: Parse → [hammer, torch]
Step 2: Analyze → hammer=tool, torch=flashlight/tool
Step 3: Categorize → hammer=Tools, torch=Tools

Input: "vitamin C, milk"
Step 1: Parse → [vitamin C, milk]
Step 2: Analyze → vitamin C=supplement/health, milk=food
Step 3: Categorize → vitamin C=Healthcare, milk=Groceries

Input: "lightbulb, detergent, toilet paper"
Step 1: Parse → [lightbulb, detergent, toilet paper]
Step 2: Analyze → lightbulb=household item, detergent=cleaning product, toilet paper=hygiene
Step 3: Categorize → lightbulb=Household Items, detergent=Cleaning Supplies, toilet paper=Hygiene Products

RESPONSE FORMAT: Valid JSON array only. No explanations.
"""

def _build_user_prompt(text: str, categories_str: str, date_context: str) -> str:
    """Build user prompt with context"""
    return f"""
EXTRACT EXPENSES FROM TEXT:
"{text}"

{date_context}

AVAILABLE CATEGORIES: {categories_str}

REQUIRED JSON FIELDS:
- date: YYYY-MM-DD format
- amount: numeric value (in pounds/currency mentioned)
- vendor: store/service name
- category: ONE from available categories
- description: single English noun (what was bought)

Apply Chain of Thought methodology. Each product gets independent analysis.
"""

def _build_date_context(relative_date: Optional[datetime.datetime]) -> str:
    """Build date context for the prompt"""
    context = f"Today's date: {datetime.datetime.now().strftime('%Y-%m-%d')}"
    if relative_date:
        context += f"\nRelative date mentioned: {relative_date.strftime('%Y-%m-%d')}"
    return context

def _parse_ai_response(response_text: str) -> Optional[List[Dict]]:
    """Parse and validate AI response"""
    try:
        # Extract JSON from response
        json_pattern = r'\[.*\]'
        json_match = re.search(json_pattern, response_text, re.DOTALL)
        json_str = json_match.group(0) if json_match else response_text

        if not json_str.strip():
            logger.error("Empty JSON returned from AI")
            return None

        expenses = json.loads(json_str)

        # Handle string response (sometimes AI returns escaped JSON)
        if isinstance(expenses, str):
            expenses = json.loads(expenses)

        # Ensure we have a list
        if isinstance(expenses, dict):
            expenses = [expenses]

        if not isinstance(expenses, list):
            logger.error(f"Expected list, got {type(expenses).__name__}")
            return None

        return expenses

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return None

def _post_process_expenses(expenses: List[Dict], relative_date: Optional[datetime.datetime]) -> List[Dict]:
    """Post-process expenses with date normalization"""
    current_date = datetime.datetime.now()
    current_year = current_date.year

    for i, expense in enumerate(expenses):
        # Process date
        if isinstance(expense, dict) and 'date' in expense and expense['date']:
            try:
                expense_date = datetime.datetime.strptime(expense['date'], '%Y-%m-%d')

                # Use relative date if valid and recent
                if relative_date and relative_date.year >= current_year:
                    expense['date'] = relative_date
                elif expense_date.year < current_year or expense_date > current_date:
                    expense['date'] = current_date
                else:
                    expense['date'] = expense_date

            except (ValueError, TypeError) as e:
                logger.warning(f"Expense #{i + 1} - Date parsing error: {e}")
                expense[
                    'date'] = relative_date if relative_date and relative_date.year >= current_year else current_date
        else:
            logger.warning(f"Expense #{i + 1} - Missing date field")
            expense['date'] = relative_date if relative_date and relative_date.year >= current_year else current_date

        # Ensure required fields exist
        expense.setdefault('amount', 0.0)
        expense.setdefault('vendor', '')
        expense.setdefault('category', 'Other')
        expense.setdefault('description', '')

    return expenses

def _correct_vendor_name(vendor: str, db_manager: DBManager) -> str:
    """
    Correct vendor name using fuzzy matching against known vendors from database.

    Examples:
        "Azda" → "Asda"
        "Ridlu" → "Lidl"
        "Tecso" → "Tesco"
    """
    if not vendor:
        return vendor

    # Get known vendors from database
    known_vendors = db_manager.get_all_vendors()

    # Exact match (case-insensitive)
    vendor_lower = vendor.lower()
    for known in known_vendors:
        if known.lower() == vendor_lower:
            return known  # Return with correct capitalization

    # Fuzzy match using difflib
    from difflib import get_close_matches
    matches = get_close_matches(vendor, known_vendors, n=1, cutoff=0.75)

    if matches:
        logger.info(f"Vendor correction: '{vendor}' → '{matches[0]}'")
        return matches[0]

    # No match found - return original
    return vendor


def _validate_categorization(expenses: List[Dict]) -> List[Dict]:
    """
    Post-validation to fix obvious AI categorization mistakes.
    Senior-level rule-based fallback for AI edge cases.
    """

    # Common food items that should always be Groceries
    food_items = {
        'cucumber', 'tomato', 'potato', 'onion', 'carrot', 'lettuce', 'spinach',
        'apple', 'banana', 'orange', 'grapes', 'strawberry', 'lemon',
        'bread', 'milk', 'cheese', 'yogurt', 'butter', 'eggs',
        'rice', 'pasta', 'flour', 'sugar', 'salt', 'pepper',
        'chicken', 'beef', 'pork', 'fish', 'salmon', 'tuna'
    }

    # Cleaning products that should be Household Chemicals
    cleaning_items = {
        'domestos', 'bleach', 'detergent', 'soap', 'shampoo', 'toothpaste',
        'toilet paper', 'tissues', 'kitchen roll', 'washing powder'
    }

    # Alcoholic beverages
    alcohol_items = {
        'beer', 'wine', 'vodka', 'whiskey', 'rum', 'gin', 'champagne',
        'lager', 'ale', 'cider', 'spirits'
    }

    # Vendor name corrections
    vendor_corrections = {
        'feinsbery': "Sainsbury's",
        'feinsbergen': "Sainsbury's",
        'salisbury': "Sainsbury's",
        'steinsberry': "Sainsbury's",
        'azja': 'Asda',
        'pc karys': 'PC Currys'
    }

    amount_corrections = {
        'pęsów': 'pence',
        'pensów': 'pence'
    }

    for expense in expenses:
        if not isinstance(expense, dict) or 'description' not in expense:
            continue

        description_lower = expense['description'].lower()

        # Fix food items incorrectly categorized
        if description_lower in food_items and expense.get('category') != 'Groceries':
            logger.info(f"Correcting {description_lower} from {expense.get('category')} to Groceries")
            expense['category'] = 'Groceries'

        # Fix cleaning items
        elif description_lower in cleaning_items and expense.get('category') != 'Household Chemicals':
            logger.info(f"Correcting {description_lower} from {expense.get('category')} to Household Chemicals")
            expense['category'] = 'Household Chemicals'

        # Fix alcohol items
        elif description_lower in alcohol_items and expense.get('category') != 'Alcohol':
            logger.info(f"Correcting {description_lower} from {expense.get('category')} to Alcohol")
            expense['category'] = 'Alcohol'

        # Fix vendor names
        vendor_lower = expense.get('vendor', '').lower()
        if vendor_lower in vendor_corrections:
            logger.info(f"Correcting vendor '{expense.get('vendor')}' to '{vendor_corrections[vendor_lower]}'")
            expense['vendor'] = vendor_corrections[vendor_lower]
    return expenses


def _apply_ml_categorization(expenses: List[Dict], db_manager: DBManager) -> List[Dict]:
    """
    Apply ML model (Qdrant vector-based) for category prediction.
    This overrides OpenAI/rule-based categorization with trained model predictions.

    IMPORTANT: Always sets confidence_score (never leaves it NULL)
    """
    try:
        use_vector_model = os.getenv("USE_VECTOR_MODEL", "True").lower() == "true"

        if not use_vector_model:
            logger.info("Vector model disabled (USE_VECTOR_MODEL=False). Using OpenAI categories.")
            # Set confidence_score = 0.0 for all expenses when ML is disabled
            for expense in expenses:
                expense['confidence_score'] = 0.0
            return expenses

        # Try to use Qdrant vector model
        try:
            from app.core.vector_expense_learner import QdrantExpenseLearner
            learner = QdrantExpenseLearner(db_manager)
            logger.info("Using Qdrant vector model for category prediction")

            for expense in expenses:
                # Build context for prediction
                transcription = expense.get('description', '')
                vendor = expense.get('vendor', '')
                description = expense.get('description', '')

                # Keep original OpenAI category for comparison
                openai_category = expense.get('category')

                # Get prediction from Qdrant
                predicted_category, confidence = learner.predict_category_with_confidence(
                    transcription=transcription,
                    vendor=vendor,
                    description=description
                )

                # ML Confidence Threshold System:
                # - High confidence (≥85%): Trust ML completely
                # - Medium confidence (30-85%): Use OpenAI as fallback
                # - Low confidence (<30%): Use OpenAI
                MIN_ML_CONFIDENCE = 0.85

                if predicted_category and confidence >= MIN_ML_CONFIDENCE:
                    # High confidence - trust ML
                    expense['category'] = predicted_category
                    expense['confidence_score'] = confidence
                    expense['ml_prediction'] = predicted_category
                    expense['openai_category'] = openai_category

                    logger.info(
                        f"ML: '{description}' → {predicted_category} "
                        f"(confidence: {confidence:.2f})"
                    )
                elif confidence >= 0.3 and confidence < MIN_ML_CONFIDENCE:
                    # Medium confidence - use OpenAI as fallback
                    expense['category'] = openai_category  # Keep OpenAI prediction
                    expense['confidence_score'] = confidence
                    expense['ml_prediction'] = predicted_category
                    expense['openai_category'] = openai_category

                    logger.info(
                        f"ML confidence low ({confidence:.2f}) - using OpenAI fallback: "
                        f"'{description}' → {openai_category} (ML suggested: {predicted_category})"
                    )
                else:
                    # Very low confidence - keep OpenAI
                    expense['category'] = openai_category
                    expense['confidence_score'] = 0.0
                    expense['ml_prediction'] = predicted_category if predicted_category else None
                    expense['openai_category'] = openai_category

                    logger.info(
                        f"ML confidence too low ({confidence:.2f}) - using OpenAI: "
                        f"'{description}' → {openai_category}"
                    )

        except (ImportError, Exception) as e:
            logger.warning(f"Vector model not available: {e}. Using OpenAI categories.")
            # Set confidence_score = 0.0 for all expenses when ML fails
            for expense in expenses:
                expense['confidence_score'] = 0.0

    except Exception as e:
        logger.error(f"Error in ML categorization: {str(e)}", exc_info=True)
        # Set confidence_score = 0.0 for all expenses on error
        for expense in expenses:
            expense.setdefault('confidence_score', 0.0)

    return expenses


def parse_relative_date(text: str, language: str = 'pl') -> Optional[datetime.datetime]:
    """Parse relative date expressions from text"""
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    text_lower = text.lower()

    # Enhanced day names mapping
    days_pl = {
        'poniedziałek': 1, 'poniedzialek': 1,
        'wtorek': 2,
        'środa': 3, 'sroda': 3, 'środę': 3, 'srodę': 3,
        'czwartek': 4,
        'piątek': 5, 'piatek': 5,
        'sobota': 6, 'sobotę': 6, 'sobote': 6,
        'niedziela': 7, 'niedzielę': 7, 'niedziele': 7
    }

    days_en = {'monday': 1, 'tuesday': 2, 'wednesday': 3, 'thursday': 4, 'friday': 5, 'saturday': 6, 'sunday': 7}

    # Enhanced patterns
    patterns = [
        (r'(?:ostatni[ąe]?|w\s+ostatni[ąe]?)\s+(\w+)', days_pl),
        (r'(?:last|on\s+last)\s+(\w+)', days_en)
    ]

    for pattern, day_map in patterns:
        match = re.search(pattern, text_lower)
        if match:
            day_name = match.group(1)
            if day_name in day_map:
                target_weekday = day_map[day_name]
                days_back = (today.weekday() - target_weekday) % 7
                if days_back == 0:
                    days_back = 7
                logger.info(f"Parsed '{day_name}' -> {target_weekday}, going back {days_back} days")
                return today - datetime.timedelta(days=days_back)

    relative_terms = {
        'pl': {
            'dzisiaj': today,
            'dziś': today,
            'wczoraj': today - datetime.timedelta(days=1),
            'przedwczoraj': today - datetime.timedelta(days=2),
            'dwa dni temu': today - datetime.timedelta(days=2),
            'tydzień temu': today - datetime.timedelta(days=7),
            'miesiąc temu': today - relativedelta(months=1)
        },
        'en': {
            'today': today,
            'yesterday': today - datetime.timedelta(days=1),
            'day before yesterday': today - datetime.timedelta(days=2),
            'two days ago': today - datetime.timedelta(days=2),
            'last week': today - datetime.timedelta(days=7),
            'a week ago': today - datetime.timedelta(days=7),
            'a month ago': today - relativedelta(months=1),
            'last month': today - relativedelta(months=1)
        }
    }

    month_names = {
        'pl': {
            'stycznia': 1, 'styczeń': 1, 'styczniu': 1, 'styczen': 1,
            'lutego': 2, 'luty': 2, 'lutym': 2,
            'marca': 3, 'marzec': 3, 'marcu': 3,
            'kwietnia': 4, 'kwiecień': 4, 'kwietniu': 4, 'kwiecien': 4,
            'maja': 5, 'maj': 5, 'maju': 5,
            'czerwca': 6, 'czerwiec': 6, 'czerwcu': 6,
            'lipca': 7, 'lipiec': 7, 'lipcu': 7,
            'sierpnia': 8, 'sierpień': 8, 'sierpniu': 8, 'sierpien': 8,
            'września': 9, 'wrzesień': 9, 'wrześniu': 9, 'wrzesien': 9, 'wrzesniu': 9,
            'października': 10, 'październik': 10, 'październiku': 10, 'pazdziernika': 10, 'pazdziernik': 10,
            'listopada': 11, 'listopad': 11, 'listopadzie': 11,
            'grudnia': 12, 'grudzień': 12, 'grudniu': 12, 'grudzien': 12
        },
        'en': {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }
    }

    # Check relative terms
    for term, date in relative_terms.get(language, {}).items():
        if term in text_lower:
            return date

    # Check other language
    other_lang = 'en' if language == 'pl' else 'pl'
    for term, date in relative_terms.get(other_lang, {}).items():
        if term in text_lower:
            return date

    # Check specific dates (day + month)
    for lang, month_dict in month_names.items():
        for month_name, month_num in month_dict.items():
            # Pattern: number + month name
            number_pattern = rf'(\d+)[^\d]*{month_name}'
            number_match = re.search(number_pattern, text_lower)
            if number_match:
                day = int(number_match.group(1))
                if 1 <= day <= 31:
                    year = today.year
                    try:
                        return datetime.datetime(year, month_num, day)
                    except ValueError:
                        continue

    # Check date formats (YYYY-MM-DD, DD-MM-YYYY)
    date_patterns = [
        r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})',  # YYYY-MM-DD
        r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})',  # DD-MM-YYYY
    ]

    for pattern in date_patterns:
        date_match = re.search(pattern, text)
        if date_match:
            groups = date_match.groups()
            if len(groups[0]) == 4:  # YYYY-MM-DD
                year, month, day = map(int, groups)
            else:  # DD-MM-YYYY
                day, month, year = map(int, groups)

            try:
                return datetime.datetime(year, month, day)
            except ValueError:
                continue
    return None

# Legacy function aliases for backward compatibility
def extract_with_llm(text: str) -> Optional[List[Dict]]:
    """Legacy alias for extract_expenses_with_ai"""
    return extract_expenses_with_ai(text)

def enhance_with_llm(text: str, existing_expenses=None) -> Optional[List[Dict]]:
    """Legacy alias for extract_expenses_with_ai"""
    return extract_expenses_with_ai(text)

def enhance_with_openai(text: str, existing_expenses=None) -> Optional[List[Dict]]:
    """Legacy alias for extract_expenses_with_ai"""
    return extract_expenses_with_ai(text)

def extract_amount_and_currency(text: str) -> Tuple[Optional[float], str]:
    """Extract amount and currency from text (legacy compatibility)"""
    # Enhanced patterns for better recognition
    amount_patterns = [
        r'£(\d+[,.]\d+)',  # £9.99
        r'(\d+[,.]\d+)\s*(?:GBP|£|pounds?)',  # 9.99 GBP
        r'(\d+[,.]\d+)\s*(?:zł|PLN|złotych)',  # 9.99 zł
        r'(\d+[,.]\d+)\s*(?:EUR|euros?)',  # 9.99 EUR
        r'(\d+[,.]\d+)',  # 9.99 (fallback)
    ]

    currency = 'GBP'  # Default currency

    for pattern in amount_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '.')
            try:
                amount = float(amount_str)

                # Determine currency
                if any(curr in text.lower() for curr in ['zł', 'pln', 'złotych']):
                    currency = 'PLN'
                elif any(curr in text.lower() for curr in ['eur', 'euro']):
                    currency = 'EUR'

                return amount, currency
            except ValueError:
                continue

    return None, currency