"""Define the CLI commands for the app."""

import click
from flask.cli import with_appcontext
from app.models import db, Datasource, Plan, Role


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Clear existing data and create new tables."""
    db.create_all()

    # create the alembic version table
    db.session.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    db.session.commit()

    click.echo("Initialized the database.")


@click.command("seed-db")
@with_appcontext
def seed_db_command():
    """Seed the database with initial data."""
    click.echo("Seeding the database...")

    click.echo("Creating datasources...")
    # Add your seed data here, for example:
    datasource = Datasource.create(name="Slack", type="oauth")
    db.session.add(datasource)
    datasource = Datasource.create(name="Google Drive", type="oauth")
    db.session.add(datasource)
    db.session.commit()

    click.echo("Creating plans...")
    plan = Plan.create(name="Free", price=0, duration=30, message_limit_daily=1000)
    db.session.add(plan)
    plan = Plan.create(name="Pro", price=10, duration=30, message_limit_daily=10000)
    db.session.add(plan)
    db.session.commit()

    click.echo("Creating roles...")
    role = Role.create(name="org_admin", description="Admin role")
    db.session.add(role)
    role = Role.create(name="super_admin", description="Super admin role")
    db.session.add(role)
    role = Role.create(name="user", description="User role")
    db.session.add(role)
    db.session.commit()

    click.echo("Seeded the database.")
