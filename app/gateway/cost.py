from decimal import Decimal

from app.llm.gateway_contract import Usage

from .prices import PRICES

TOKENS_PER_PRICE_UNIT = Decimal(1_000_000)


def cost_usd(model: str, usage: Usage) -> Decimal | None:
    """What one call cost, or None for a model the price list doesn't know."""
    # shortcut: prices the whole call at the answering model's rates; a refusal fallback bills the declined part
    # at the first model's rates. Fine while fallbacks are rare; read usage.iterations if they become common.
    price = PRICES.get(model)
    if price is None:
        return None
    # input_tokens counts the cached parts too; each part has its own rate.
    uncached = usage.input_tokens - usage.cache_read_input_tokens - usage.cache_creation_input_tokens
    return (
        uncached * price.input
        + usage.cache_creation_input_tokens * price.cache_write
        + usage.cache_read_input_tokens * price.cache_read
        + usage.output_tokens * price.output
    ) / TOKENS_PER_PRICE_UNIT
