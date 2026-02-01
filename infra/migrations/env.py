"""
Alembic environment configuration.

This file is executed when you run Alembic commands (e.g., `alembic upgrade head`).

For the MVP, we keep it simple:
- we read DATABASE_URL from environment (preferred)
- otherwise we fall back to alembic.ini sqlalchemy.url

We are not using SQLAlchemy ORM models yet, so we do not provide `target_metadata`.
Migrations are written as explicit `op.create_table(...)` operations.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config object (reads alembic.ini)
config = context.config

# Configure Python logging using the config file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No ORM metadata yet (explicit migrations)
target_metadata = None


def _get_database_url() -> str:
    """Read DATABASE_URL env var, with fallback to alembic.ini setting."""

    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without connecting)."""

    url = _get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connects to DB and applies changes)."""

    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
