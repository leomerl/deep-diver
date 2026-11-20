import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url


def postgres_checkpointer(database_url: str) -> PostgresSaver:
    """LangGraph's checkpointer on its own connection. `database_url` is the SQLAlchemy URL; psycopg wants the plain
    scheme. PostgresSaver needs autocommit and dict rows. `setup()` creates and migrates LangGraph's own tables:
    the one schema Alembic doesn't own, because the library owns its layout and migrates it itself."""
    dsn = make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)
    saver = PostgresSaver(psycopg.connect(dsn, autocommit=True, row_factory=dict_row))
    saver.setup()
    return saver
