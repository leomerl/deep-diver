import logging

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.llm.gateway_contract import Caller, Usage
from app.models import LlmCall

from .cost import cost_usd

logger = logging.getLogger(__name__)


def record_call(engine: Engine, model: str, usage: Usage, caller: Caller | None) -> None:
    """Store one paid call. Never raises: the call is already paid, and failing the request would make the
    agent retry it and pay again. A lost row is logged with every field, so it can be recovered by hand."""
    row = LlmCall(
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_input_tokens,
        cache_write_tokens=usage.cache_creation_input_tokens,
        cost_usd=cost_usd(model, usage),
        label=caller.label if caller else None,
        run_id=caller.run_id if caller else None,
    )
    if row.cost_usd is None:
        logger.warning("no price for model %s; usage stored without a cost", model)
    try:
        with Session(engine) as session:
            session.add(row)
            session.commit()
    except SQLAlchemyError:
        logger.exception("usage row lost: %s", row.model_dump_json(exclude={"id"}))
