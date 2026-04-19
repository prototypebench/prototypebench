"""Validate a tasks/instances.jsonl file against schemas/task_instance.schema.json."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "task_instance.schema.json"


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def validate_instance(instance: dict) -> list[str]:
    """Return list of human-readable error messages (empty if valid)."""
    validator = Draft202012Validator(_load_schema())
    errors: list[ValidationError] = sorted(validator.iter_errors(instance), key=lambda e: e.path)
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]


def validate_file(path: Path) -> tuple[int, list[tuple[int, str, str]]]:
    """Return (n_instances, errors). Each error is (line_no, instance_id, message)."""
    schema = _load_schema()
    validator = Draft202012Validator(schema)
    errors: list[tuple[int, str, str]] = []
    n = 0
    with path.open() as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            n += 1
            try:
                inst = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append((i, "<invalid-json>", str(e)))
                continue
            iid = inst.get("instance_id", "<missing>")
            for e in validator.iter_errors(inst):
                loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
                errors.append((i, iid, f"{loc}: {e.message}"))
    return n, errors
