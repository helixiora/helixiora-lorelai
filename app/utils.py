import sqlite3
import logging
from contextlib import closing
from typing import Dict

from lorelai.utils import load_config

def is_admin(google_id):
    # Implement your logic to verify if the google_id belongs to an admin
    return True

# Helper function for database connections
def get_db_connection() -> sqlite3.Connection:
    """Get a database connection

    Returns:
        conn: a connection to the database
    """
    try:
        conn = load_config('db')
        
        conn = sqlite3.connect(conn['db_path'])
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Database connection failed: {e}")
        raise e

def get_user_details() -> Dict[str, str]:
    """Fetches details of the currently logged-in user from the database.
    Returns:
        A dictionary with user details or an empty dictionary if not found.
    """
    required_keys = ['google_id', 'email']
    if not all(key in session for key in required_keys):
        return {}  # Returns an empty dictionary if required keys are missing

    logging.debug("SESSION: %s", session)
    email = session['email']

    try:
        with get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                user_details = cursor.execute("""
                    SELECT u.name, u.email, o.name AS org_name
                    FROM users u
                    INNER JOIN organisations o ON u.org_id = o.id
                    WHERE u.email = ?
                """, (email,)).fetchone()
                if user_details:
                    return {key: user_details[key] for key in ['name', 'email', 'org_name']}
                return {}  # Returns an empty dictionary if no user details are found
    except RuntimeError as e:  # Consider narrowing this to specific exceptions
        logging.error("Failed to fetch user details: %s", e, exc_info=True)
        return {}  # Returns an empty dictionary in case of an exception