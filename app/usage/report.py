"""Where the API money went: python -m app.usage.report [days]

Reads the gateway's llm_calls rows. Calls made through the Claude Code login (agent_sdk runtime) never reach the
gateway, so they don't appear here; they bill the subscription, not the API key.
"""
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.config import engine
from app.models import LlmCall

DEFAULT_DAYS = 30
NO_CALLER = "(no caller)"

type DayRow = tuple[date, Decimal, int, int]  # day, cost, calls, unpriced calls
type LabelRow = tuple[str, int, Decimal, int]  # label, agent runs, cost, calls


def spend_per_day(session: Session, since: datetime) -> list[DayRow]:
    day = func.date_trunc("day", col(LlmCall.created_at))
    # Served by the index on llm_calls.created_at.
    rows = session.exec(
        select(
            day,
            func.coalesce(func.sum(col(LlmCall.cost_usd)), 0),
            func.count(),
            func.count().filter(col(LlmCall.cost_usd).is_(None)),
        )
        .where(col(LlmCall.created_at) >= since)
        .group_by(day)
        .order_by(day)
    ).all()
    return [(d.date(), Decimal(cost), calls, unpriced) for d, cost, calls, unpriced in rows]


def spend_per_label(session: Session, since: datetime) -> list[LabelRow]:
    """Most expensive first. More than one run for a label means that agent was paid for more than once."""
    cost = func.coalesce(func.sum(col(LlmCall.cost_usd)), 0)
    rows = session.exec(
        select(col(LlmCall.label), func.count(func.distinct(col(LlmCall.run_id))), cost, func.count())
        .where(col(LlmCall.created_at) >= since)
        .group_by(col(LlmCall.label))
        .order_by(cost.desc())
    ).all()
    return [(label or NO_CALLER, runs, Decimal(total), calls) for label, runs, total, calls in rows]


def main() -> None:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DAYS
    since = datetime.now(UTC) - timedelta(days=days)
    with Session(engine) as session:
        per_day, per_label = spend_per_day(session, since), spend_per_label(session, since)
    print(f"Spend per day, last {days} days")
    for day, cost, calls, unpriced in per_day:
        print(f"  {day}  ${cost:>9.2f}  {calls:>6} calls" + (f"  ({unpriced} unpriced)" if unpriced else ""))
    print(f"  total  ${sum((row[1] for row in per_day), Decimal(0)):>9.2f}")
    print("\nSpend per agent label (runs > 1: paid more than once)")
    for label, runs, cost, calls in per_label:
        print(f"  ${cost:>9.2f}  {runs:>3} run{'s' if runs != 1 else ' '}  {calls:>5} calls  {label}")


if __name__ == "__main__":
    main()
