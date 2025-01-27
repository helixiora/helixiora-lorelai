"""Define the CLI commands for the app."""

import click
from flask.cli import with_appcontext
from app.models.datasource import Datasource
from app.models.plan import Plan
from app.models.role import Role
from app.database import db

from sqlalchemy import text


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Clear existing data and create new tables."""
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
    roles = ["org_admin", "super_admin", "user"]
    for role_name in roles:
        if not Role.query.filter_by(name=role_name).first():
            role = Role(name=role_name)
            db.session.add(role)
            click.echo(f"Added role: {role_name}")
        else:
            click.echo(f"Skipped existing role: {role_name}")
    db.session.commit()

    click.echo("Seeded the database.")
