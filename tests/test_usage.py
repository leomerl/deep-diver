import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlmodel import Session, create_engine, select

from app.config import engine
from app.gateway.cost import cost_usd
from app.gateway.record_call import record_call
from app.llm.gateway_contract import Caller, Usage
from app.models import LlmCall
from app.usage import spend_per_day, spend_per_label

# 1,000 uncached input, 2,000 cache writes, 10,000 cache reads, 500 output.
USAGE = Usage(input_tokens=13_000, output_tokens=500, cache_read_input_tokens=10_000, cache_creation_input_tokens=2_000)
OPUS_COST = Decimal("0.026")  # (1,000 x 4 + 2,000 x 5 + 10,000 x 0.20 + 500 x 20) / 1M


def test_each_token_kind_is_priced_at_its_own_rate() -> None:
    assert cost_usd("claude-opus-5-5", USAGE) == OPUS_COST


def test_an_unlisted_model_has_no_cost() -> None:
    assert cost_usd("claude-haiku-5-5", USAGE) is None


def test_two_runs_of_one_label_show_as_paid_twice(session: Session) -> None:
    for run_id in (uuid.uuid4(), uuid.uuid4()):
        record_call(engine, "claude-opus-5-5", USAGE, Caller(label="r > Queue", run_id=run_id))
    record_call(engine, "claude-haiku-5-5", USAGE, None)
    since = datetime.now(UTC) - timedelta(days=1)

    assert spend_per_label(session, since) == [("r > Queue", 2, 2 * OPUS_COST, 2), ("(no caller)", 0, Decimal(0), 1)]
    [(_, day_cost, calls, unpriced)] = spend_per_day(session, since)
    assert (day_cost, calls, unpriced) == (2 * OPUS_COST, 3, 1)


def test_a_database_failure_is_logged_not_raised(session: Session, caplog: pytest.LogCaptureFixture) -> None:
    unreachable = create_engine("postgresql+psycopg://dd:dd@localhost:1/dd", connect_args={"connect_timeout": 1})

    with caplog.at_level(logging.ERROR):
        record_call(unreachable, "claude-opus-5-5", USAGE, None)  # must not raise: the call was already paid

    assert "usage row lost" in caplog.text and '"input_tokens":13000' in caplog.text
    assert session.exec(select(LlmCall)).all() == []
