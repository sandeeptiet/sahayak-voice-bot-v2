from alembic import context
from sqlalchemy import pool
from sahayak.api.config import Settings

config = context.config


def run(connection):
    context.configure(connection=connection, target_metadata=None, version_table_schema="public")
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("This migration verifies the existing schema and requires a database connection")
provided = config.attributes.get("connection")
if provided is not None:
    run(provided)
else:
    engine = Settings().engine()
    with engine.connect() as connection:
        run(connection)
    engine.dispose()
