"""Utility functions for the application.
"""
import sqlite3

from lorelai.utils import load_config

def is_admin(google_id: str) -> bool:
    """Check if the user is an admin
    """
    return google_id >= 0   # Assuming all users are admins for now

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
