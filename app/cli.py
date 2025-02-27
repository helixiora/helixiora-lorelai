"""Define the CLI commands for the app."""

import os
import re

import click
from flask.cli import with_appcontext
from sqlalchemy import text

from app.database import db
from app.models.datasource import Datasource
from app.models.plan import Plan
from app.models.role import Role


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Clear existing data and create new tables."""
    # Check if database already exists by checking if alembic_version table exists and has data
    try:
        result = db.session.execute(text("SHOW TABLES LIKE 'alembic_version'"))
        if result.fetchone():
            # Check if version is set
            version_result = db.session.execute(text("SELECT version_num FROM alembic_version"))
            if version_result.fetchone():
                click.echo("Database already initialized. Skipping initialization.")
                return
    except Exception:
        # If there's an error checking the table, continue with initialization
        pass

    try:
        db.create_all()
        click.echo("Created database tables.")
    except Exception as e:
        click.echo(f"Error creating tables: {e}")

    try:
        # Check if alembic_version table exists
        result = db.session.execute(text("SHOW TABLES LIKE 'alembic_version'"))
        if not result.fetchone():
            db.session.execute(
                text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
            )
            click.echo("Created alembic_version table.")
        else:
            click.echo("Alembic version table already exists.")

        # Find the latest migration version from the migrations directory
        versions_dir = os.path.join("migrations", "versions")
        latest_version = "00000"  # Default version if no files found

        if os.path.exists(versions_dir):
            for filename in os.listdir(versions_dir):
                match = re.match(r"^(\d+).*\.py$", filename)
                if match:
                    version = match.group(1)
                    if version > latest_version:
                        latest_version = version

        # Check if a version is already set
        version_result = db.session.execute(text("SELECT version_num FROM alembic_version"))
        existing_version = version_result.fetchone()

        if not existing_version:
            # Insert the latest version number
            db.session.execute(
                text(f"INSERT INTO alembic_version (version_num) VALUES ('{latest_version}')")
            )
            click.echo(f"Set alembic_version to '{latest_version}'")
        else:
            click.echo(f"Alembic version already set to '{existing_version[0]}'")

        db.session.commit()
    except Exception as e:
        click.echo(f"Error handling alembic_version table: {e}")
        db.session.rollback()

    click.echo("Initialized the database.")


@click.command("seed-db")
@with_appcontext
def seed_db_command():
    """Seed the database with initial data."""
    click.echo("Seeding the database...")

    click.echo("Creating datasources...")
    # Add datasources if they don't exist
    datasources = [{"name": "Slack", "type": "oauth"}, {"name": "Google Drive", "type": "oauth"}]
    for ds in datasources:
        if not Datasource.query.filter_by(datasource_name=ds["name"]).first():
            datasource = Datasource(datasource_name=ds["name"], datasource_type=ds["type"])
            db.session.add(datasource)
            click.echo(f"Added datasource: {ds['name']}")
        else:
            click.echo(f"Skipped existing datasource: {ds['name']}")
    db.session.commit()

    click.echo("Creating plans...")
    # Add plans if they don't exist
    plans = [
        {"name": "Free", "price": 0, "duration": 30, "limit": 1000},
        {"name": "Pro", "price": 10, "duration": 30, "limit": 10000},
    ]
    for p in plans:
        if not Plan.query.filter_by(plan_name=p["name"]).first():
            plan = Plan(
                plan_name=p["name"],
                price=p["price"],
                duration_months=p["duration"],
                message_limit_daily=p["limit"],
            )
            db.session.add(plan)
            click.echo(f"Added plan: {p['name']}")
        else:
            click.echo(f"Skipped existing plan: {p['name']}")
    db.session.commit()

    click.echo("Creating roles...")
    # Add roles if they don't exist
    roles = ["super_admin", "org_admin", "user"]
    for role_name in roles:
        if not Role.query.filter_by(name=role_name).first():
            role = Role(name=role_name)
            db.session.add(role)
            click.echo(f"Added role: {role_name}")
        else:
            click.echo(f"Skipped existing role: {role_name}")
    db.session.commit()

    click.echo("Seeded the database with initial data.")
