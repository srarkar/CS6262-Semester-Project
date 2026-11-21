"""One-hop domain discovery by registrar, hosting-ASN, and domain-aging fingerprints."""

import argparse
from datetime import date
from ipaddress import ip_address
from pathlib import Path

from load_data import load_domains, load_infra, load_resolutions, read_json, write_jsonl
from pivot.common import normalize_domain, validate_labels


def _registration_periods(metadata):
    """Return valid periods in a stable order, including top-level-only records."""
    periods = metadata.get("registrations")
    if not isinstance(periods, list) or not periods:
        periods = [metadata]
    valid = set()
    for period in periods:
        if not isinstance(period, dict):
            continue
        try:
            registered = date.fromisoformat(period.get("registered"))
            expired = date.fromisoformat(period["expired"]) if period.get("expired") else None
        except (TypeError, ValueError):
            continue
        if expired is not None and expired < registered:
            continue
        registrar = period.get("registrar")
        registrar = registrar.strip().casefold() if isinstance(registrar, str) else None
        valid.add((registered, expired, registrar))
    return sorted(valid, key=lambda period: (period[0], period[1] or date.max, period[2] or ""))


def _fingerprints(resolutions, infrastructure, domains, labels):
    """Build separate fingerprints per registration using eligible A/AAAA records."""
    validate_labels(labels)
    if not isinstance(infrastructure, dict) or not isinstance(domains, dict):
        raise ValueError("infra.json and domains.json must contain objects")

    eligible = {}
    for value, label in labels["infra"].items():
        if label["label"] != "candidate":
            continue
        metadata = infrastructure.get(value)
        if not isinstance(metadata, dict) or metadata.get("type") not in ("ipv4", "ipv6"):
            continue
        try:
            address = ip_address(value)
        except ValueError:
            continue
        if address.version == (4 if metadata["type"] == "ipv4" else 6):
            asn = metadata.get("asn")
            if asn is not None and str(asn).strip():
                eligible.setdefault(str(address), set()).add(str(asn).strip())

    by_domain = {}
    periods_by_domain = {}
    for row_number, row in enumerate(resolutions, 1):
        if not isinstance(row, dict):
            raise ValueError(f"resolution {row_number}: expected an object")
        if row.get("rrtype") not in ("A", "AAAA"):
            continue
        try:
            address = ip_address(row["value"])
            if address.version != (4 if row["rrtype"] == "A" else 6):
                raise ValueError("IP version does not match rrtype")
            domain = normalize_domain(row["domain"])
            first_seen = date.fromisoformat(row["first_seen"])
            last_seen = date.fromisoformat(row["last_seen"])
            if last_seen < first_seen:
                raise ValueError("last_seen precedes first_seen")
            if row["source"] not in ("forward", "passive"):
                raise ValueError("source must be forward or passive")
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"resolution {row_number}: {error}") from error
        asns = eligible.get(str(address))
        if not asns:
            continue
        if domain not in periods_by_domain:
            metadata = domains.get(domain)
            periods_by_domain[domain] = _registration_periods(metadata) if isinstance(metadata, dict) else []
        for period in periods_by_domain[domain]:
            registered, expired, _ = period
            # An observation may cross owners or a registration gap. Only its
            # intersection with this period contributes ASNs and first-use age.
            start = max(first_seen, registered)
            end = min(last_seen, expired) if expired is not None else last_seen
            if start > end:
                continue
            item = by_domain.setdefault(domain, {}).setdefault(
                period, {"first_ip_observation_start": start, "asns": set()})
            item["first_ip_observation_start"] = min(item["first_ip_observation_start"], start)
            item["asns"].update(asns)

    fingerprints = {}
    for domain, episodes in by_domain.items():
        fingerprints[domain] = []
        for period in periods_by_domain[domain]:
            item = episodes.get(period)
            if item is None:
                continue
            registered, expired, registrar = period
            fingerprints[domain].append({
                "asns": item["asns"],
                "first_ip_observation_start": item["first_ip_observation_start"].isoformat(),
                "registrar": registrar,
                "registration_date": registered.isoformat(),
                "registration_expired": expired.isoformat() if expired is not None else None,
                "aging_days": (item["first_ip_observation_start"] - registered).days,
            })
    return fingerprints


def find_fingerprint_matches(seed, resolutions, infrastructure, domains, labels):
    """Return domains sharing candidate-labeled hosting ASNs with a comparable fingerprint.

    The ASN is the pivot key. Registrar agreement and registration-to-first-IP-use
    age contribute to the heuristic score; scores are evidence strengths, not
    probabilities. All historical registration periods are searched separately;
    each candidate retains its strongest complete period pair, with stable ties.
    """
    seed_domain = normalize_domain(seed)
    try:
        ip_address(seed_domain)
    except ValueError:
        pass
    else:
        raise ValueError("IP seeds are not supported; supply a domain seed")

    fingerprints = _fingerprints(resolutions, infrastructure, domains, labels)
    seed_periods = fingerprints.get(seed_domain)
    if not seed_periods:
        return []

    results = []
    for candidate, candidate_periods in sorted(fingerprints.items()):
        if candidate == seed_domain:
            continue
        best = None
        for seed_fp in seed_periods:
            for candidate_fp in candidate_periods:
                shared_asns = sorted(seed_fp["asns"] & candidate_fp["asns"])
                if not shared_asns:
                    continue
                registrar_match = bool(seed_fp["registrar"] and candidate_fp["registrar"]
                                       and seed_fp["registrar"] == candidate_fp["registrar"])
                age_delta = abs(seed_fp["aging_days"] - candidate_fp["aging_days"])
                age_similarity = max(0.0, 1.0 - age_delta / 365.0)
                score = round(0.5 + (0.25 if registrar_match else 0.0) + 0.25 * age_similarity, 6)
                # Periods are chronological; equal scores retain the first pair.
                if best is not None and score <= best["score"]:
                    continue
                fields = ("first_ip_observation_start", "registrar", "registration_date",
                          "registration_expired", "aging_days")
                best = {
                    "seed": seed,
                    "candidate": candidate,
                    "method": "fingerprint_match",
                    "evidence": {
                        "shared_hosting_asns": shared_asns,
                        "seed": {key: seed_fp[key] for key in fields},
                        "candidate": {key: candidate_fp[key] for key in fields},
                        "aging_basis": "registration date to earliest eligible A/AAAA observation within that period; intervals are clipped to registration boundaries",
                        "period_policy": "all historical periods; strongest complete pair",
                        "registrar_match": registrar_match,
                        "aging_delta_days": age_delta,
                        "aging_similarity": round(age_similarity, 6),
                    },
                    "score": score,
                }
        if best is not None:
            results.append(best)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed", help="domain seed (IP seeds are not supported)")
    parser.add_argument("--data-dir", type=Path, default=Path("data/seed-data_no-ground-truth"))
    parser.add_argument("--labels", type=Path, required=True,
                        help="filter output or explicit mock labels")
    parser.add_argument("--output", type=Path, default=Path("output/pivot_results.jsonl"))
    args = parser.parse_args()
    try:
        try:
            labels = read_json(args.labels)
        except ValueError as error:
            raise ValueError(f"{args.labels}: invalid JSON: {error}") from error
        results = find_fingerprint_matches(
            args.seed, load_resolutions(args.data_dir), load_infra(args.data_dir),
            load_domains(args.data_dir), labels)
        write_jsonl(args.output, results)
    except (OSError, ValueError) as error:
        parser.error(str(error).replace(": bad JSON:", ": invalid JSON:"))
    print(f"Wrote {len(results)} result(s) to {args.output} (labels: {args.labels})")


if __name__ == "__main__":
    main()
