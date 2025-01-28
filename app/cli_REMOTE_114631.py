"""Define the CLI commands for the app."""

import click
from flask.cli import with_appcontext
from app.models import db, Datasource


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
    slack_datasource = Datasource(datasource_name="Slack", datasource_type="oauth2")
    google_drive_datasource = Datasource(datasource_name="Google Drive", datasource_type="oauth2")

    db.session.add(slack_datasource)
    db.session.add(google_drive_datasource)
    db.session.commit()

    # db.session.add(user)
    # db.session.commit()
    click.echo("Seeded the database.")



