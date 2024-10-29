"""User related helper functions."""

import logging
from datetime import datetime

from functools import wraps

from flask import redirect, session, url_for

from app.models import User, Organisation, Profile, Role, UserRole, db


def is_org_admin(user_id: int) -> bool:
    """Check if the user is an organisation admin.

    Parameters
    ----------
    user_id : int
        The user ID of the user.

    Returns
    -------
    bool
        True if the user is an organisation admin, False otherwise.
    """
    user = User.query.get(user_id)
    return user.has_role("org_admin") if user else False


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
    user = User.query.get(user_id)
    return user.has_role("super_admin") if user else False


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
    user = User.query.get(user_id)
    return user.has_role("org_admin") or user.has_role("super_admin") if user else False


def role_required(role_name_list):
    """Check if the user has the required role."""

    def wrapper(f):
        """Define the wrapper function. This is the actual decorator."""

        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if "role" is in session and is a list
            if "user.user_roles" not in session or not isinstance(session["user.user_roles"], list):
                return redirect(url_for("unauthorized"))

            # Check if any role in session['user.user_roles'] is in role_name_list
            if not any(role in role_name_list for role in session["user.user_roles"]):
                return redirect(url_for("unauthorized"))

            return f(*args, **kwargs)

        return decorated_function

    return wrapper


def create_invited_user_in_db(email: str, org_id: int):
    """
    Create or update a user with the given email and org_id.

    Args:
        email (str): The email of the user.
        org_id (int): The organisation ID for the user.

    Returns
    -------
        bool: True if the operation was successful.
    """
    try:
        # Check if the user already exists by email
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            # User already exists, no need to insert
            logging.info(f"User with email {email} already exists.")
            return True

        # Create a new user since the email doesn't exist
        new_user = User(
            email=email,
            org_id=org_id,
        )
        # get role
        role = Role.query.filter_by(name="user").first()
        db.session.add(new_user)
        new_user.roles.append(role)

        # Commit the transaction
        db.session.commit()

        return True

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error during user creation: {e}")
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
    try:
        # check if the organisation exists
        org = Organisation.query.filter_by(name=organisation).first()
        if not org:
            # create the organisation
            try:
                org = Organisation(name=organisation)
                db.session.add(org)
                db.session.commit()
                created_new_org = True

            except Exception as e:
                created_new_org = False
                db.session.rollback()
                logging.error(e)
                raise e
        else:
            created_new_org = False

        # insert the user
        try:
            user = User(email=email, organisation=org)
            user.roles.append(Role.query.filter_by(name="user").first())
            db.session.add(user)
            db.session.commit()
            user_created_success = True
        except Exception as e:
            user_created_success = False
            db.session.rollback()
            logging.error(e)
            raise e

        # if created = True, this is the first user of the org so make them an org_admin by
        # inserting a record in the user_roles table
        if user_created_success and created_new_org:
            # get the role_id of the org_admin role
            role = Role.query.filter_by(name="org_admin").first()
            if not role:
                raise ValueError("Role 'org_admin' not found in the database.")
            role_id = role.id

            user_role = UserRole(user_id=user.id, role_id=role_id)
            db.session.add(user_role)
            db.session.commit()

        return True, "Registration successful!", user.id, org.id

    except Exception as e:
        logging.error("An error occurred: %s", e)
        db.session.rollback()
        return False, f"An error occurred: {e}", -1


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


def add_new_plan_user(user_id: int, plan_id: int):
    """
    Add a new plan for a user and update existing plans.

    Args:
        user_id (int): The ID of the user to whom the plan will be assigned.
        plan_id (int): The ID of the plan to be assigned to the user.

    Returns
    -------
        bool: True if the operation was successful, False otherwise.

    Raises
    ------
        Exception: If there is an error during the database query.
    """
    try:
        # Calculate the start and end dates for the new plan
        start_date = datetime.now().date()

        # Set is_active to FALSE for existing plans for the same user
        update_existing_plans_query = """
        UPDATE user_plans
        SET is_active = FALSE
        WHERE user_id = %s AND is_active = TRUE;
        """
        db.session.execute(update_existing_plans_query, (user_id,))

        # Insert the new plan for the user
        insert_new_plan_query = """
        INSERT INTO user_plans (user_id, plan_id, start_date)
        VALUES (%s, %s, %s);
        """
        db.session.execute(insert_new_plan_query, (user_id, plan_id, start_date))

        db.session.commit()
        return True
    except Exception as e:
        logging.error(f"Error adding new plan for user {user_id}: {e}")
        db.session.rollback()
        raise e


def get_user_current_plan(user_id: int):
    """
    Retrieve the current plan for a user or assign the 'free' plan if none exists.

    Args:
        user_id (int): The ID of the user.

    Returns
    -------
        str: The current plan name. Returns 'free' if assigned or False if an error occurs.
    """
    try:
        # SQL query to get the current plan for the user
        query = """
            SELECT
                p.plan_name AS plan_name
            FROM
                user_plans up
            JOIN
                plans p ON up.plan_id = p.plan_id
            WHERE
                up.user_id = %s
                AND up.is_active = TRUE
                AND CURDATE() BETWEEN up.start_date AND up.end_date
            LIMIT 1;
        """

        # Execute the query with the provided user_id
        result = db.session.execute(query, (user_id,)).fetchone()

        if result:
            return result[0]  # Return the current plan_name
        else:
            # No active plan, assign the 'free' plan
            # Get the free plan's plan_id from the plans table
            query_get_free_plan = """
                SELECT plan_id
                FROM plans
                WHERE plan_name = 'free'
                LIMIT 1;
            """
            free_plan_result = db.session.execute(query_get_free_plan).fetchone()

            if free_plan_result:
                free_plan_id = free_plan_result[0]
                add_new_plan_user(user_id=user_id, plan_id=free_plan_id)
                return "free"  # Return 'free' as the assigned plan

    except Exception as e:
        logging.error(f"Error get_user_current_plan for userid {user_id}: {e}")
        return False


def create_user(email, full_name=None, org_name=None, roles=None):
    """Create a user."""
    user = User(email=email, full_name=full_name)
    if org_name:
        org = Organisation.query.filter_by(name=org_name).first()
        if not org:
            org = Organisation(name=org_name)
            db.session.add(org)
        user.organisation = org

    if roles:
        for role_name in roles:
            role = Role.query.filter_by(name=role_name).first()
            if role:
                user.roles.append(role)

    db.session.add(user)
    db.session.commit()

    # Create an empty profile for the user
    profile = Profile(user_id=user.id)
    db.session.add(profile)
    db.session.commit()

    return user


def get_user_profile(user_id):
    """Get a user's profile."""
    return Profile.query.filter_by(user_id=user_id).first()


def update_user_profile(user_id, bio=None, location=None, birth_date=None, avatar_url=None):
    """Update a user's profile."""
    profile = Profile.query.filter_by(user_id=user_id).first()
    if not profile:
        profile = Profile(user_id=user_id)
        db.session.add(profile)

    if bio is not None:
        profile.bio = bio
    if location is not None:
        profile.location = location
    if birth_date is not None:
        profile.birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()
    if avatar_url is not None:
        profile.avatar_url = avatar_url

    db.session.commit()
    return profile


def get_user_roles(user_id):
    """Get a user's roles."""
    user = User.query.get(user_id)
    return [role.name for role in user.roles] if user else []


def add_user_role(user_id, role_name):
    """Add a role to a user."""
    user = User.query.get(user_id)
    role = Role.query.filter_by(name=role_name).first()
    if user and role:
        user.roles.append(role)
        db.session.commit()
        return True
    return False


def remove_user_role(user_id, role_name):
    """Remove a role from a user."""
    user = User.query.get(user_id)
    role = Role.query.filter_by(name=role_name).first()
    if user and role and role in user.roles:
        user.roles.remove(role)
        db.session.commit()
        return True
    return False


# def create_api_token(user_id, token_name, expires_in_days=30):
#     """Create an API token for a user."""
#     user = User.query.get(user_id)
#     if user:
#         token = APIToken(user=user, name=token_name, expires_in_days=expires_in_days)
#         db.session.add(token)
#         db.session.commit()
#         return token
#     return None


# def get_user_api_tokens(user_id):
#     """Get a user's API tokens."""
#     return APIToken.query.filter_by(user_id=user_id).all()


# def revoke_api_token(token_id, user_id):
#     """Revoke an API token for a user."""
#     token = APIToken.query.filter_by(id=token_id, user_id=user_id).first()
#     if token:
#         db.session.delete(token)
#         db.session.commit()
#         return True
#     return False


# def validate_api_token(token):
#     """Validate an API token."""
#     api_token = APIToken.query.filter_by(token=token).first()
#     if api_token and api_token.is_valid():
#         api_token.last_used_at = datetime.utcnow()
#         db.session.commit()
#         return api_token.user
#     return None
