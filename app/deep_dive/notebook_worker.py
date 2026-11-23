"""Notebook worker: python -m app.deep_dive.notebook_worker"""
import logging
import os
import signal
import socket
import threading
from functools import partial
from pathlib import Path

from sqlmodel import Session

from app.auth import git_env
from app.config import DEEP_DIVE_BUCKET, JOB_LEASE_S, JOB_MAX_DELIVERIES, engine, rds, s3
from app.deep_dive.generate_notebook import generate_notebook
from app.deep_dive.make_notebook import make_notebook
from app.deep_dive.read_html import read_html
from app.deep_dive.store_notebook import store_notebook
from app.deep_dive.streams import NOTEBOOK_DEAD_STREAM, NOTEBOOK_GROUP, NOTEBOOK_STREAM, PAYLOAD_FIELD
from app.git import list_files, sparse_clone
from app.jobs import record_job_event
from app.models import NotebookJob
from app.queue import ReportStep, WorkLoopSettings, ensure_group, work_loop
from app.storage import ensure_bucket

CLONE_TIMEOUT_S = 300
GIT_TIMEOUT_S = 30  # local commands on an existing checkout
READ_BLOCK_MS = 5000

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    consumer = f"{socket.gethostname()}-{os.getpid()}"  # unique per process, so pending jobs show who took them
    ls = partial(list_files, timeout_s=GIT_TIMEOUT_S)
    write = make_notebook()
    read_page = partial(read_html, s3, DEEP_DIVE_BUCKET)
    store = partial(store_notebook, s3, DEEP_DIVE_BUCKET)

    def handle(fields: dict[str, str], report_step: ReportStep) -> None:  # one step: nothing to report
        job = NotebookJob.model_validate_json(fields[PAYLOAD_FIELD])
        with Session(engine) as session:

            def clone(url: str, sha: str, paths: list[str], dest: Path, added_by: int | None) -> None:
                sparse_clone(url, sha, paths, dest, CLONE_TIMEOUT_S, env=git_env(session, url, added_by))

            generate_notebook(session, job, clone, ls, read_page, write, store)
        logger.info("notebook done for deep dive %s", job.deep_dive_id)

    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())  # finish the current job, then exit
    settings = WorkLoopSettings(
        stream=NOTEBOOK_STREAM,
        group=NOTEBOOK_GROUP,
        dlq_stream=NOTEBOOK_DEAD_STREAM,
        lease_s=JOB_LEASE_S,
        max_deliveries=JOB_MAX_DELIVERIES,
        block_ms=READ_BLOCK_MS,
    )
    ensure_bucket(s3, DEEP_DIVE_BUCKET)
    ensure_group(rds, NOTEBOOK_STREAM, NOTEBOOK_GROUP)
    logger.info("worker %s reading %s", consumer, NOTEBOOK_STREAM)
    observe = partial(record_job_event, engine, NOTEBOOK_STREAM, consumer)
    work_loop(rds, settings, consumer, handle, stop, observe)
    logger.info("worker %s stopped", consumer)


if __name__ == "__main__":
    main()
