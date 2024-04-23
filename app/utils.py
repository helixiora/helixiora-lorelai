"""Utility functions for the application."""

import logging
import sqlite3

from lorelai.utils import load_config


def is_admin(google_id: str) -> bool:
    """Check if the user is an admin."""
    return google_id != ""  # Assuming all users are admins for now


# Helper function for database connections
def get_db_connection() -> sqlite3.Connection:
    """Get a database connection.

    Returns
    -------
        conn: a connection to the database

    """
    try:
        conn = load_config("db")
        # check if the db_path is set in the config
        db_path = conn.get("db_path") if conn else "./userdb.sqlite"

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error:
        logging.exception("Database connection failed")
        raise
    else:
        return conn
