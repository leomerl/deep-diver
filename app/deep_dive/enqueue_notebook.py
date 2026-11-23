from app.config import rds
from app.models import NotebookJob
from app.queue import enqueue_once

from .streams import NOTEBOOK_DEDUP_PREFIX, NOTEBOOK_STREAM, PAYLOAD_FIELD


def enqueue_notebook_job(deep_dive_id: int) -> bool:
    """Queue the notebook for a saved page. Returns False if it was already queued."""
    job = NotebookJob(deep_dive_id=deep_dive_id)
    return enqueue_once(rds, f"{NOTEBOOK_DEDUP_PREFIX}{deep_dive_id}", NOTEBOOK_STREAM, {PAYLOAD_FIELD: job.model_dump_json()})
