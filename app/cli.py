"""Define the CLI commands for the app."""

import click
from flask.cli import with_appcontext
from sqlalchemy import text

from app.models import Datasource, Plan, Role, db


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Clear existing data and create new tables."""
    db.create_all()

    # create the alembic version table
    db.session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
    db.session.commit()

    click.echo("Initialized the database.")


@click.command("seed-db")
@with_appcontext
def seed_db_command():
    """Seed the database with initial data."""
    click.echo("Seeding the database...")

    click.echo("Creating datasources...")
    # Add your seed data here, for example:
    datasource = Datasource(datasource_name="Slack", datasource_type="oauth")
    db.session.add(datasource)
    datasource = Datasource(datasource_name="Google Drive", datasource_type="oauth")
    db.session.add(datasource)
    db.session.commit()

    click.echo("Creating plans...")
    plan = Plan(plan_name="Free", price=0, duration_months=30, message_limit_daily=1000)
    db.session.add(plan)
    plan = Plan(plan_name="Pro", price=10, duration_months=30, message_limit_daily=10000)
    db.session.add(plan)
    db.session.commit()

    click.echo("Creating roles...")
    role = Role(
        name="org_admin",
    )
    db.session.add(role)
    role = Role(
        name="super_admin",
    )
    db.session.add(role)
    role = Role(
        name="user",
    )
    db.session.add(role)
    db.session.commit()

    click.echo("Seeded the database.")
