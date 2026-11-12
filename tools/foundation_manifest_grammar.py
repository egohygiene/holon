"""Enforce the closed foundation-manifest grammar without runtime dependencies.

This is deliberately limited to the keywords used by Holon's own v1 schema.
It is not a general JSON Schema implementation: an unsupported keyword or
reference is a contract configuration error, never silently ignored.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas/foundation-manifest.v1.schema.json"
SUPPORTED_KEYWORDS = {
    "$schema", "$id", "$defs", "$ref", "title", "description", "type",
    "additionalProperties", "required", "properties", "const", "enum",
    "pattern", "minLength", "uniqueItems", "items",
}


def _check_schema(schema: Any, root: dict[str, Any]) -> None:
    if not isinstance(schema, dict) or set(schema) - SUPPORTED_KEYWORDS:
        raise ValueError("unsupported foundation-manifest schema keywords")
    if "type" in schema and schema["type"] not in {"object", "array", "string"}:
        raise ValueError("unsupported foundation-manifest schema type")
    if "$ref" in schema:
        reference = schema["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
            raise ValueError("unsupported foundation-manifest schema reference")
        name = reference.removeprefix("#/$defs/")
        if "/" in name or name not in root.get("$defs", {}):
            raise ValueError("unknown foundation-manifest schema reference")
    if "pattern" in schema:
        re.compile(schema["pattern"])
    for collection in ("$defs", "properties"):
        for child in schema.get(collection, {}).values():
            _check_schema(child, root)
    if "items" in schema:
        _check_schema(schema["items"], root)
    additional = schema.get("additionalProperties", True)
    if not isinstance(additional, bool):
        _check_schema(additional, root)


def _validate(value: Any, schema: dict[str, Any], root: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    if "$ref" in schema:
        name = schema["$ref"].removeprefix("#/$defs/")
        errors.extend(_validate(value, root["$defs"][name], root, path))
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} must be one of {', '.join(schema['enum'])}")

    expected = schema.get("type")
    matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
    }
    if expected is not None and not matches[expected]:
        article = "an" if expected in {"object", "array"} else "a"
        return errors + [f"{path} must be {article} {expected}"]

    if expected == "object":
        if any(not isinstance(key, str) for key in value):
            return errors + [f"{path} must use string property names"]
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key} is required")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key in sorted(value):
            if key in properties:
                errors.extend(_validate(value[key], properties[key], root, f"{path}.{key}"))
            elif additional is False:
                errors.append(f"{path}.{key} is not a supported field")
            elif isinstance(additional, dict):
                errors.extend(_validate(value[key], additional, root, f"{path}.{key}"))
    elif expected == "array":
        if schema.get("uniqueItems") and any(item in value[:index] for index, item in enumerate(value)):
            errors.append(f"{path} must not contain duplicates")
        for index, item in enumerate(value):
            if "items" in schema:
                errors.extend(_validate(item, schema["items"], root, f"{path}[{index}]"))
    elif expected == "string":
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path} must be a non-empty string")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path} does not match the supported grammar")
    return errors


def validate_manifest(value: Any) -> list[str]:
    """Validate the complete public v1 grammar before semantic resolution."""
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        _check_schema(schema, schema)
    except (OSError, ValueError, TypeError, AttributeError, re.error):
        return ["foundation-manifest schema is unavailable or unsupported"]
    return sorted(set(_validate(value, schema, schema, "manifest")))
