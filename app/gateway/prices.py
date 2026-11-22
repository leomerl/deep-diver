from decimal import Decimal

from .price import Price

# Anthropic first-party API rates, per million tokens. Update when Anthropic changes them; past rows keep what
# they were priced at. Claude Haiku 5.5 is left out on purpose: its rate changes above a 100K-token prompt, and
# a flat entry would misprice long agent turns. An unlisted model is recorded with tokens and no cost.
PRICES: dict[str, Price] = {
    "claude-opus-5-5": Price(input=Decimal("4"), output=Decimal("20"), cache_write=Decimal("5"), cache_read=Decimal("0.20")),
    "claude-sonnet-5-5": Price(input=Decimal("2"), output=Decimal("10"), cache_write=Decimal("2.50"), cache_read=Decimal("0.10")),
    "claude-fable-5-2": Price(input=Decimal("8"), output=Decimal("40"), cache_write=Decimal("10"), cache_read=Decimal("0.20")),
}
