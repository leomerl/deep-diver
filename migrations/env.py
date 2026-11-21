from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    # Default True silences every logger created before this runs: in tests, the app's own (the suite migrates first).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Migrations are derived from the SQLModel tables in app/models.py.
from sqlmodel import SQLModel

import app.models  # noqa: F401  registers the tables on SQLModel.metadata
from app.config import DATABASE_URL

config.set_main_option("sqlalchemy.url", DATABASE_URL)
target_metadata = SQLModel.metadata

# LangGraph's checkpointer owns and migrates these tables itself (PostgresSaver.setup()); autogenerate must not
# see them as unknown and emit drop_table for them.
CHECKPOINTER_TABLES = frozenset({"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"})


def include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    if type_ == "table":
        return name not in CHECKPOINTER_TABLES
    if type_ == "index":
        return parent_names.get("table_name") not in CHECKPOINTER_TABLES
    return True

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_name=include_name,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, include_name=include_name
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
