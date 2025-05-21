import re
import datetime
import logging
import json

from openai import OpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam
from dateutil.relativedelta import relativedelta

from app.services import category_service
from app.database.db_manager import DBManager
from app.config import Config

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

        amount, currency = extract_amount_and_currency(text)
        amount_hint = ""
        if amount is not None:
            amount_hint = f"\nWykryta kwota: {amount} {currency}"

        system_prompt = """
        Jesteś asystentem finansowym, który wyodrębnia informacje o wydatkach z tekstu.
        Tekst będzie zawierał informacje o wydatkach po polsku lub angielsku.
        
        Twoim zadaniem jest zidentyfikowanie:
        1. Daty wydatku - zwróć dzisiejszą datę jeśli nie podano konkretnej daty
        2. Kwoty wydanej (w funtach)
        3. Sprzedawcy/sklepu
        4. Kategorii/ grupy towarowej, do której należy przypisać dany wydatek
        5. Dodatkowego opisu w języku ANGIELSKIM (Użyj tylko rzeczownika, wszyscy wiedzą, że chodzi o zakup)
        
        BARDZO WAŻNE: Zachowaj oryginalną datę z tekstu. Jeśli jest mowa o konkretnej dacie (np. "2 maja"), 
        użyj tej daty, nie dzisiejszej daty.
        
        BARDZO WAŻNE: Zachowaj oryginalną kwotę z tekstu. Nie przeliczaj walut.
        Jeśli kwota jest w PLN (złotych), pozostaw ją w oryginalnej walucie.
        
        BARDZO WAŻNE: Określ poprawną kategorię na podstawie rodzaju produktu:
        - Chemię gospodarczą, środki czystości, detergenty zaklasyfikuj jako 'Household Chemicals'
        - Artykuły spożywcze zaklasyfikuj jako 'Groceries'
        - Napoje alkoholowe zaklasyfikuj jako 'Alcohol'

        Pamiętaj, że jeśli w tekście jest mowa o kilku produktach, każdy z nich musi być osobnym rekordem w tablicy wydatków.
        Na przykład "Kupiłem chleb za 2 funty, mleko za 1 funt i piwo za 3 funty" powinno dać 3 osobne rekordy
        Przeskanuj listę sklepów w UK, aby uniknąć błędnych nazw dodawanych do bazy danych takich jak "Azja" zamiast "Asda" lub "PC Karys" lub "Piscicaris" zamiast "PC Currys"

        Odpowiedz TYLKO strukturą danych w formacie JSON. Upewnij się, że opis jest w języku angielskim.
        """

        user_prompt = f"""
        Wyodrębnij informacje o wydatkach z poniższego tekstu:

        Text: "{text}"
        {relative_date_hint}
        {amount_hint}

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
            if isinstance(expense, dict) and 'amount' in expense:
                if amount is not None:
                    expense['amount'] = amount
                    expense['currency'] = currency

        return expenses

    except Exception as e:
        logger.error(f"Error in extract_with_llm: {str(e)}", exc_info=True)
        return None

def parse_relative_date(text, language='pl'):
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    text_lower = text.lower()

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

    day_words = {
        'pl': {
            'pierwszego': 1, 'pierwszy': 1, 'pierwszym': 1,
            'drugiego': 2, 'drugi': 2, 'drugim': 2,
            'trzeciego': 3, 'trzeci': 3, 'trzecim': 3,
            'czwartego': 4, 'czwarty': 4, 'czwartym': 4,
            'piątego': 5, 'piąty': 5, 'piątym': 5, 'piatego': 5,
            'szóstego': 6, 'szósty': 6, 'szóstym': 6, 'szostego': 6,
            'siódmego': 7, 'siódmy': 7, 'siódmym': 7, 'siodmego': 7,
            'ósmego': 8, 'ósmy': 8, 'ósmym': 8, 'osmego': 8,
            'dziewiątego': 9, 'dziewiąty': 9, 'dziewiątym': 9, 'dziewiatego': 9,
            'dziesiątego': 10, 'dziesiąty': 10, 'dziesiątym': 10, 'dziesiatego': 10
        },
        'en': {
            'first': 1, '1st': 1,
            'second': 2, '2nd': 2,
            'third': 3, '3rd': 3,
            'fourth': 4, '4th': 4,
            'fifth': 5, '5th': 5,
            'sixth': 6, '6th': 6,
            'seventh': 7, '7th': 7,
            'eighth': 8, '8th': 8,
            'ninth': 9, '9th': 9,
            'tenth': 10, '10th': 10
        }
    }

    # 1. Najpierw sprawdź daty względne
    for term, date in relative_terms.get(language, {}).items():
        if term in text_lower:
            return date

    # Sprawdź w drugim języku
    other_lang = 'en' if language == 'pl' else 'pl'
    for term, date in relative_terms.get(other_lang, {}).items():
        if term in text_lower:
            return date

    # 2. Szukaj konkretnej daty w formacie "dzień miesiąc" lub "słowny_dzień miesiąc"
    for lang, month_dict in month_names.items():
        for month_name, month_num in month_dict.items():
            # 2a. Sprawdź wzorzec: cyfra + nazwa miesiąca (np. "2 maja")
            number_pattern = rf'(\d+)[^\d]*{month_name}'
            number_match = re.search(number_pattern, text_lower)
            if number_match:
                day = int(number_match.group(1))
                if 1 <= day <= 31:  # Sprawdź, czy dzień jest w prawidłowym zakresie
                    year = today.year
                    try:
                        return datetime.datetime(year, month_num, day)
                    except ValueError:
                        # Obsługa błędów np. 31 lutego
                        continue  # Kontynuuj szukanie innych wzorców

            # 2b. Sprawdź wzorzec: słowny dzień + nazwa miesiąca (np. "drugiego maja")
            for day_word, day_num in day_words.get(lang, {}).items():
                word_pattern = rf'{day_word}[^\w]*{month_name}'
                word_match = re.search(word_pattern, text_lower)
                if word_match:
                    year = today.year
                    try:
                        return datetime.datetime(year, month_num, day_num)
                    except ValueError:
                        # Obsługa błędów
                        continue

    # 3. Sprawdź format daty w tekście (np. "2023-05-02" lub "02.05.2023")
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
                # Nieprawidłowa data, kontynuuj szukanie
                continue

    return None


def extract_amount_and_currency(text):
    """Wyodrębnia kwotę i walutę z tekstu"""
    # Wzorce kwot z różnymi walutami
    amount_patterns = [
        r'(\d+[,.]\d+)\s*(?:zł|PLN|złotych)',  # np. "9,99 zł"
        r'(\d+[,.]\d+)\s*(?:GBP|£|funtów)',  # np. "9.99 GBP"
        r'(\d+[,.]\d+)',  # np. "9.99" (bez waluty)
    ]

    # Domyślna waluta (GBP)
    currency = 'GBP'

    # Szukaj kwoty i waluty
    for pattern in amount_patterns:
        match = re.search(pattern, text)
        if match:
            amount_str = match.group(1).replace(',', '.')
            amount = float(amount_str)

            # Określ walutę
            if 'zł' in text or 'PLN' in text or 'złotych' in text:
                currency = 'PLN'
                # Jeśli kwota jest w PLN, przelicz na GBP (jeśli potrzebne)
                # Przykładowy kurs: 1 GBP = 5 PLN
                if currency == 'PLN' and Config.CONVERT_CURRENCY:
                    amount = round(amount / 5.0, 2)  # Przeliczenie PLN na GBP

            return amount, currency

    # Jeśli nie znaleziono, zwróć None
    return None, None

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
        Pay special attention to product type to determine the correct category.
        For example:
        - Cleaning products, detergents, soaps should be categorized as 'Household Chemicals'
        - Food items should be categorized as 'Groceries'
        - Alcoholic beverages should be categorized as 'Alcohol'
        
        IMPORTANT: Preserve the original date mentioned in the text. If a specific date like "2nd May" is mentioned, 
        use that date, not today's date.
        
        IMPORTANT: Preserve the original currency. If an amount is in PLN (Polish Złoty), keep it as PLN and don't convert.
        
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