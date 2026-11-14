"""Shared JSON/JSONL file I/O; pivot methods operate on the loaded records."""

import json
from pathlib import Path


def load_json(path):
    """Read JSON and include the file and line in decoding errors."""
    with Path(path).open(encoding="utf-8") as stream:
        try:
            return json.load(stream)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"{path}:{error.lineno}: invalid JSON: {error.msg}"
            ) from error


def load_jsonl(path):
    """Read JSON Lines, ignoring blank lines and identifying malformed lines."""
    records = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{path}:{line_number}: invalid JSON: {error.msg}"
                ) from error
    return records


def write_jsonl(path, records):
    """Replace the output with deterministic JSONL, creating its directory."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
