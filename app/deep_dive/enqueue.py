from app.config import rds
from app.models import DeepDiveCreate
from app.queue import enqueue_once

from .streams import DEEP_DIVE_STREAM, DEDUP_PREFIX, PAYLOAD_FIELD


def enqueue_deep_dive_job(job: DeepDiveCreate) -> bool:
    """Queue a deep dive for the node or repo root. Returns False if it was already queued."""
    return enqueue_once(
        rds, f"{DEDUP_PREFIX}{job.target_key}", DEEP_DIVE_STREAM, {PAYLOAD_FIELD: job.model_dump_json()}
    )
