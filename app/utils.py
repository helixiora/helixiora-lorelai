"""Utility functions for the application."""

import logging
import os

import mysql.connector
import redis

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
        logging.debug(
            f"Connecting to MySQL database: {creds['user']}@{creds['host']}/{creds['database']}"
        )
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


def check_mysql():
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT 1")
        return True, "MySQL is up and running."
    except Exception as e:
        return False, str(e)


def check_redis():
    try:
        redis_config = load_config("redis")
        logging.debug(f"Connecting to Redis: {redis_config['url']}")
        r = redis.Redis.from_url(redis_config["url"])
        r.ping()
        return True, "Redis is reachable."
    except redis.ConnectionError as e:
        return False, str(e)


def check_flyway():
    # Assuming you have a way to check Flyway's current schema version
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(version) FROM flyway_schema_history")
        version = cursor.fetchone()

        if version is None:
            return False, "Flyway schema history not found."

        # get the migrations from disk
        migrations_dir = "./db/migrations"
        # get all the .sql files in the migrations directory in alphabetical order
        migrations = sorted(
            [
                f
                for f in os.listdir(migrations_dir)
                if os.path.isfile(os.path.join(migrations_dir, f)) and f.endswith(".sql")
            ]
        )

        if not migrations:
            return False, "No migrations found."

        last_migration = migrations[-1]

        # this checks if eg. '1.2' is in 'V1.2__Rename_expires_in_to_expiry.sql'
        if version[0] in last_migration:
            return True, f"Flyway schema version: {version[0]}"

        return True, f"Flyway schema version: {version[0]}"

    except Exception as e:
        return False, str(e)


def perform_health_checks():
    checks = [check_mysql, check_redis, check_flyway]
    errors = []
    for check in checks:
        success, message = check()
        if not success:
            errors.append(message)
            logging.error(message)
        else:
            logging.info(message)
    return errors
