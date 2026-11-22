from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Price:
    """US dollars per million tokens."""

    input: Decimal
    output: Decimal
    cache_write: Decimal  # 5-minute TTL, the only one the gateway asks for
    cache_read: Decimal
