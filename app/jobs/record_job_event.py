import logging

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.models import JobEvent
from app.queue import JobEventKind

MAX_DETAIL_CHARS = 4000  # an agent's error can quote a whole rejected answer

logger = logging.getLogger(__name__)


def record_job_event(
    engine: Engine, stream: str, consumer: str, entry_id: str, kind: JobEventKind, delivery: int, detail: str | None
) -> None:
    """Insert one event in its own transaction, apart from the job's: a failed job rolls its work back, and its
    `failed` event must survive that. An insert that fails is logged, not raised: history is not worth failing
    (and so retrying, and paying for) a job."""
    event = JobEvent(
        stream=stream, entry_id=entry_id, kind=kind, delivery=delivery, consumer=consumer,
        detail=None if detail is None else detail[:MAX_DETAIL_CHARS],
    )
    try:
        with Session(engine) as session:
            session.add(event)
            session.commit()
    except SQLAlchemyError:
        logger.warning("could not record %s for %s %s", kind, stream, entry_id, exc_info=True)
