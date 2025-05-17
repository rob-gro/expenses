import pymysql
import datetime
import logging
import json
import re
from config import Config

# Configure logging
logger = logging.getLogger(__name__)


class DBManager:
    """Database manager for expense tracking application"""

    def __init__(self, host, user, password, database):
        """Initialize database connection parameters"""
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self._ensure_database_setup()

    def _get_connection(self):
        """Create and return a database connection"""
        return pymysql.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            database=self.database,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

    def _ensure_database_setup(self):
        """Ensure database tables are set up"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Check if tables exist, if not create them
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS expenses (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            date DATETIME NOT NULL,
                            amount DECIMAL(10, 2) NOT NULL,
                            vendor VARCHAR(255),
                            category VARCHAR(100),
                            description TEXT,
                            creation_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                            audio_file_path VARCHAR(255),
                            transcription TEXT
                        )
                    """)

                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS categories (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            name VARCHAR(100) UNIQUE NOT NULL,
                            parent_category_id INT NULL,
                            FOREIGN KEY (parent_category_id) REFERENCES categories(id)
                        )
                    """)

                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS reports (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            report_type VARCHAR(50) NOT NULL,
                            parameters TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            file_path VARCHAR(255)
                        )
                    """)

                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS pending_categorizations (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            expense_id INT NOT NULL,
                            predicted_category VARCHAR(100),
                            confidence FLOAT,
                            alternative_categories TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            status VARCHAR(20) DEFAULT 'pending',
                            FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE
                        )
                    """)

                    # Check if default categories exist
                    cursor.execute("SELECT COUNT(*) AS count FROM categories")
                    category_count = cursor.fetchone()['count']

                    if category_count == 0:
                        # Insert default categories
                        for category in Config.DEFAULT_CATEGORIES:
                            cursor.execute(
                                "INSERT INTO categories (name) VALUES (%s)",
                                (category,)
                            )

                conn.commit()
                logger.info("Database schema verification completed successfully")

        except Exception as e:
            logger.error(f"Database setup error: {str(e)}", exc_info=True)
            raise

    def check_for_duplicate(self, date, amount, vendor=None, category=None, time_threshold_minutes=5):
        """
        Sprawdza, czy podobny wydatek już istnieje w bazie danych
        Zwraca True jeśli znaleziono duplikat, False w przeciwnym razie
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Ustaw przedział czasowy dla sprawdzenia
                    date_from = date - datetime.timedelta(minutes=time_threshold_minutes)
                    date_to = date + datetime.timedelta(minutes=time_threshold_minutes)

                    # Podstawowe warunki wyszukiwania
                    query = """
                        SELECT id FROM expenses
                        WHERE amount = %s 
                        AND date BETWEEN %s AND %s
                    """
                    params = [amount, date_from, date_to]

                    # Dodaj warunki dla kategorii i sprzedawcy, jeśli podano
                    if vendor:
                        query += " AND vendor = %s"
                        params.append(vendor)

                    if category:
                        query += " AND category = %s"
                        params.append(category)

                    cursor.execute(query, params)
                    result = cursor.fetchone()

                    # Jeśli znaleziono wynik, to mamy duplikat
                    return result is not None

        except Exception as e:
            logger.error(f"Error checking for duplicate: {str(e)}", exc_info=True)
            # W przypadku błędu zakładamy, że to nie duplikat
            return False

    def add_expense(self, date, amount, vendor=None, category=None, description=None,
                    audio_file_path=None, transcription=None, needs_confirmation=False,
                    predicted_category=None, category_confidence=0.0, alternative_categories=None,
                    notification_callback=None):  # Dodany parametr callback
        """
        Add an expense record to the database
        Returns the ID of the newly created expense record, or 0 if it's a duplicate
        """
        try:
            # Sprawdź, czy podobny wydatek już istnieje
            is_duplicate = self.check_for_duplicate(
                date=date,
                amount=amount,
                vendor=vendor,
                category=category,
                time_threshold_minutes=10
            )

            if is_duplicate:
                logger.warning(f"Duplicate expense detected: {date}, {amount}, {vendor}, {category}")
                # Zwracamy 0 jako sygnał, że był to duplikat
                return 0

            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Ensure category exists
                    if category:
                        cursor.execute(
                            "SELECT id FROM categories WHERE name = %s",
                            (category,)
                        )
                        cat_result = cursor.fetchone()

                        if not cat_result:
                            # Create new category if doesn't exist
                            cursor.execute(
                                "INSERT INTO categories (name) VALUES (%s)",
                                (category,)
                            )

                    # Insert expense record
                    cursor.execute("""
                        INSERT INTO expenses 
                        (date, amount, vendor, category, description, audio_file_path, transcription)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        date,
                        amount,
                        vendor or '',
                        category or 'Other',
                        description or '',
                        audio_file_path or '',
                        transcription or ''
                    ))

                    # Get the ID of the last inserted row
                    expense_id = cursor.lastrowid

                    # Jeśli wydatek wymaga potwierdzenia kategorii
                    if needs_confirmation:
                        # Zapisz do tabeli oczekujących kategoryzacji
                        alt_categories_json = json.dumps(alternative_categories or [])

                        cursor.execute("""
                            INSERT INTO pending_categorizations 
                            (expense_id, predicted_category, confidence, alternative_categories)
                            VALUES (%s, %s, %s, %s)
                        """, (
                            expense_id,
                            predicted_category,
                            category_confidence,
                            alt_categories_json
                        ))

                        # Jeśli przekazano callback i wydatek został utworzony
                        if notification_callback and expense_id:
                            # Pobierz kompletne dane wydatku
                            expense = self.get_expense(expense_id)
                            # Wywołaj callback z odpowiednimi argumentami
                            notification_callback(
                                expense=expense,
                                current_category=category,
                                predicted_category=predicted_category,
                                alternatives=alternative_categories or []
                            )

                conn.commit()
                logger.info(f"Added expense record with ID: {expense_id}")
                return expense_id

        except Exception as e:
            logger.error(f"Error adding expense: {str(e)}", exc_info=True)
            raise

    def get_expense(self, expense_id):
        """Get a single expense record by ID"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT 
                            id, date, amount, vendor, category, 
                            description, creation_timestamp, 
                            audio_file_path, transcription
                        FROM expenses
                        WHERE id = %s
                    """, (expense_id,))

                    result = cursor.fetchone()

                    if result:
                        # Convert datetime objects to ISO format strings for JSON serialization
                        result['date'] = result['date'].isoformat()
                        result['creation_timestamp'] = result['creation_timestamp'].isoformat()

                    return result

        except Exception as e:
            logger.error(f"Error getting expense with ID {expense_id}: {str(e)}", exc_info=True)
            return None

    def get_expenses(self, page=1, per_page=10, category=None, start_date=None,
                     end_date=None, vendor=None):
        """
        Get a list of expenses with pagination and filtering
        Returns a tuple of (expenses_list, total_count)
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Build WHERE clause for filtering
                    where_clauses = []
                    params = []

                    if category:
                        where_clauses.append("category = %s")
                        params.append(category)

                    if start_date:
                        where_clauses.append("date >= %s")
                        params.append(start_date)

                    if end_date:
                        where_clauses.append("date <= %s")
                        params.append(end_date)

                    if vendor:
                        where_clauses.append("vendor LIKE %s")
                        params.append(f"%{vendor}%")

                    # Build WHERE clause string
                    where_sql = ""
                    if where_clauses:
                        where_sql = "WHERE " + " AND ".join(where_clauses)

                    # Get total count first
                    count_sql = f"SELECT COUNT(*) as total FROM expenses {where_sql}"
                    cursor.execute(count_sql, params)
                    total = cursor.fetchone()['total']

                    # Calculate offset for pagination
                    offset = (page - 1) * per_page

                    # Get paginated results
                    query_sql = f"""
                        SELECT 
                            id, date, amount, vendor, category, 
                            description, creation_timestamp
                        FROM expenses
                        {where_sql}
                        ORDER BY date DESC
                        LIMIT %s OFFSET %s
                    """

                    # Add pagination parameters
                    params.extend([per_page, offset])

                    cursor.execute(query_sql, params)
                    expenses = cursor.fetchall()

                    # Convert datetime objects to strings for JSON serialization
                    for expense in expenses:
                        expense['date'] = expense['date'].isoformat()
                        expense['creation_timestamp'] = expense['creation_timestamp'].isoformat()

                    return expenses, total

        except Exception as e:
            logger.error(f"Error retrieving expenses: {str(e)}", exc_info=True)
            return [], 0

    def get_pending_categorization(self, expense_id):
        """Get pending categorization for an expense"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT 
                            id, expense_id, predicted_category, confidence, 
                            alternative_categories, created_at, status
                        FROM pending_categorizations
                        WHERE expense_id = %s AND status = 'pending'
                    """, (expense_id,))

                    result = cursor.fetchone()

                    if result and result.get('alternative_categories'):
                        try:
                            result['alternative_categories'] = json.loads(result['alternative_categories'])
                        except:
                            result['alternative_categories'] = []

                    return result

        except Exception as e:
            logger.error(f"Error getting pending categorization for expense {expense_id}: {str(e)}", exc_info=True)
            return None

    def update_pending_categorization(self, expense_id, status='confirmed'):
        """Update status of pending categorization"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE pending_categorizations
                        SET status = %s
                        WHERE expense_id = %s AND status = 'pending'
                    """, (status, expense_id))

                    if cursor.rowcount > 0:
                        conn.commit()
                        logger.info(f"Updated categorization status for expense {expense_id} to {status}")
                        return True
                    else:
                        logger.warning(f"No pending categorization found for expense {expense_id}")
                        return False

        except Exception as e:
            logger.error(f"Error updating categorization status for expense {expense_id}: {str(e)}", exc_info=True)
            return False


    def update_expense(self, expense_id, **kwargs):
        """
        Update an expense record
        Returns True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Build SET part of the query
                    set_parts = []
                    params = []

                    # Process each update field
                    allowed_fields = ['date', 'amount', 'vendor', 'category', 'description']
                    for field, value in kwargs.items():
                        if field in allowed_fields and value is not None:
                            set_parts.append(f"{field} = %s")
                            params.append(value)

                    if not set_parts:
                        logger.warning("No valid fields provided for update")
                        return False

                    # Add expense ID to parameters
                    params.append(expense_id)

                    # Execute update query
                    query = f"""
                        UPDATE expenses 
                        SET {", ".join(set_parts)}
                        WHERE id = %s
                    """

                    cursor.execute(query, params)

                    if cursor.rowcount > 0:
                        conn.commit()
                        logger.info(f"Updated expense record with ID: {expense_id}")
                        return True
                    else:
                        logger.warning(f"No expense found with ID: {expense_id}")
                        return False

        except Exception as e:
            logger.error(f"Error updating expense with ID {expense_id}: {str(e)}", exc_info=True)
            return False

    def delete_expense(self, expense_id):
        """
        Delete an expense record
        Returns True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))

                    if cursor.rowcount > 0:
                        conn.commit()
                        logger.info(f"Deleted expense record with ID: {expense_id}")
                        return True
                    else:
                        logger.warning(f"No expense found with ID: {expense_id}")
                        return False

        except Exception as e:
            logger.error(f"Error deleting expense with ID {expense_id}: {str(e)}", exc_info=True)
            return False

    def get_all_expenses_for_training(self):
        """Get all expenses with transcription for model training"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT 
                            id, date, amount, vendor, category, 
                            description, transcription
                        FROM expenses
                        WHERE transcription IS NOT NULL
                        ORDER BY date
                    """)

                    expenses = cursor.fetchall()
                    return expenses

        except Exception as e:
            logger.error(f"Error retrieving training expenses: {str(e)}", exc_info=True)
            return []

    def get_all_categories(self):
        """Get all expense categories"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT name FROM categories ORDER BY name")
                    categories = cursor.fetchall()
                    return [category['name'] for category in categories]

        except Exception as e:
            logger.error(f"Error retrieving categories: {str(e)}", exc_info=True)
            return Config.DEFAULT_CATEGORIES  # Fallback to default categories

    def add_category(self, name):
        """Add a category to the database if it doesn't exist already"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Check if exists (case insensitive)
                    cursor.execute(
                        "SELECT id, name FROM categories WHERE LOWER(name) = LOWER(%s)",
                        (name,)
                    )
                    existing = cursor.fetchone()

                    if existing:
                        return False, f"Category '{existing['name']}' already exists"

                    # Add new category
                    cursor.execute(
                        "INSERT INTO categories (name) VALUES (%s)",
                        (name,)
                    )

                    conn.commit()
                    category_id = cursor.lastrowid
                    logger.info(f"Added new category: '{name}' with ID: {category_id}")
                    return True, f"Successfully added category '{name}'"
        except Exception as e:
            logger.error(f"Error adding category: {str(e)}", exc_info=True)
            return False, f"Database error: {str(e)}"

    def add_report(self, report_type, parameters, file_path):
        """
        Add a report record to the database
        Returns the ID of the newly created report record
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO reports 
                        (report_type, parameters, file_path)
                        VALUES (%s, %s, %s)
                    """, (
                        report_type,
                        parameters,
                        file_path
                    ))

                    # Get the ID of the last inserted row
                    report_id = cursor.lastrowid

                conn.commit()
                logger.info(f"Added report record with ID: {report_id}")
                return report_id

        except Exception as e:
            logger.error(f"Error adding report: {str(e)}", exc_info=True)
            raise

    def get_expense_data_for_report(self, category=None, start_date=None, end_date=None, group_by='month'):
        """
        Get expense data for report generation with grouping options
        Returns a list of expenses grouped by the specified period
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Build WHERE clause for filtering
                    where_clauses = []
                    params = []

                    if category:
                        where_clauses.append("category = %s")
                        params.append(category)

                    if start_date:
                        where_clauses.append("date >= %s")
                        params.append(start_date)

                    if end_date:
                        where_clauses.append("date <= %s")
                        params.append(end_date)

                    # Build WHERE clause string
                    where_sql = ""
                    if where_clauses:
                        where_sql = "WHERE " + " AND ".join(where_clauses)

                    # Escape all % in SQL by doubling them to avoid format string issues
                    # Set group by expression based on period
                    if group_by == 'day':
                        group_expr = "DATE(date)"
                        period_format = "DATE_FORMAT(date, '%%Y-%%m-%%d')"
                    elif group_by == 'week':
                        group_expr = "YEARWEEK(date, 1)"  # Mode 1: weeks start on Monday
                        period_format = "CONCAT(YEAR(date), '-', WEEKOFYEAR(date))"
                    elif group_by == 'month':
                        group_expr = "DATE_FORMAT(date, '%%Y-%%m-01')"
                        period_format = "DATE_FORMAT(date, '%%Y-%%m')"
                    elif group_by == 'year':
                        group_expr = "YEAR(date)"
                        period_format = "CAST(YEAR(date) AS CHAR)"
                    else:
                        # Default to month
                        group_expr = "DATE_FORMAT(date, '%%Y-%%m-01')"
                        period_format = "DATE_FORMAT(date, '%%Y-%%m')"

                    # Query for grouped data with escaped % characters
                    query = f"""
                        SELECT 
                            {group_expr} AS period,
                            {period_format} AS period_label,
                            category,
                            SUM(amount) AS total_amount,
                            COUNT(*) AS transaction_count
                        FROM expenses
                        {where_sql}
                        GROUP BY period, category
                        ORDER BY period, category
                    """

                    cursor.execute(query, params)
                    grouped_data = cursor.fetchall()

                    # Query for individual expenses (for detailed reports)
                    query = f"""
                        SELECT 
                            id, date, amount, vendor, category, description
                        FROM expenses
                        {where_sql}
                        ORDER BY date, category
                    """

                    cursor.execute(query, params)
                    detailed_data = cursor.fetchall()

                    # Convert datetime objects to strings for JSON serialization
                    for expense in detailed_data:
                        expense['date'] = expense['date'].isoformat()

                    return {
                        'grouped': grouped_data,
                        'detailed': detailed_data
                    }

        except Exception as e:
            logger.error(f"Error retrieving report data: {str(e)}", exc_info=True)
            return {'grouped': [], 'detailed': []}