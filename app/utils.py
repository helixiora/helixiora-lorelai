"""Utility functions for the application."""

import logging
import os
import re
import subprocess
from datetime import datetime, timedelta
from functools import wraps

import mysql.connector
import redis
from flask import redirect, session, url_for

from lorelai.utils import load_config


def is_org_admin(user_id: int) -> bool:
    """Check if the user is an organization admin.

    Parameters
    ----------
    user_id : int
        The user ID of the user.

    Returns
    -------
    bool
        True if the user is an organization admin, False otherwise.
    """
    if "org_admin" in session["user_roles"]:
        return True
    return False


def is_super_admin(user_id: int) -> bool:
    """Check if the user is a super admin.

    Parameters
    ----------
    user_id : int
        The user ID of the user.

    Returns
    -------
    bool
        True if the user is a super admin, False otherwise.
    """
    if "super_admin" in session["user_roles"]:
        return True
    return False


def is_admin(user_id: int) -> bool:
    """Check if the user is an admin.

    Parameters
    ----------
    user_id : int
        The user ID of the user.

    Returns
    -------
    bool
        True if the user is an admin (both super and org), False otherwise.
    """
    admin_roles = ["org_admin", "super_admin"]
    if any(role in admin_roles for role in session["user_roles"]):
        return True
    return False


def role_required(role_name_list):
    """Check if the user has the required role."""

    def wrapper(f):
        """Define the wrapper function. This is the actual decorator."""

        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if "role" is in session and is a list
            if "user_roles" not in session or not isinstance(session["user_roles"], list):
                return redirect(url_for("unauthorized"))

            # Check if any role in session['user_roles'] is in role_name_list
            if not any(role in role_name_list for role in session["user_roles"]):
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
        logging.debug(f"Flyway command: {' '.join(flyway_command)}")
        result = subprocess.run(flyway_command, capture_output=True, text=True)
        logging.info("Flyway stdout: " + result.stdout)
        if result.returncode == 0:
            logging.info("Flyway migrations successful")
            return True, result.stdout
        else:
            logging.error(f"Flyway migrations failed: {result.stderr}")
            return False, f"Flyway migrations failed: {result.stderr}"
    except Exception as e:
        logging.exception(f"Flyway migration failed with exception: {str(e)}")
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
            "SELECT version \
    FROM flyway_schema_history \
    ORDER BY \
        CAST(SUBSTRING_INDEX(version, '.', 1) AS UNSIGNED) DESC, \
        CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(version, '.', 2), '.', -1) AS UNSIGNED) DESC, \
        CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(version, '.', 3), '.', -1) AS UNSIGNED) DESC \
    LIMIT 1;",
            fetch_one=True,
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
            ],
            key=lambda f: [int(num) for num in re.findall(r"\d+", f)],
        )

        if not migrations:
            return False, "No migrations found."

        last_migration = migrations[-1]

        if version["version"] in last_migration:
            return True, f"Flyway schema version: {version['version']}"

        return (
            False,
            f"Version of the database schema in MySQL {version['version']} is not up to date with \
                last migration file on disk {last_migration}.",
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
            logging.debug(f"Health check passed ({check.__name__}): {message}")
    return errors


def get_user_role_by_id(user_id: str):
    """Get the role of a user by email."""
    with get_db_connection() as db:
        try:
            cursor = db.cursor()
            query = """
                SELECT roles.role_name
                FROM user
                JOIN user_roles ON user.user_id = user_roles.user_id
                JOIN roles ON user_roles.role_id = roles.role_id
                WHERE user.user_id = %s;
            """
            cursor.execute(query, (user_id,))
            roles = cursor.fetchall()
            role_names = [role[0] for role in roles]
            return role_names

        except Exception:
            logging.critical(f"{user_id} has no role assigned")
            raise ValueError(f"{user_id} has no role assigned") from None


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


def get_users(org_id: int = None) -> list[dict] | None:
    """Get the list of users from the user table.

    If an org_id is provided, only users from that organization are returned.

    Parameters
    ----------
    org_id : int, optional
        The organization ID.

    Returns
    -------
    list[dict] | None
        A list of dictionaries containing the users.
    """
    if org_id:
        users = get_query_result(
            "SELECT u.user_id, u.email, u.user_name, o.name as organisation \
            FROM \
                user u \
            LEFT JOIN \
                organisation o on u.org_id = o.id \
            WHERE \
                u.org_id = %s",
            (org_id,),
        )
    else:
        users = get_query_result(
            "SELECT \
                u.user_id, u.email, u.user_name, o.name as organisation \
            FROM \
                user u \
            LEFT JOIN \
                organisation o on u.org_id = o.id"
        )

    # go through all users and add their roles as a list
    for user in users:
        user["roles"] = get_user_role_by_id(user["user_id"])

    return users if users else None


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
    conn: mysql.connector.connection.MySQLConnection,
    organisation: str,
    create_if_not_exists: bool = False,
) -> (int, bool):
    """
    Get the organization ID, inserting the organization if it does not exist.

    Parameters
    ----------
    conn : mysql.connector.connection.MySQLConnection
        The connection to the database.
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
        cursor = conn.cursor(dictionary=True)
        # Query to find the organization by name
        query = "SELECT id FROM organisation WHERE name = %s"
        cursor.execute(query, (organisation,))
        org_result = cursor.fetchone()

        if org_result:
            logging.debug("Organisation found: %s", org_result["id"])
            return org_result["id"], False

        if create_if_not_exists:
            logging.debug("Creating organisation: %s", organisation)
            cursor = conn.cursor(dictionary=False)
            insert_query = "INSERT INTO organisation (name) VALUES (%s)"
            cursor.execute(insert_query, (organisation,))
            conn.commit()
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

    logging.error("No user found for user id: %s", user_id)
    raise ValueError(f"No user found for user id: {user_id}")


def get_datasource_id_by_name(datasource_name: str):
    """Get the organization name by ID."""
    datasource_name_result = get_query_result(
        "SELECT datasource_id FROM datasource WHERE datasource_name = %s",
        (datasource_name,),
        fetch_one=True,
    )
    if datasource_name_result:
        return datasource_name_result["datasource_id"]

    return None


def get_datasources_name():
    """Get the list of datasources from datasource table."""
    with get_db_connection() as db:
        try:
            cursor = db.cursor()
            query = """
                SELECT datasource.datasource_name
                FROM datasource;
            """
            cursor.execute(query)
            datasources = cursor.fetchall()
            datasources = [source[0] for source in datasources]
            return datasources

        except Exception:
            logging.critical("No datasources in datasources table")
            raise ValueError("No datasources in datasources table") from None


def org_exists_by_name(org_name):
    """Get the list of datasources from datasource table."""
    with get_db_connection() as db:
        try:
            cursor = db.cursor()
            query = """
                SELECT name
                FROM organisation WHERE name = %s;
            """
            cursor.execute(query, (org_name,))
            result = cursor.fetchone()

            return result is not None

        except Exception as e:
            logging.error(e)
            raise e


def get_msg_count_last_24hr(user_id: int):
    """
    Retrieve the count of chat messages for a specified user from the last 24 hours.

    Args:
        user_id (int): The ID of the user whose messages are to be counted.

    Returns
    -------
        int: The number of chat messages sent by the specified user in the last 24 hours.

    Raises
    ------
        Exception: If there is an error connecting to the database or executing the query.
    """
    try:
        with get_db_connection() as db:
            past_24_hours_time = datetime.now() - timedelta(days=1)
            cursor = db.cursor()
            query = """
                    SELECT t.user_id, COUNT(m.message_id) AS message_count
            FROM chat_threads t
            JOIN chat_messages m ON t.thread_id = m.thread_id
            WHERE t.user_id = %s AND m.sender = 'bot' and m.created_at >= %s
            GROUP BY t.user_id
                """
            cursor.execute(query, (user_id, past_24_hours_time))
            count = cursor.fetchone()
            if count is None:
                return 0
            return count[1]  # (user_id,message_count)
    except Exception as e:
        logging.error(e)
        raise e


def insert_thread_ignore(thread_id: str, user_id, thread_name=None):
    """
    Insert a new chat thread into the chat_threads table, ignoring the insertion if a duplicate.

    # thread_id exists.

    Args:
        thread_id (str): The unique identifier for the chat thread.
        user_id: The ID of the user who owns the thread.
        thread_name (str, optional): The name of the chat thread. Defaults to None.

    Returns
    -------
        bool: True if the insertion was successful or ignored, False otherwise.

    Raises
    ------
        Exception: Propagates any exception that occurs during the database operation.
    """
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            query = """
            INSERT IGNORE INTO chat_threads (thread_id, user_id, thread_name)
            VALUES (%s, %s, %s)
                """
            thread_data = (thread_id, user_id, thread_name)
            cursor.execute(query, thread_data)
            db.commit()
            return True
    except Exception as e:
        logging.error(e)
        raise e


def insert_message(thread_id: str, sender: str, message_content: str, sources: str = None):
    """
    Insert a new message into the chat_messages table.

    Args:
        thread_id (str): The unique identifier for the chat thread the message belongs to.
        sender (str): The sender of the message.
        message_content (str): The content of the message.
        sources (str, optional): Any sources associated with the message. Defaults to None.

    Returns
    -------
        bool: True if the insertion was successful, False otherwise.

    Raises
    ------
        Exception: Propagates any exception that occurs during the database operation.
    """
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            query = """
            INSERT INTO chat_messages (thread_id, sender, message_content, sources)
            VALUES (%s, %s, %s, %s)
                """
            msg_data = (thread_id, sender, message_content, sources)
            cursor.execute(query, msg_data)
            db.commit()
            return True
    except Exception as e:
        logging.error(e)
        raise e


def list_all_user_threads(user_id: int):
    """
    Retrieve all thread IDs for a given user.

    Args:
        user_id (int): The ID of the user whose threads are to be listed.

    Returns
    -------
        list: A list of thread IDs associated with the user. Returns an empty list if no threads are
        found.

    Raises
    ------
        Exception: If there is an error during the database query.
    """
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            query = """
            SELECT thread_id from chat_threads WHERE user_id = %s;
                """
            cursor.execute(query, (user_id,))
            thread_ids = cursor.fetchall()
            if thread_ids is None:
                return []
            return thread_ids
    except Exception as e:
        logging.error(e)
        raise e


def get_all_thread_messages(thread_id: str):
    """
    Retrieve all messages for a given thread, ordered by creation time.

    Args:
        thread_id (str): The ID of the thread whose messages are to be retrieved.

    Returns
    -------
        list: A list of messages associated with the thread. Each message includes sender,
        message_content, created_at, and sources. Returns an empty list if no messages are found.

    Raises
    ------
        Exception: If there is an error during the database query.
    """
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            query = """
            SELECT sender, message_content, created_at, sources
                FROM chat_messages
                WHERE thread_id = %s
                ORDER BY created_at ASC;
                """
            cursor.execute(query, (thread_id,))
            messages = cursor.fetchall()
            if messages is None:
                return []
            return messages
    except Exception as e:
        logging.error(e)
        raise e


def create_invited_user_in_db(email: str, org_name: str):
    """
    Create an invited user in the database and assign a default role.

    This function performs the following steps:
    1. Retrieves the organization ID (`org_id`) for the given organization name (`org_name`).
       If the organization ID is not found, a ValueError is raised.
    2. Inserts a new user record into the `user` table with the retrieved `org_id` and the provided
       email.
    3. Retrieves the `user_id` of the newly inserted user.
    4. Inserts a record into the `user_roles` table to assign a default role (role_id=3) to the
       newly created user.
    5. Commits the transaction if all steps are successful.

    Args:
        email (str): The email of the invited user.
        org_name (str): The name of the organization to which the user is being invited.

    Returns
    -------
        bool: True if the user was created and the role was assigned successfully, False otherwise.

    Raises
    ------
        ValueError: If the organization ID for the given organization name is not found.
        Exception: If any other error occurs during the database operations.
    """
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            org_id, _ = get_org_id_by_organisation(db, org_name)
            if org_id is None:
                raise ValueError(f"Org_id for {org_name} not found")

            # user table
            query = "INSERT INTO user (org_id, email) VALUES (%s, %s)"
            user_data = (
                org_id,
                email,
            )
            cursor.execute(query, user_data)
            user_id = cursor.lastrowid

            # user role
            query = "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)"
            role_data = (
                user_id,
                3,
            )
            cursor.execute(query, role_data)

            db.commit()
            return True
    except Exception as e:
        logging.error(e)
        raise e
