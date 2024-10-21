"""Database related helper functions."""

import logging
from datetime import date

import mysql.connector
import redis
from sqlalchemy.exc import SQLAlchemyError

from app.models import (
    db,
    User,
    Role,
    Organisation,
    Profile,
)
from flask import current_app


def check_mysql() -> tuple[bool, str]:
    """Check if the MySQL database is up and running.

    Returns
    -------
    tuple
        A tuple with a boolean indicating success and a string with the message.
    """
    try:
        db.session.execute("SELECT 1")
        return True, "MySQL is up and running."
    except mysql.connector.Error as e:
        logging.exception("MySQL check failed")
        return False, str(e)


def check_redis() -> tuple[bool, str]:
    """Check if the Redis server is up and running."""
    try:
        logging.debug(f"Connecting to Redis: {current_app.config['REDIS_URL']}")
        r = redis.Redis.from_url(current_app.config["REDIS_URL"])
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


def create_user(
    email: str,
    full_name: str | None = None,
    org_name: str | None = None,
    roles: list[str] | None = None,
) -> User:
    """Create a user."""
    session = db.session
    try:
        user = User(email=email, full_name=full_name)
        if org_name:
            org = Organisation.query.filter_by(name=org_name).first()
            if not org:
                org = Organisation(name=org_name)
                session.add(org)
            user.organisation = org

        if roles:
            for role_name in roles:
                role = Role.query.filter_by(name=role_name).first()
                if role:
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


def get_user_by_id(user_id: int) -> User | None:
    """Get a user by their ID."""
    return User.query.get(user_id)


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


# Additional helper functions can be similarly refactored to use ORM
