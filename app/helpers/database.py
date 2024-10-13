"""Database related helper functions."""

import logging

import mysql.connector
import redis

from lorelai.utils import load_config


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


def get_query_result(query, params=None, fetch_one=False):
    """Get a query result from the database.

    Parameters
    ----------
    query : str
        The query to execute.
    params : list, optional
        The parameters to pass to the query.
    fetch_one : bool, optional
        Whether to fetch only one result.

    Returns
    -------
    list
        A list of results.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, params)
            if fetch_one:
                result = cursor.fetchone()
            else:
                result = cursor.fetchall()
            # Ensure all results are read
            cursor.fetchall()
        return result
    finally:
        conn.close()


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
            conn = mysql.connector.connect(
                host=creds["host"],
                user=creds["user"],
                password=creds["password"],
                database=creds["database"],
            )
        else:
            conn = mysql.connector.connect(
                host=creds["host"], user=creds["user"], password=creds["password"]
            )
        return conn
    except mysql.connector.Error:
        logging.exception("Database connection failed")
        raise


def check_mysql() -> tuple[bool, str]:
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


def check_redis() -> tuple[bool, str]:
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


def perform_health_checks() -> list[str]:
    """Perform health checks on the application.

    Returns
    -------
    list
        A list of errors, if any.
    """
    checks = [check_mysql, check_redis]
    errors = []
    for check in checks:
        logging.debug(f"Running check: {check.__name__}")
        success, message = check()
        if not success:
            logging.error(f"Health check failed ({check.__name__}): {message}")
            errors.append(message)
        else:
            logging.debug(f"Health check passed ({check.__name__}): {message}")
    return errors
