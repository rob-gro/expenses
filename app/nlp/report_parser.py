import logging
import datetime
import re

logger = logging.getLogger(__name__)

# Category detection (bilingual)
category_patterns = {
    'Fuel': ['fuel', 'gas', 'petrol', 'gasoline', 'paliwo', 'benzyna', 'tankowanie'],
    'Groceries': ['food', 'groceries', 'grocery', 'żywność', 'jedzenie', 'spożywcze', 'artykuły spożywcze'],
    'Utilities': ['utilities', 'bills', 'rachunki', 'media', 'opłaty', 'prąd', 'gaz', 'woda'],
    'Rent': ['rent', 'czynsz', 'mieszkanie', 'wynajem', 'housing', 'apartment'],
    'Entertainment': ['entertainment', 'fun', 'rozrywka', 'zabawa', 'kino', 'film', 'movies'],
    'Transportation': ['transportation', 'transport', 'travel', 'podróż', 'przejazd', 'komunikacja'],
    'Healthcare': ['healthcare', 'health', 'medical', 'doctor', 'zdrowie', 'lekarz', 'medyczne'],
    'Clothing': ['clothing', 'clothes', 'ubrania', 'odzież', 'buty', 'shoes', 'apparel'],
    'Education': ['education', 'school', 'learning', 'edukacja', 'szkoła', 'studia', 'nauka', 'kursy'],
    'Other': ['other', 'misc', 'miscellaneous', 'inne', 'pozostałe', 'różne'],
    'Alcohol': ['alcohol', 'liquor', 'beer', 'wine', 'alkohol', 'piwo', 'wino', 'wódka', 'drink'],
    'Tools': ['tools', 'hardware', 'narzędzia', 'sprzęt', 'elektronarzędzia'],
    'Office supplies': ['office', 'supplies', 'stationery', 'biurowe', 'papiernicze', 'artykuły biurowe'],
    'Materials': ['materials', 'supplies', 'materiały', 'surowce', 'budowlane'],
    'Insurance': ['insurance', 'ubezpieczenie', 'polisa', 'oc', 'ac'],
    'Household Chemicals': ['household', 'chemicals', 'cleaning', 'chemię domową', 'środki czystości', 'detergenty']
}


def parse_report_command(transcription):
    """
    Parse report command in both English and Polish without translation.

    Analyzes transcription text to extract report parameters including:
    - category
    - date range
    - grouping method
    - report format

    Args:
        transcription (str): Transcribed text containing report command

    Returns:
        dict: Dictionary containing extracted report parameters
    """
    original_transcription = transcription
    transcription = transcription.lower()
    logger.info(f"Processing command: '{transcription}'")

    # Detect language
    is_english = True
    polish_chars = ['ą', 'ć', 'ę', 'ł', 'ń', 'ó', 'ś', 'ź', 'ż']
    polish_words = ['raport', 'wydatki', 'koszty', 'tydzień', 'miesiąc', 'rok', 'przez']

    if any(char in transcription for char in polish_chars) or any(word in transcription for word in polish_words):
        is_english = False
        logger.info("Detected Polish command - processing directly")
    else:
        logger.info("Detected English command - processing directly")

    params = {
        'category': None,
        'start_date': None,
        'end_date': None,
        'group_by': 'month',
        'format': 'pdf'
    }

    # Scan for category in any language
    for category, patterns in category_patterns.items():
        for pattern in patterns:
            if pattern in transcription:
                params['category'] = category
                logger.info(f"Detected category: {category} (matched: {pattern})")
                break
        if params['category']:
            break

    # Group by detection (bilingual)
    if is_english:
        if any(g in transcription for g in ['week', 'weekly', 'by week']):
            params['group_by'] = 'week'
        elif any(g in transcription for g in ['day', 'daily', 'by day']):
            params['group_by'] = 'day'
        elif any(g in transcription for g in ['year', 'yearly', 'annual']):
            params['group_by'] = 'year'
    else:
        if any(g in transcription for g in ['tydzień', 'tygodni', 'przez tydzień', 'grupę przez tydzień']):
            params['group_by'] = 'week'
        elif any(g in transcription for g in ['dzień', 'dziennie', 'codziennie']):
            params['group_by'] = 'day'
        elif any(g in transcription for g in ['rok', 'rocznie', 'przez rok']):
            params['group_by'] = 'year'

    logger.info(f"Selected grouping: {params['group_by']}")

    # Year detection
    year_match = re.search(r'\b(20\d{2})\b', transcription)
    if year_match:
        year = int(year_match.group(1))
        params['start_date'] = f"{year}-01-01"
        params['end_date'] = f"{year}-12-31"
    elif any(phrase in transcription for phrase in ['this year', 'current year', 'tym roku', 'bieżącym roku']):
        year = datetime.datetime.now().year
        params['start_date'] = f"{year}-01-01"
        params['end_date'] = f"{year}-12-31"

    if params['start_date']:
        logger.info(f"Date range: {params['start_date']} to {params['end_date']}")

    # Format detection
    if "pdf" in transcription:
        params['format'] = 'pdf'
    elif "csv" in transcription:
        params['format'] = 'csv'
    elif "excel" in transcription:
        params['format'] = 'excel'

    logger.info(
        f"Report parameters - Category: {params['category']}, Group by: {params['group_by']}, "
        f"Dates: {params['start_date']} to {params['end_date']}, Format: {params['format']}"
    )

    return params