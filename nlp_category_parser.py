import logging
import re
import datetime
from openai import OpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam
from config import Config

logger = logging.getLogger(__name__)


def extract_date_range_from_text(text):

    if not text:
        return None, None

    # Convert text to lowercase for matching
    text_lower = text.lower()

    # Get current date for relative calculations
    current_date = datetime.datetime.now()
    current_year = current_date.year
    current_month = current_date.month

    # Initialize result
    start_date = None
    end_date = None

    # --- Year handling ---

    # Check for specific year mentions
    year_pattern = r'rok\s+(\d{4})|(\d{4})\s+rok|w\s+(\d{4})|for\s+(\d{4})|in\s+(\d{4})'
    year_match = re.search(year_pattern, text_lower)

    if year_match:
        # Get the first non-None match group which contains the year
        year = next((group for group in year_match.groups() if group), None)
        if year:
            year = int(year)
            # Set range for the entire year
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"
            logger.info(f"Detected year range: {year} -> {start_date} to {end_date}")

    # --- Fiscal/Tax year handling ---

    # UK tax year: April 6 to April 5 of following year
    uk_tax_year_pattern = r'rok\s+podatkowy\s+(\d{4})[\s/-]+(\d{4})|tax\s+year\s+(\d{4})[\s/-]+(\d{4})'
    uk_tax_match = re.search(uk_tax_year_pattern, text_lower)

    if uk_tax_match:
        # Extract years from match groups
        groups = uk_tax_match.groups()
        if groups[0] and groups[1]:  # Polish format
            start_year, end_year = int(groups[0]), int(groups[1])
        elif groups[2] and groups[3]:  # English format
            start_year, end_year = int(groups[2]), int(groups[3])
        else:
            # If no specific years provided, use current and next year
            start_year, end_year = current_year, current_year + 1

        # UK tax year: April 6 to April 5
        start_date = f"{start_year}-04-06"
        end_date = f"{end_year}-04-05"
        logger.info(f"Detected UK tax year: {start_year}-{end_year} -> {start_date} to {end_date}")

    # UK accounting year: Any 12-month period (commonly April 1 to March 31)
    uk_accounting_pattern = r'rok\s+obrachunkowy|accounting\s+year|fiscal\s+year'
    if re.search(uk_accounting_pattern, text_lower) and not uk_tax_match:
        # If a specific year is mentioned along with accounting year
        year_in_text = re.search(r'(\d{4})', text_lower)
        if year_in_text:
            year = int(year_in_text.group(1))
            # Assume standard accounting year April to March
            if "poprzedni" in text_lower or "last" in text_lower or "previous" in text_lower:
                start_date = f"{year - 1}-04-01"
                end_date = f"{year}-03-31"
            else:
                start_date = f"{year}-04-01"
                end_date = f"{year + 1}-03-31"
        else:
            # If no specific year mentioned, use current accounting year
            if current_month < 4:  # January to March
                start_date = f"{current_year - 1}-04-01"
                end_date = f"{current_year}-03-31"
            else:  # April to December
                start_date = f"{current_year}-04-01"
                end_date = f"{current_year + 1}-03-31"

        logger.info(f"Detected accounting year -> {start_date} to {end_date}")

    # --- Month handling ---

    # Check for specific month mentions
    months_pl = {
        'styczeń': 1, 'stycznia': 1, 'styczniu': 1,
        'luty': 2, 'lutego': 2, 'lutym': 2,
        'marzec': 3, 'marca': 3, 'marcu': 3,
        'kwiecień': 4, 'kwietnia': 4, 'kwietniu': 4,
        'maj': 5, 'maja': 5, 'maju': 5,
        'czerwiec': 6, 'czerwca': 6, 'czerwcu': 6,
        'lipiec': 7, 'lipca': 7, 'lipcu': 7,
        'sierpień': 8, 'sierpnia': 8, 'sierpniu': 8,
        'wrzesień': 9, 'września': 9, 'wrześniu': 9,
        'październik': 10, 'października': 10, 'październiku': 10,
        'listopad': 11, 'listopada': 11, 'listopadzie': 11,
        'grudzień': 12, 'grudnia': 12, 'grudniu': 12
    }

    months_en = {
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

    # If we already found a year range, don't override with month detection
    if not start_date and not end_date:
        # Check for month mentions
        for month_name, month_num in {**months_pl, **months_en}.items():
            if month_name in text_lower:
                # Check if a specific year is mentioned with this month
                year_with_month = re.search(fr'{month_name}\s+(\d{{4}})|(\d{{4}})\s+{month_name}', text_lower)

                year = current_year
                if year_with_month:
                    # Extract year from the match
                    groups = year_with_month.groups()
                    extracted_year = next((group for group in groups if group), None)
                    if extracted_year:
                        year = int(extracted_year)

                # Set range for the specific month
                start_date = f"{year}-{month_num:02d}-01"

                # Calculate last day of month
                if month_num == 2:  # February
                    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):  # Leap year
                        end_date = f"{year}-{month_num:02d}-29"
                    else:
                        end_date = f"{year}-{month_num:02d}-28"
                elif month_num in [4, 6, 9, 11]:  # 30 days
                    end_date = f"{year}-{month_num:02d}-30"
                else:  # 31 days
                    end_date = f"{year}-{month_num:02d}-31"

                logger.info(f"Detected month: {month_name} {year} -> {start_date} to {end_date}")
                break

    # --- Period handling ---

    # Check for "last X months/years" patterns
    last_period_pattern = r'(ostatnich|ostatnie|last|past)\s+(\d+)\s+(miesiące|miesięcy|miesiąca|months|month|lat|years|year)'
    last_period_match = re.search(last_period_pattern, text_lower)

    if last_period_match and not start_date and not end_date:
        number = int(last_period_match.group(2))
        period_type = last_period_match.group(3).lower()

        end_date = current_date.strftime('%Y-%m-%d')

        if 'miesiąc' in period_type or 'month' in period_type:
            # Last X months
            start_date = (current_date - datetime.timedelta(days=30 * number)).strftime('%Y-%m-%d')
        elif 'lat' in period_type or 'year' in period_type:
            # Last X years
            start_date = (current_date.replace(year=current_date.year - number)).strftime('%Y-%m-%d')

        logger.info(f"Detected relative period: last {number} {period_type} -> {start_date} to {end_date}")

    # --- Date range handling ---

    # Look for "between" or "from X to Y" patterns
    between_pattern = r'(pomiędzy|między|between|from)\s+(.+?)\s+(a|i|and|to)\s+(.+?)\b'
    between_match = re.search(between_pattern, text_lower)

    if between_match and not start_date:
        # This is more complex and would require date parsing logic
        # For demonstration, we'll just log that it was detected
        logger.info(f"Detected between pattern: {between_match.group(0)}")
        # Advanced implementation would parse the dates in the range
        # This would require NLP date parsing capabilities

    # If no specific dates found, default to current year
    if not start_date and not end_date and "rok" in text_lower or "year" in text_lower:
        start_date = f"{current_year}-01-01"
        end_date = f"{current_year}-12-31"
        logger.info(f"No specific date range found, defaulting to current year: {start_date} to {end_date}")

    return start_date, end_date

def extract_category_from_text(text, categories):
    """
    Extract expense category from text by checking for matches with known categories.

    Args:
        text (str): The input text to analyze
        categories (list): List of valid expense categories

    Returns:
        str or None: Matched category or None if no category was found
    """
    if not text or not categories:
        return None

    # Convert text to lowercase for case-insensitive matching
    text_lower = text.lower()

    # Common words that indicate report requests
    report_indicators = [
        'raport', 'report', 'zestawienie', 'podsumowanie', 'wyślij',
        'wyciąg', 'summary', 'statement', 'send me', 'wszystkie', 'wydatki'
    ]

    # Check if text contains report request indicators
    is_report_request = any(indicator in text_lower for indicator in report_indicators)

    if not is_report_request:
        return None

    # Find category mentions in text
    for category in categories:
        # Search for exact category name (case insensitive)
        if category.lower() in text_lower:
            return category

        # Additional handling for specific categories that might be mentioned differently
        if category.lower() == 'fuel' and any(
                word in text_lower for word in ['benzyna', 'paliwo', 'diesel', 'gas', 'petrol', 'gasoline', 'ropa']):
            return 'Fuel'
        elif category.lower() == 'groceries' and any(
                word in text_lower for word in ['żywność', 'jedzenie', 'food', 'spożywcze', 'żarcie']):
            return 'Groceries'
        elif category.lower() == 'utilities' and any(
                word in text_lower for word in ['prąd', 'gaz', 'woda', 'media', 'electricity', 'water']):
            return 'Utilities'

    # If text is a report request but no specific category was found,
    # check if "all" or "wszystkie" is mentioned, implying a full report
    if any(word in text_lower for word in ['all', 'wszystkie', 'całość']):
        # Return None for all categories report
        return None

    return None


