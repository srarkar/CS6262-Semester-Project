"""Check that a dataset follows data-format.md.

    python validate_data.py              # checks data/seed-data_no-ground-truth (and output/ files if present)
    python validate_data.py path/to/data
"""
from __future__ import annotations

import ipaddress
import re
import sys
from collections import defaultdict
from pathlib import Path

import load_data as ld

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HOST_RE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")


def is_date(s) -> bool:
    if not isinstance(s, str) or not DATE_RE.match(s):
        return False
    try:
        ld.to_date(s)
        return True
    except ValueError:
        return False


def validate(data_dir: Path, output_dir: Path) -> list[str]:
    errors: list[str] = []
    err = errors.append

    infra = ld.load_infra(data_dir)
    domains = ld.load_domains(data_dir)
    manifest = ld.load_manifest(data_dir)
    if manifest.get("format_version") != ld.FORMAT_VERSION:
        err(f"manifest format_version {manifest.get('format_version')} != {ld.FORMAT_VERSION}")
    lo, hi = manifest["world_start"], manifest["world_end"]

    seen_domains_per_value = defaultdict(set)
    n = 0
    for i, r in enumerate(ld.iter_jsonl(data_dir / "resolutions.jsonl"), 1):
        n += 1
        where = f"resolutions.jsonl:{i}"
        keys = {"domain", "rrtype", "value", "first_seen", "last_seen", "source"}
        if set(r) != keys:
            err(f"{where}: fields {sorted(r)} != {sorted(keys)}")
            continue
        if r["rrtype"] not in ld.RRTYPES:
            err(f"{where}: bad rrtype {r['rrtype']}")
        if r["source"] not in ld.SOURCES:
            err(f"{where}: bad source {r['source']}")
        if not HOST_RE.match(r["domain"]):
            err(f"{where}: bad domain {r['domain']}")
        if not (is_date(r["first_seen"]) and is_date(r["last_seen"])):
            err(f"{where}: bad dates")
        elif not (lo <= r["first_seen"] <= r["last_seen"] <= hi):
            err(f"{where}: dates out of order or outside {lo}..{hi}")
        v = r["value"]
        try:
            if r["rrtype"] == "A":
                ok = isinstance(ipaddress.ip_address(v), ipaddress.IPv4Address)
            elif r["rrtype"] == "AAAA":
                ok = isinstance(ipaddress.ip_address(v), ipaddress.IPv6Address) and str(ipaddress.ip_address(v)) == v
            else:
                ok = bool(HOST_RE.match(v))
        except ValueError:
            ok = False
        if not ok:
            err(f"{where}: bad value {v} for {r['rrtype']}")
        if v not in infra:
            err(f"{where}: value {v} missing from infra.json")
        if r["domain"] not in domains:
            err(f"{where}: domain {r['domain']} missing from domains.json")
        seen_domains_per_value[v].add(r["domain"])
        if len(errors) > 50:
            return errors + ["... (stopping after 50 errors)"]

    for v, meta in infra.items():
        for k in ("type", "asn", "org", "country", "domain_count", "label"):
            if k not in meta:
                err(f"infra.json[{v}]: missing {k}")
        if meta.get("domain_count") != len(seen_domains_per_value.get(v, ())):
            err(f"infra.json[{v}]: domain_count {meta.get('domain_count')} != {len(seen_domains_per_value.get(v, ()))}")
        if meta.get("label") != "unknown":
            err(f"infra.json[{v}]: raw label must be 'unknown'")

    for d, meta in domains.items():
        regs = meta.get("registrations") or []
        if not regs or not all(is_date(x["registered"]) for x in regs):
            err(f"domains.json[{d}]: bad registrations")
        elif meta.get("registered") != regs[-1]["registered"] or meta.get("registrar") != regs[-1]["registrar"]:
            err(f"domains.json[{d}]: top-level registrar/registered must match latest registration")

    counts = manifest.get("counts", {})
    if counts.get("resolutions") != n:
        err(f"manifest counts.resolutions {counts.get('resolutions')} != {n}")

    # optional stage outputs
    lbl_path = output_dir / "infra_labels.json"
    if lbl_path.exists():
        labels = ld.load_infra_labels(output_dir)
        for v, m in labels.get("infra", {}).items():
            if m.get("label") not in ld.FILTER_LABELS:
                err(f"infra_labels.json[{v}]: bad label {m.get('label')}")
    piv_path = output_dir / "pivot_results.jsonl"
    if piv_path.exists():
        for i, r in enumerate(ld.load_pivot_results(output_dir), 1):
            if r.get("method") not in ld.PIVOT_METHODS:
                err(f"pivot_results.jsonl:{i}: bad method {r.get('method')}")
            if not isinstance(r.get("score"), (int, float)) or not 0 <= r["score"] <= 1:
                err(f"pivot_results.jsonl:{i}: score must be in [0, 1]")
            if not isinstance(r.get("evidence"), dict):
                err(f"pivot_results.jsonl:{i}: evidence must be an object")
    return errors


def main() -> int:
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ld.DATA_DIR / "seed-data_no-ground-truth"
    errors = validate(data_dir, ld.OUTPUT_DIR)
    if errors:
        print("\n".join(errors))
        print(f"FAILED: {len(errors)} problem(s)")
        return 1
    print(f"OK: {data_dir} matches data-format.md v{ld.FORMAT_VERSION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
