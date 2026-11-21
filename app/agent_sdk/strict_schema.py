from pydantic import JsonValue

from app.llm.gateway_contract import JsonObject

# Pydantic emits OpenAPI's `discriminator` for tagged unions. It is not JSON Schema, and the Claude Code binary
# validates `--json-schema` in strict mode, so a schema carrying it fails the run before the first turn.
NON_JSON_SCHEMA_KEYS = frozenset({"discriminator"})


def strict_json_schema(schema: JsonObject) -> JsonObject:
    return {key: _strip(value) for key, value in schema.items() if key not in NON_JSON_SCHEMA_KEYS}


def _strip(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {key: _strip(item) for key, item in value.items() if key not in NON_JSON_SCHEMA_KEYS}
    if isinstance(value, list):
        return [_strip(item) for item in value]
    return value
