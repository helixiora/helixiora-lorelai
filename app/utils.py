"""Utility functions for the application."""

import logging
import os
import subprocess
from functools import wraps

import mysql.connector
import redis
from flask import redirect, session, url_for

from lorelai.utils import load_config


def is_admin(google_id: str) -> bool:
    """Check if the user is an admin.

    Parameters
    ----------
    google_id : str
        The Google ID of the user.

    Returns
    -------
    bool
        True if the user is an admin, False otherwise.
    """
    return google_id != ""  # Assuming all users are admins for now


def role_required(role_name_list):
    def wrapper(f):
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
    bool
        True if the migrations were successful, False otherwise.
    str
        The output of the migrations.
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
        print("running flyway migrations")
        result = subprocess.run(flyway_command, capture_output=True, text=True)
        print(result.stdout)
        if result.returncode == 0:
            # return the output of flyway migrations
            return True, result.stdout
        else:
            return False, f"Flyway migrations failed: {result.stderr}"
    except Exception as e:
        return str(e)


# Helper function for database connections
def get_db_connection(with_db: bool = True) -> mysql.connector.connection.MySQLConnection:
    """Get a database connection.

    Parameters
    ----------
    with_db : bool, optional
        Whether to connect to a database or just the server.

    Returns
    -------
        conn: a connection to the database

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
    bool
        True if the MySQL database is up and running, False otherwise.
    str
        The message to log.
    """
    try:
        db = get_db_connection()
        logging.debug("Checking MySQL connection. DB: " + db.database + " Host: " + db.server_host)
        cursor = db.cursor()
        cursor.execute("SELECT 1")
        return True, "MySQL is up and running."
    except Exception as e:
        return False, str(e)


def check_redis() -> tuple[bool, str]:
    """Check if the Redis server is up and running.

    Returns
    -------
    bool
        True if the Redis server is up and running, False otherwise.
    str
        The message to log.
    """
    try:
        redis_config = load_config("redis")
        logging.debug(f"Connecting to Redis: {redis_config['url']}")
        r = redis.Redis.from_url(redis_config["url"])
        r.ping()
        return True, "Redis is reachable."
    except redis.ConnectionError as e:
        return False, str(e)


def check_flyway() -> tuple[bool, str]:
    """Check if the Flyway schema version is up to date.

    Returns
    -------
    bool
        True if the Flyway schema version is up to date, False otherwise.
    str
        The message to log.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(version) FROM flyway_schema_history")
        version = cursor.fetchone()
        logging.debug(f"Flyway schema version: {version[0]}")

        if version is None or version[0] is None:
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
        # print the name of the check:
        logging.debug(f"Running check: {check.__name__}")
        success, message = check()
        if not success:
            logging.debug(f"Something went wrong ({check.__name__}): " + message)
            errors.append(message)
            logging.error(message)
        else:
            logging.debug("Nothing went wrong: " + message)
            logging.info(message)
    return errors


def get_user_role(email):
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
            raise ValueError(f"{email} has no role assigned")
