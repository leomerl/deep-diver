from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.config import engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, closed when the response is sent."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
