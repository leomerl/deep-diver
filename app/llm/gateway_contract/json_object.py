from pydantic import JsonValue

# JsonValue, not Any: still "any JSON", but Pydantic checks that it really is JSON.
JsonObject = dict[str, JsonValue]
