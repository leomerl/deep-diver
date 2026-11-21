"""Bring stored deep dive pages up to the current template: python -m app.deep_dive.restyle_stored"""
import logging

from sqlmodel import Session, select

from app.config import DEEP_DIVE_BUCKET, engine, s3
from app.models import DeepDive

from .read_html import read_html
from .restyle_html import restyle_html
from .store_html import store_html

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with Session(engine) as session:
        for deep_dive in session.exec(select(DeepDive)).all():
            # Upload before the row points at it. The old object stays in the bucket, so the log is the undo list.
            key = store_html(s3, DEEP_DIVE_BUCKET, restyle_html(read_html(s3, DEEP_DIVE_BUCKET, deep_dive.object_key)))
            if key == deep_dive.object_key:
                continue
            logger.info("deep dive %s: %s -> %s", deep_dive.id, deep_dive.object_key, key)
            deep_dive.object_key = key
            session.add(deep_dive)
            session.commit()  # per row: a page that fails to convert stops the run without undoing the earlier ones


if __name__ == "__main__":
    main()
