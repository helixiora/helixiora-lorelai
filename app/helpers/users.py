"""User related helper functions."""

import logging
from datetime import date, datetime
from functools import wraps

from dateutil.relativedelta import relativedelta
from flask import redirect, session, url_for
from sqlalchemy.exc import SQLAlchemyError

from app.database import db
from app.models.organisation import Organisation
from app.models.plan import Plan, UserPlan
from app.models.profile import Profile
from app.models.role import Role, UserRole
from app.models.user import User


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
        return True, "Registration successful!", user

    except Exception as e:
        logging.error("An error occurred: %s", e)
        db.session.rollback()
        raise e


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


def assign_free_plan_if_no_active(user_id: int):
    """
    Assign a free one-month plan to a user if no active plan is currently assigned.
    Expire any existing plans that have passed their end date.

    This function performs the following steps:
    1. Checks if the user has any active plans.
    2. If a plan is expired (its end date is past the current date), it sets `is_active` to `False`.
    3. If no active plan is found, assigns a free plan with a one-month duration.
    4. Commits all changes to the database or rolls back in case of an error.

    Args:
        user_id (int): The unique identifier of the user.

    Returns
    -------
        bool: `True` if the operation was successful, `False` otherwise.

    Raises
    ------
        Exception: If there is an error during the database operations, it logs the error
        and rolls back the transaction.
    """  # noqa: D205
    try:
        # Query user's active plans
        user_plans = UserPlan.query.filter_by(user_id=user_id).all()
        has_active_plan = False
        for plan in user_plans:
            # Check if the plan is expired
            if plan.end_date and plan.end_date < datetime.utcnow().date():
                plan.is_active = False
                db.session.add(plan)
            elif plan.is_active:
                has_active_plan = True

        # Assign free plan if no active plan found
        if not has_active_plan:
            free_plan = Plan.query.filter_by(plan_name="Free").first()
            if free_plan:
                start_date = datetime.utcnow()
                end_date = start_date + relativedelta(months=free_plan.duration_months)
                new_user_plan = UserPlan(
                    user_id=user_id,
                    plan_id=free_plan.plan_id,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True,
                )
                db.session.add(new_user_plan)

        # Commit changes
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in assigning free plan: {e}", exc_info=True)
        raise e


def create_user(
    email: str,
    full_name: str | None = None,
    org_name: str | None = None,
    roles: list[str] | None = None,
) -> User:
    """Create a user."""
    session = db.session
    try:
        user = User(
            email=email,
            full_name=full_name,
            created_at=datetime.utcnow(),  # Set the created_at field
        )
        if org_name:
            org = Organisation.query.filter_by(name=org_name).first()
            if not org:
                org = Organisation(name=org_name)
                session.add(org)
            user.organisation = org

        # If no roles specified, assign default 'user' role
        if not roles:
            roles = ["user"]

        for role_name in roles:
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                # Create the role if it doesn't exist
                role = Role(name=role_name)
                session.add(role)
            user.roles.append(role)

        session.add(user)
        session.commit()

        # Create an empty profile for the user
        profile = Profile(user_id=user.id)
        session.add(profile)
        session.commit()

        return user
    except SQLAlchemyError as e:
        session.rollback()
        logging.exception("Failed to create user")
        raise e


def is_valid_past_date(date_str: str, date_format: str = "%Y-%m-%d") -> bool:
    """Check if a date string is a valid past date."""
    try:
        # Parse the date string into a datetime object
        date = datetime.strptime(date_str, date_format)

        # Check if the date is in the past
        return date < datetime.now()
    except ValueError:
        # If parsing fails, the date is not valid
        return False


def update_user_profile(
    user_id: int,
    bio: str | None = None,
    location: str | None = None,
    birth_date: date | None = None,
    avatar_url: str | None = None,
) -> Profile:
    """Update a user's profile."""
    session = db.session
    try:
        profile = Profile.query.filter_by(user_id=user_id).first()
        if not profile:
            profile = Profile(user_id=user_id)
            session.add(profile)

        if bio is not None:
            profile.bio = bio
        if location is not None:
            profile.location = location
        if birth_date is not None:
            profile.birth_date = birth_date
        if avatar_url is not None:
            profile.avatar_url = avatar_url

        session.commit()
        return profile
    except SQLAlchemyError as e:
        session.rollback()
        logging.exception("Failed to update user profile")
        raise e


def get_user_roles(user_id: int) -> list[str]:
    """Get a user's roles."""
    user = User.query.get(user_id)
    return [role.name for role in user.roles] if user else []


def add_user_role(user_id: int, role_name: str) -> bool:
    """Add a role to a user."""
    user = User.query.get(user_id)
    role = Role.query.filter_by(name=role_name).first()
    if user and role:
        user.roles.append(role)
        db.session.commit()
        return True
    return False


def remove_user_role(user_id: int, role_name: str) -> bool:
    """Remove a role from a user."""
    user = User.query.get(user_id)
    role = Role.query.filter_by(name=role_name).first()
    if user and role and role in user.roles:
        user.roles.remove(role)
        db.session.commit()
        return True
    return False


def assign_plan_to_user(user_id: int, plan_name: str) -> bool:
    """
    Assign a specific plan to a user.

    This function performs the following steps:
    1. Deactivates any existing active plans for the user
    2. Finds the requested plan by name
    3. Creates a new active plan for the user with duration from plan settings
    4. Commits all changes to the database

    Args:
        user_id (int): The unique identifier of the user.
        plan_name (str): The name of the plan to assign.

    Returns
    -------
        bool: True if plan was assigned successfully, False if plan not found.

    Raises
    ------
        Exception: If there is an error during the database operations.
    """
    try:
        # Deactivate existing active plans
        UserPlan.query.filter_by(user_id=user_id, is_active=True).update({"is_active": False})

        # Find the requested plan
        plan = Plan.query.filter_by(plan_name=plan_name).first()
        if not plan:
            logging.error(f"Plan not found: {plan_name}")
            return False

        # assign  new plan for user
        start_date = datetime.utcnow()
        end_date = start_date + relativedelta(months=plan.duration_months)

        new_user_plan = UserPlan(
            user_id=user_id,
            plan_id=plan.plan_id,
            start_date=start_date,
            end_date=end_date,
            is_active=True,
        )

        db.session.add(new_user_plan)
        db.session.commit()

        logging.info(f"Successfully assigned {plan_name} plan to user {user_id}")
        return True

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error assigning plan to user: {e}", exc_info=True)
        raise e
