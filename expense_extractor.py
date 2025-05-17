import re
import datetime
import logging
import json

from openai import OpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam
from dateutil.relativedelta import relativedelta

import category_service
from db_manager import DBManager
from config import Config

# Configure logging
logger = logging.getLogger(__name__)

# Set OpenAI API client
client = OpenAI(api_key=Config.OPENAI_API_KEY)

# Initialize DB manager
db = DBManager(
    host=Config.DB_HOST,
    user=Config.DB_USER,
    password=Config.DB_PASSWORD,
    database=Config.DB_NAME
)


def extract_with_llm(text):
    try:
        is_category_command, category_name = category_service.detect_category_command(text)

        if is_category_command and category_name:
            logger.info(f"Detected category addition command in LLM extraction: '{category_name}'")
            # Return None to indicate that this is not an expense record
            return None

        all_categories = db.get_all_categories()
        categories_str = ", ".join(all_categories)

        relative_date = parse_relative_date(text)
        relative_date_hint = f"\nDzisiejsza data to: {datetime.datetime.now().strftime('%Y-%m-%d')}"
        if relative_date:
            relative_date_hint += f", a data względna to: {relative_date.strftime('%Y-%m-%d')}"

        system_prompt = """
        Jesteś asystentem finansowym, który wyodrębnia informacje o wydatkach z tekstu.
        Tekst będzie zawierał informacje o wydatkach po polsku lub angielsku.
        Twoim zadaniem jest zidentyfikowanie:
        1. Daty wydatku - zwróć dzisiejszą datę jeśli nie podano konkretnej daty
        2. Kwoty wydanej (w funtach)
        3. Sprzedawcy/sklepu
        4. Kategorii/ grupy towarowej, do której należy przypisać dany wydatek
        5. Dodatkowego opisu w języku ANGIELSKIM (Użyj tylko rzeczownika, wszyscy wiedzą, że chodzi o zakup)

        Pamiętaj, że jeśli w tekście jest mowa o kilku produktach, każdy z nich musi być osobnym rekordem w tablicy wydatków.
        Na przykład "Kupiłem chleb za 2 funty, mleko za 1 funt i piwo za 3 funty" powinno dać 3 osobne rekordy, a piwo powinno być zapisane do kategorii "Alcohol'
        Przeskanuj listę sklepów w UK, aby uniknąć błędnych nazw dodawanych do bazy danych takich jak "Azja" zamiast "Asda" lub "PC Karys" lub "Piscicaris" zamiast "PC Currys"

        Odpowiedz TYLKO strukturą danych w formacie JSON. Upewnij się, że opis jest w języku angielskim.
        """

        user_prompt = f"""
        Wyodrębnij informacje o wydatkach z poniższego tekstu:

        Text: "{text}"
        {relative_date_hint}

        Zwróć tablicę JSON z polami:
        - date: w formacie RRRR-MM-DD
        - amount: wartość liczbowa (w funtach)
        - vendor: nazwa sprzedawcy lub sklepu
        - category: JEDNA z dostępnych kategorii: {categories_str}
        - description: krótki opis wydatku W JĘZYKU ANGIELSKIM (Użyj tylko rzeczownika, wszyscy wiedzą, że chodzi o zakup)
        """

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                ChatCompletionSystemMessageParam(role="system", content=system_prompt),
                ChatCompletionUserMessageParam(role="user", content=user_prompt)
            ],
            temperature=0.1
        )

        response_text = response.choices[0].message.content.strip()

        json_pattern = r'\[.*\]'
        json_match = re.search(json_pattern, response_text, re.DOTALL)
        json_str = json_match.group(0) if json_match else response_text

        if not json_str.strip():
            logger.error("Empty or invalid JSON returned from OpenAI.")
            return None

        expenses = json.loads(json_str)

        if isinstance(expenses, str):
            try:
                expenses = json.loads(expenses)
            except Exception as e:
                logger.error(f"Second JSON decode failed: {e}")
                return None

        # Jeśli LLM zwrócił pojedynczy obiekt, a nie listę — owiń w listę
        if isinstance(expenses, dict):
            expenses = [expenses]

        if not isinstance(expenses, list):
            logger.error(f"Expected list of expenses, got {type(expenses).__name__}")
            return None

        current_date = datetime.datetime.now()
        current_year = current_date.year

        for i, expense in enumerate(expenses):
            if isinstance(expense, dict) and 'date' in expense and expense['date']:
                try:
                    expense_date = datetime.datetime.strptime(expense['date'], '%Y-%m-%d')

                    if relative_date and relative_date.year >= current_year:
                        expense['date'] = relative_date
                    elif expense_date.year < current_year or expense_date > current_date:
                        expense['date'] = current_date
                    else:
                        expense['date'] = expense_date

                except Exception as e:
                    logger.warning(f"Expense #{i + 1} - Error parsing date: {e}. Using fallback date.")
                    expense[
                        'date'] = relative_date if relative_date and relative_date.year >= current_year else current_date
            else:
                logger.warning(f"Expense #{i + 1} - Missing or invalid 'date' field. Assigning fallback date.")
                expense[
                    'date'] = relative_date if relative_date and relative_date.year >= current_year else current_date

        return expenses

    except Exception as e:
        logger.error(f"Error in extract_with_llm: {str(e)}", exc_info=True)
        return None

def parse_relative_date(text, language='pl'):
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

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

    text_lower = text.lower()

    for term, date in relative_terms.get(language, {}).items():
        if term in text_lower:
            return date

    other_lang = 'en' if language == 'pl' else 'pl'
    for term, date in relative_terms.get(other_lang, {}).items():
        if term in text_lower:
            return date

    return None

def enhance_with_llm(text, existing_expenses=None):
    try:
        existing_info = ""
        if existing_expenses:
            if isinstance(existing_expenses, list):
                for i, exp in enumerate(existing_expenses):
                    existing_info += f"Expense {i + 1}: {exp}\n"
            else:
                existing_info = f"Partial info: {existing_expenses}\n"

        system_prompt = """
        You are a financial assistant that extracts expense information from text.
        Extract precise details about expenses including dates, amounts, vendors, and categories.
        Respond only with structured valid JSON data.
        """

        user_prompt = f"""
        Extract and return expense information from the following text:

        Text: \"{text}\"

        {existing_info}

        Return a JSON array of expenses with the following fields:
        - date: in YYYY-MM-DD format (default to today if not mentioned)
        - amount: numeric value (in pounds)
        - vendor: store or service provider name
        - category: one of [Fuel, Cosmetics, Groceries, Utilities, Rent, Entertainment, Transportation, Healthcare, Clothing, Education, Office supplies, Alcohol, Other]
        - description: use just only substantive in brief description of the expense
        """

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                ChatCompletionSystemMessageParam(role="system", content=system_prompt),
                ChatCompletionUserMessageParam(role="user", content=user_prompt)
            ],
            temperature=0.1
        )

        response_text = response.choices[0].message.content.strip()

        json_pattern = r'\[.*\]'
        json_match = re.search(json_pattern, response_text, re.DOTALL)
        json_str = json_match.group(0) if json_match else response_text

        expenses = json.loads(json_str)

        for expense in expenses:
            if 'date' in expense and expense['date']:
                try:
                    expense['date'] = datetime.datetime.strptime(expense['date'], '%Y-%m-%d')
                except:
                    expense['date'] = datetime.datetime.now()

        return expenses

    except Exception as e:
        logger.error(f"Error in LLM enhancement: {str(e)}", exc_info=True)
        return None


def enhance_with_openai(text, existing_expenses=None):
    try:
        existing_info = ""
        if existing_expenses:
            if isinstance(existing_expenses, list):
                for i, exp in enumerate(existing_expenses):
                    existing_info += f"Expense {i + 1}: {exp}\n"
            else:
                existing_info = f"Partial info: {existing_expenses}\n"

        user_prompt = f"""
        Extract expense information from the following text.

        Text: \"{text}\"

        {existing_info}

        Extract and return a JSON array of expenses with the following fields:
        - date: in YYYY-MM-DD format (default to today if not mentioned)
        - amount: numeric value (in pounds)
        - vendor: store or service provider name
        - category: one of [Fuel, Cosmetics, Groceries, Utilities, Rent, Entertainment, Transportation, Healthcare, Clothing, Education, Other, Office supplies, Alcohol]
        - description: use just only substantive in brief description of the expense
        """

        system_prompt = "You are a financial assistant. Return only valid JSON."

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                ChatCompletionSystemMessageParam(role="system", content=system_prompt),
                ChatCompletionUserMessageParam(role="user", content=user_prompt)
            ],
            temperature=0.1
        )

        response_text = response.choices[0].message.content.strip()

        json_pattern = r'\[.*\]'
        json_match = re.search(json_pattern, response_text, re.DOTALL)
        json_str = json_match.group(0) if json_match else response_text

        expenses = json.loads(json_str)

        for expense in expenses:
            if 'date' in expense and expense['date']:
                try:
                    expense['date'] = datetime.datetime.strptime(expense['date'], '%Y-%m-%d')
                except:
                    expense['date'] = datetime.datetime.now()

        return expenses

    except Exception as e:
        logger.error(f"Error in OpenAI enhancement: {str(e)}", exc_info=True)
        return None