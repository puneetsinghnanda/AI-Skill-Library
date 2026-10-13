"""Alembic environment. Runs as the owner role (SDD-08 §9.4); online mode only."""

from __future__ import annotations

from sqlalchemy import create_engine, pool

from alembic import context
from app.config import get_settings

config = context.config


def run_migrations_online() -> None:
    url = config.attributes.get("url") or get_settings().database_url("owner")
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=None, transaction_per_migration=True
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline SQL generation is not supported; run `python -m app.entry migrate`.")
run_migrations_online()
