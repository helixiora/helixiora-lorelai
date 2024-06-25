"""Utility functions for the application."""

import logging
import os
import subprocess
from functools import wraps

import mysql.connector
import redis
from flask import redirect, session, url_for

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


def role_required(role_name_list):
    """Check if the user has the required role."""

    def wrapper(f):
        """Define the wrapper function. This is the actual decorator."""

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "role" not in session or session["role"] not in role_name_list:
                return redirect(url_for("unauthorized"))
            return f(*args, **kwargs)

        return decorated_function

    return wrapper


def run_flyway_migrations(host: str, database: str, user: str, password: str) -> tuple[bool, str]:
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
) -> list[dict] | None:
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
        logging.debug(f"Executing query: {query}")
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


def check_flyway() -> tuple[bool, str]:
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
            f"Flyway schema version {version['version']} is not up to date with last \
                migration {last_migration}.",
        )
    except Exception as e:
        logging.exception("Flyway check failed")
        return False, str(e)


def perform_health_checks() -> list[str]:
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


def get_user_role(email: str):
    """Get the role of a user by email."""
    with get_db_connection() as db:
        try:
            cursor = db.cursor()
            query = """
                SELECT roles.role_name
                FROM users
                JOIN user_roles ON users.user_id = user_roles.user_id
                JOIN roles ON user_roles.role_id = roles.role_id
                WHERE users.email = %s;
            """
            cursor.execute(query, (email,))
            role_name = cursor.fetchone()[0]
            return role_name

        except Exception:
            logging.critical(f"{email} has no role assigned")
            raise ValueError(f"{email} has no role assigned") from None


def user_is_logged_in(session) -> bool:
    """Check if the user is logged in.

    Yhis is very simple now but might be more complex later. Using a function for maintainability

    Parameters
    ----------
    session : dict
        The session object.

    Returns
    -------
    bool
        True if the user is logged in, False otherwise.
    """
    return "user_id" in session


def get_user_id_by_email(email: str) -> int:
    """
    Get the user ID by email.

    Parameters
    ----------
    email : str
        The email of the user.

    Returns
    -------
    int
        The user ID.
    """
    result = get_query_result("SELECT user_id FROM user WHERE email = %s", (email,), fetch_one=True)
    return result["user_id"] if result else None


def get_organisation_by_org_id(cursor, org_id: int):
    """Get the organization name by ID."""
    org_result = get_query_result(
        "SELECT name FROM organisation WHERE id = %s", (org_id,), fetch_one=True
    )
    if org_result:
        return org_result["name"]

    return None


def get_org_id_by_userid(cursor, user_id: int):
    """Get the organization ID for a user."""
    org_result = get_query_result(
        "SELECT org_id FROM user WHERE user_id = %s", (user_id,), fetch_one=True
    )

    if org_result:
        return org_result["org_id"]

    return None


def get_org_id_by_organisation(
    cursor, organisation: str, create_if_not_exists: bool = False
) -> (int, bool):
    """
    Get the organization ID, inserting the organization if it does not exist.

    Parameters
    ----------
    cursor : mysql.connector.cursor.MySQLCursor
        The database cursor with dictionary=True.
    organisation : str
        The name of the organisation.
    create_if_not_exists : bool, optional
        Whether to create the organisation if it does not exist (default is False).

    Returns
    -------
    tuple
        A tuple containing:
        - int: The organisation ID.
        - bool: Whether the organisation was created.
    """
    try:
        # Query to find the organization by name
        query = "SELECT id FROM organisation WHERE name = %s"
        cursor.execute(query, (organisation,))
        org_result = cursor.fetchone()

        if org_result:
            logging.debug("Organisation found: %s", org_result["id"])
            return org_result["id"], False

        if create_if_not_exists:
            logging.debug("Creating organisation: %s", organisation)
            insert_query = "INSERT INTO organisation (name) VALUES (%s)"
            cursor.execute(insert_query, (organisation,))
            cursor.connection.commit()
            return cursor.lastrowid, True

        logging.debug("Organisation not found and not created: %s", organisation)
        return None, False

    except Exception as e:
        logging.error("Error occurred while getting or creating organisation: %s", e)
        raise


def get_user_email_by_id(cursor, user_id: int):
    """Get the email of a user by ID."""
    cursor.execute("SELECT email FROM user WHERE user_id = %s", (user_id,))
    user_result = cursor.fetchone()
    if user_result:
        return user_result["email"]
