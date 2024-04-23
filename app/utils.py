"""Utility functions for the application."""

import logging
import mysql.connector

from lorelai.utils import load_config


def is_admin(google_id: str) -> bool:
    """Check if the user is an admin."""
    return google_id != ""  # Assuming all users are admins for now


# Helper function for database connections
def get_db_connection():  # -> MySQLConnection.Connection:
    """Get a database connection.

    Returns
    -------
        conn: a connection to the database

    """
    try:
        creds = load_config("db")
        conn = mysql.connector.connect(
            host=creds["host"],
            user=creds["user"],
            password=creds["password"],
            database=creds["database"],
        )
        return conn
    except mysql.connector.Error:
        logging.exception("Database connection failed")
        raise
