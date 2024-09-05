"""User related helper functions."""

import logging
from functools import wraps
import mysql

from flask import redirect, session, url_for

from app.helpers.database import get_db_connection, get_query_result


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
            query = "INSERT IGNORE INTO user (org_id, email) VALUES (%s, %s)"
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


def register_user_to_org(
    email: str, full_name: str, organisation: str, google_id: str
) -> (bool, str, int, int):
    """
    Register a user to an organisation.

    Parameters
    ----------
    email : str
        The user's email.
    full_name : str
        The user's full name.
    organisation : str
        The organisation name.
    google_id : str
        The Google ID.

    Returns
    -------
    tuple
        A tuple containing a boolean indicating success, a message, the user ID, and the
        organisation ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # check if the organisation exists
        org_id, created_new_org = get_org_id_by_organisation(
            conn=conn, organisation=organisation, create_if_not_exists=True
        )

        # insert the user
        user_id, user_created_success = insert_user(
            cursor, org_id, full_name, email, full_name, google_id
        )

        # if created = True, this is the first user of the org so make them an org_admin by
        # inserting a record in the user_roles table
        if user_created_success and created_new_org:
            # get the role_id of the org_admin role
            cursor.execute("SELECT role_id FROM roles WHERE role_name = 'org_admin'")
            result = cursor.fetchone()
            if not result:
                raise ValueError("Role 'org_admin' not found in the database.")
            role_id = result["role_id"]

            cursor.execute(
                "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)",
                (user_id, role_id),
            )

        conn.commit()

        return True, "Registration successful!", user_id, org_id

    except Exception as e:
        logging.error("An error occurred: %s", e)
        conn.rollback()
        return False, f"An error occurred: {e}", -1

    finally:
        cursor.close()
        conn.close()


def insert_user(
    cursor, org_id: int, name: str, email: str, full_name: str, google_id: str
) -> (int, bool):
    """Insert a new user and return the user ID."""
    cursor.execute(
        "INSERT INTO user (org_id, user_name, email, full_name, google_id) \
            VALUES (%s, %s, %s, %s, %s)",
        (org_id, name, email, full_name, google_id),
    )

    # return lastrowid if the insert was successful
    user_id = cursor.lastrowid
    if user_id:
        return user_id, True
    return -1, False


def validate_form(email: str, name: str, organisation: str):
    """Validate the registration form.

    Parameters
    ----------
    email : str
        The user's email.
    name : str
        The user's name.
    organisation : str
        The user's organisation.

    Returns
    -------
    list
        A list of missing fields.
    """
    missing_fields = []

    if not email:
        missing_fields.append("email")
    if not name:
        missing_fields.append("name")
    if not organisation:
        missing_fields.append("organisation")

    return missing_fields
