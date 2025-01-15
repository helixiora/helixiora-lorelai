"""Alembic environment file."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from app.factory import create_app
from app.models import db
import logging

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get Flask app
flask_app = create_app()

# add your model's MetaData object here
target_metadata = db.metadata  # noqa: F405


def get_url():
    """Get the SQLAlchemy database URI."""
    logging.info(f"SQLALCHEMY_DATABASE_URI {flask_app.config['SQLALCHEMY_DATABASE_URI']}")
    return flask_app.config["SQLALCHEMY_DATABASE_URI"]


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    logging.info("Running migrations in offline mode")
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    logging.info("Running migrations in online mode")
    try:
        configuration = config.get_section(config.config_ini_section)
        if configuration is not None:
            configuration["sqlalchemy.url"] = get_url()

        connectable = engine_from_config(
            configuration or {},
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
                transaction_per_migration=True,
                include_comments=True,
                render_as_batch=True,
            )

            logging.info("Starting migration detection...")
            with context.begin_transaction():
                try:
                    context.run_migrations()
                except Exception as e:
                    logging.info(f"Error during migration detection: {str(e)}")
                    logging.exception("Migration detection failed")
                    raise
            logging.info("Migration detection completed")

    except Exception as e:
        logging.info(f"Error setting up migration environment: {str(e)}")
        logging.exception("Migration setup failed")
        raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
