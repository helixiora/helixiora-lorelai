"""Define the CLI commands for the app."""

import click
from flask.cli import with_appcontext
from app.models.datasource import Datasource
from app.database import db


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Clear existing data and create new tables."""
    db.create_all()
    click.echo("Initialized the database.")


# Optional: Add some seed data
@click.command("seed-db")
@with_appcontext
def seed_db_command():
    """Seed the database with initial data."""
    # Add your seed data here, for example:
    Datasource.create(name="Slack", type="oauth")
    Datasource.create(name="Google Drive", type="oauth")
    Datasource.create(name="", type="oauth")

    # db.session.add(user)
    # db.session.commit()
    click.echo("Seeded the database.")
