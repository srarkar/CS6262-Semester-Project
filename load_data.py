"""Shared loaders for the pipeline's data files. See DATA_FORMAT.md.

Every stage loads data through this module, so a format change is fixed here once.

    from load_data import load_resolutions, load_infra, load_domains
    res = load_resolutions()                  # list of dicts
    by_domain = index_by(res, "domain")       # {domain: [records]}

Dates stay ISO strings (they compare correctly as strings); use to_date / days_between /
overlap_days when you need arithmetic.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Iterable, Iterator

FORMAT_VERSION = "0.1"

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

RRTYPES = ("A", "AAAA", "NS", "MX")
SOURCES = ("passive", "forward")
PIVOT_METHODS = ("ip_coresidency", "ns_mx_reuse", "fingerprint_match")
FILTER_LABELS = ("parking", "sinkhole", "cdn", "shared_hosting", "candidate")


# ---------------------------------------------------------------- JSON helpers

def read_json(path: Path | str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path | str, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.write("\n")


def iter_jsonl(path: Path | str) -> Iterator[dict]:
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(f"{path}:{n}: bad JSON: {e}") from None


def write_jsonl(path: Path | str, records: Iterable[dict]) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, separators=(", ", ": ")) + "\n")
            n += 1
    return n


# ---------------------------------------------------------------- raw data (stage A)

def load_resolutions(data_dir: Path | str = DATA_DIR, source: str | None = None) -> list[dict]:
    """All DNS observations. source='passive' or 'forward' keeps only that sensor."""
    recs = iter_jsonl(Path(data_dir) / "resolutions.jsonl")
    if source is not None:
        if source not in SOURCES:
            raise ValueError(f"source must be one of {SOURCES}")
        return [r for r in recs if r["source"] == source]
    return list(recs)


def load_infra(data_dir: Path | str = DATA_DIR) -> dict[str, dict]:
    return read_json(Path(data_dir) / "infra.json")


def load_domains(data_dir: Path | str = DATA_DIR) -> dict[str, dict]:
    return read_json(Path(data_dir) / "domains.json")


def load_manifest(data_dir: Path | str = DATA_DIR) -> dict:
    return read_json(Path(data_dir) / "manifest.json")


def load_actor_configs(actors_dir: Path | str = DATA_DIR / "actors") -> list[dict]:
    return [read_json(p) for p in sorted(Path(actors_dir).glob("*.json"))]


def load_ground_truth(data_dir: Path | str = DATA_DIR) -> dict:
    """EVALUATION ONLY (stage E). The filter and pivot stages must never call this."""
    return read_json(Path(data_dir) / "ground_truth.json")


# ---------------------------------------------------------------- stage outputs (C, D)

def load_infra_labels(output_dir: Path | str = OUTPUT_DIR) -> dict:
    return read_json(Path(output_dir) / "infra_labels.json")


def load_pivot_results(output_dir: Path | str = OUTPUT_DIR) -> list[dict]:
    return list(iter_jsonl(Path(output_dir) / "pivot_results.jsonl"))


# ---------------------------------------------------------------- helpers

def to_date(s: str) -> date:
    return date.fromisoformat(s)


def days_between(a: str, b: str) -> int:
    """b - a in days."""
    return (to_date(b) - to_date(a)).days


def overlap_days(a_first: str, a_last: str, b_first: str, b_last: str) -> int:
    """Days two [first, last] ranges overlap (inclusive); 0 if they don't."""
    start, end = max(a_first, b_first), min(a_last, b_last)
    return days_between(start, end) + 1 if start <= end else 0


def index_by(records: Iterable[dict], key: str) -> dict[str, list[dict]]:
    """Group records by a field, e.g. index_by(res, "value") -> {ip: [records]}."""
    out: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        out[r[key]].append(r)
    return dict(out)