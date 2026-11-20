import os
from collections.abc import Iterator

# Must run before `app.config` is imported: tests get their own Redis DB and Postgres DB,
# so flushing and truncating them never touches dev data.
TEST_REDIS_URL = "redis://localhost:6379/15"
TEST_DB_NAME = "dd_test"
ADMIN_DB_URL = "postgresql://dd:dd@localhost:5432/dd"
os.environ["REDIS_URL"] = TEST_REDIS_URL
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ["DATABASE_URL"] = f"postgresql+psycopg://dd:dd@localhost:5432/{TEST_DB_NAME}"

import psycopg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.config import engine  # noqa: E402


@pytest.fixture(scope="session")
def migrated_db() -> None:
    # CREATE DATABASE can't run inside a transaction, hence autocommit.
    with psycopg.connect(ADMIN_DB_URL, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", [TEST_DB_NAME]).fetchone():
            conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    # migrations/env.py reads DATABASE_URL from app.config, which now points at dd_test
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
def session(migrated_db: None) -> Iterator[Session]:
    with Session(engine) as s:
        s.execute(text("TRUNCATE users, repos, nodes, edges RESTART IDENTITY CASCADE"))
        s.commit()
        yield s
