import uuid
from datetime import UTC, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class LlmCallBase(SQLModel):
    """One paid model call through the gateway: what it cost and which agent run asked for it."""

    model: str = Field(max_length=64)  # the model that answered, which a refusal fallback can change
    input_tokens: int  # every input token read, cached or not (as in the contract's Usage)
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    # Priced when the call is recorded, so a later price change doesn't rewrite what was paid.
    # NULL: the model has no entry in the price list; the tokens above still allow pricing it later.
    cost_usd: Decimal | None = Field(default=None, max_digits=12, decimal_places=6)
    label: str | None = Field(default=None, sa_type=sa.Text)  # the agent's label; NULL for calls without a caller
    # One per agent run: the same label under two run ids means that agent ran (and was paid for) twice.
    run_id: uuid.UUID | None = None


class LlmCall(LlmCallBase, table=True):
    __tablename__ = "llm_calls"

    id: int | None = Field(default=None, primary_key=True)
    # index serves the usage report's per-day grouping
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=sa.DateTime(timezone=True), index=True
    )
