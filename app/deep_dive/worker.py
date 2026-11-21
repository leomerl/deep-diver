"""Deep dive worker: python -m app.deep_dive.worker"""
import logging
import os
import signal
import socket
import threading
from functools import partial
from pathlib import Path

from sqlmodel import Session

from app.auth import git_env
from app.config import DATABASE_URL, DEEP_DIVE_BUCKET, JOB_LEASE_S, JOB_MAX_DELIVERIES, engine, rds, s3
from app.deep_dive.generate_deep_dive import generate_deep_dive
from app.deep_dive.graph import forget_thread, postgres_checkpointer
from app.deep_dive.make_write import make_write
from app.deep_dive.store_html import store_html
from app.deep_dive.streams import DEEP_DIVE_DEAD_STREAM, DEEP_DIVE_GROUP, DEEP_DIVE_STREAM, PAYLOAD_FIELD
from app.git import list_files, sparse_clone
from app.models import DeepDiveCreate
from app.queue import WorkLoopSettings, ensure_group, work_loop
from app.storage import ensure_bucket

CLONE_TIMEOUT_S = 300
GIT_TIMEOUT_S = 30  # local commands on an existing checkout
READ_BLOCK_MS = 5000

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    consumer = f"{socket.gethostname()}-{os.getpid()}"  # unique per process, so pending jobs show who took them
    ls = partial(list_files, timeout_s=GIT_TIMEOUT_S)
    checkpointer = postgres_checkpointer(DATABASE_URL)  # creates LangGraph's tables on first start
    write = make_write(checkpointer)
    forget = partial(forget_thread, checkpointer)
    store = partial(store_html, s3, DEEP_DIVE_BUCKET)

    def handle(fields: dict[str, str]) -> None:
        job = DeepDiveCreate.model_validate_json(fields[PAYLOAD_FIELD])
        with Session(engine) as session:

            def clone(url: str, sha: str, paths: list[str], dest: Path, added_by: int | None) -> None:
                sparse_clone(url, sha, paths, dest, CLONE_TIMEOUT_S, env=git_env(session, url, added_by))

            generate_deep_dive(session, job, clone, ls, write, store, forget)
        logger.info("deep dive done for %s", job.target_key)

    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())  # finish the current job, then exit
    settings = WorkLoopSettings(
        stream=DEEP_DIVE_STREAM,
        group=DEEP_DIVE_GROUP,
        dlq_stream=DEEP_DIVE_DEAD_STREAM,
        lease_s=JOB_LEASE_S,
        max_deliveries=JOB_MAX_DELIVERIES,
        block_ms=READ_BLOCK_MS,
    )
    ensure_bucket(s3, DEEP_DIVE_BUCKET)
    ensure_group(rds, DEEP_DIVE_STREAM, DEEP_DIVE_GROUP)
    logger.info("worker %s reading %s", consumer, DEEP_DIVE_STREAM)
    work_loop(rds, settings, consumer, handle, stop)
    logger.info("worker %s stopped", consumer)


if __name__ == "__main__":
    main()
