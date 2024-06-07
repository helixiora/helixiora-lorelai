"""Utility functions for the application."""

import logging
import os
import subprocess
from typing import List, Optional, Tuple

import mysql.connector
import redis

from lorelai.utils import load_config


def is_admin(user_id: int) -> bool:
    """Check if the user is an admin.

    Parameters
    ----------
    user_id : int
        The user ID of the user.

    Returns
    -------
    bool
        True if the user is an admin, False otherwise.
    """
    # Implement the actual check logic, assuming user_id == 1 is admin for example
    return user_id == 1


def run_flyway_migrations(host: str, database: str, user: str, password: str) -> Tuple[bool, str]:
    """Run Flyway migrations on the database.

    Parameters
    ----------
    host : str
        The host of the database.
    database : str
        The name of the database.
    user : str
        The username to connect to the database.
    password : str
        The password to connect to the database.

    Returns
    -------
    tuple
        A tuple with a boolean indicating success and a string with the output message.
    """
    try:
        flyway_command = [
            "flyway",
            f"-url=jdbc:mysql://{host}:3306/{database}?useSSL=false",
            f"-user={user}",
            f"-password={password}",
            "-locations=filesystem:db/migrations",
            "migrate",
        ]
        logging.info("Running Flyway migrations")
        result = subprocess.run(flyway_command, capture_output=True, text=True)
        logging.info(result.stdout)
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, f"Flyway migrations failed: {result.stderr}"
    except Exception as e:
        logging.exception("Flyway migration failed")
        return False, str(e)


def get_db_cursor(with_dict: bool = False) -> mysql.connector.cursor.MySQLCursor:
    """Get a database cursor.

    Parameters
    ----------
    with_dict : bool, optional
        Whether to return rows as dictionaries.

    Returns
    -------
    mysql.connector.cursor.MySQLCursor
        A cursor to the database.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=with_dict)
        return cursor
    except mysql.connector.Error:
        logging.exception("Database connection failed")
        raise


def get_query_result(
    query: str, params: tuple = None, fetch_one: bool = False
) -> Optional[List[dict]]:
    """Get the result of a query.

    Parameters
    ----------
    query : str
        The query to execute.
    params : tuple, optional
        The parameters to pass to the query.
    fetch_one : bool, optional
        Whether to fetch one or all results.

    Returns
    -------
    list or dict
        A list of dictionaries containing the results of the query, or a single dictionary.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone() if fetch_one else cursor.fetchall()
                return result
    except mysql.connector.Error:
        logging.exception("Database query failed")
        raise


def get_db_connection(with_db: bool = True) -> mysql.connector.connection.MySQLConnection:
    """Get a database connection.

    Parameters
    ----------
    with_db : bool, optional
        Whether to connect to a database or just the server.

    Returns
    -------
    mysql.connector.connection.MySQLConnection
        A connection to the database.
    """
    try:
        creds = load_config("db")
        if with_db:
            logging.debug(
                f"Connecting to MySQL database: {creds['user']}@{creds['host']}/{creds['database']}"
            )
            conn = mysql.connector.connect(
                host=creds["host"],
                user=creds["user"],
                password=creds["password"],
                database=creds["database"],
            )
        else:
            logging.debug(f"Connecting to MySQL server: {creds['user']}@{creds['host']}")
            conn = mysql.connector.connect(
                host=creds["host"], user=creds["user"], password=creds["password"]
            )
        return conn
    except mysql.connector.Error:
        logging.exception("Database connection failed")
        raise


def check_mysql() -> Tuple[bool, str]:
    """Check if the MySQL database is up and running.

    Returns
    -------
    tuple
        A tuple with a boolean indicating success and a string with the message.
    """
    try:
        get_query_result("SELECT 1", fetch_one=True)
        return True, "MySQL is up and running."
    except mysql.connector.Error as e:
        logging.exception("MySQL check failed")
        return False, str(e)


def check_redis() -> Tuple[bool, str]:
    """Check if the Redis server is up and running.

    Returns
    -------
    tuple
        A tuple with a boolean indicating success and a string with the message.
    """
    try:
        redis_config = load_config("redis")
        logging.debug(f"Connecting to Redis: {redis_config['url']}")
        r = redis.Redis.from_url(redis_config["url"])
        r.ping()
        return True, "Redis is reachable."
    except redis.ConnectionError as e:
        logging.exception("Redis check failed")
        return False, str(e)


def check_flyway() -> Tuple[bool, str]:
    """Check if the Flyway schema version is up to date.

    Returns
    -------
    tuple
        A tuple with a boolean indicating success and a string with the message.
    """
    try:
        version = get_query_result(
            "SELECT MAX(version) as version FROM flyway_schema_history", fetch_one=True
        )
        logging.debug(f"Flyway schema version: {version['version']}")

        if version is None or version["version"] is None:
            return False, "Flyway schema history not found."

        migrations_dir = "./db/migrations"
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

        if version["version"] in last_migration:
            return True, f"Flyway schema version: {version['version']}"

        return (
            False,
            f"Flyway schema version {version['version']} is not up to date with last migration {last_migration}.",
        )
    except Exception as e:
        logging.exception("Flyway check failed")
        return False, str(e)


def perform_health_checks() -> List[str]:
    """Perform health checks on the application.

    Returns
    -------
    list
        A list of errors, if any.
    """
    checks = [check_mysql, check_redis, check_flyway]
    errors = []
    for check in checks:
        logging.debug(f"Running check: {check.__name__}")
        success, message = check()
        if not success:
            logging.error(f"Health check failed ({check.__name__}): {message}")
            errors.append(message)
        else:
            logging.info(f"Health check passed ({check.__name__}): {message}")
    return errors
