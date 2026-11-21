import json

from app.agent_sdk.strict_schema import strict_json_schema
from app.deep_dive.answer import DeepDiveAnswer


def test_discriminator_is_stripped_at_every_depth() -> None:
    schema = {
        "oneOf": [{"$ref": "#/$defs/A"}],
        "discriminator": {"propertyName": "kind"},
        "$defs": {"A": {"properties": {"inner": {"anyOf": [], "discriminator": {"propertyName": "k"}}}}},
    }
    assert strict_json_schema(schema) == {
        "oneOf": [{"$ref": "#/$defs/A"}],
        "$defs": {"A": {"properties": {"inner": {"anyOf": []}}}},
    }


def test_deep_dive_answer_schema_becomes_strict_json_schema() -> None:
    # The live failure: the Claude Code binary rejected this schema with 'unknown keyword: "discriminator"'.
    raw = DeepDiveAnswer.model_json_schema()
    assert "discriminator" in json.dumps(raw)
    strict = strict_json_schema(raw)
    assert "discriminator" not in json.dumps(strict)
    assert strict["properties"].keys() == raw["properties"].keys()
