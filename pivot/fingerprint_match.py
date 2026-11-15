"""One-hop domain discovery by registrar, hosting-ASN, and domain-aging fingerprints."""

import argparse
from datetime import date
from ipaddress import ip_address
from pathlib import Path

from load_data import load_domains, load_infra, load_resolutions, read_json, write_jsonl
from pivot.common import normalize_domain, validate_labels


def _registration_at(metadata, observed_on):
    """Return the registration period active at observed_on, or None."""
    periods = metadata.get("registrations")
    if isinstance(periods, list) and periods:
        for period in periods:
            if not isinstance(period, dict):
                continue
            registered = period.get("registered")
            expired = period.get("expired")
            if not isinstance(registered, str):
                continue
            try:
                start = date.fromisoformat(registered)
                end = date.fromisoformat(expired) if expired else None
            except ValueError:
                continue
            observed = date.fromisoformat(observed_on)
            if start <= observed and (end is None or observed <= end):
                return period
        return None

    registered = metadata.get("registered")
    if not isinstance(registered, str):
        return None
    try:
        if date.fromisoformat(registered) <= date.fromisoformat(observed_on):
            return {"registered": registered, "expired": None,
                    "registrar": metadata.get("registrar")}
    except ValueError:
        pass
    return None


def _fingerprints(seed, resolutions, infrastructure, domains, labels):
    """Build fingerprints using only candidate-labeled A/AAAA infrastructure."""
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
        item = by_domain.setdefault(domain, {"first_ip_observation_start": first_seen, "asns": set()})
        item["first_ip_observation_start"] = min(item["first_ip_observation_start"], first_seen)
        item["asns"].update(asns)

    fingerprints = {}
    for domain, item in by_domain.items():
        metadata = domains.get(domain)
        if not isinstance(metadata, dict):
            continue
        first_seen = item["first_ip_observation_start"].isoformat()
        registration = _registration_at(metadata, first_seen)
        if registration is None:
            continue
        try:
            aging_days = (item["first_ip_observation_start"] - date.fromisoformat(registration["registered"])).days
        except (KeyError, TypeError, ValueError):
            continue
        if aging_days < 0:
            continue
        registrar = registration.get("registrar")
        fingerprints[domain] = {
            "asns": item["asns"],
            "first_ip_observation_start": first_seen,
            "registrar": registrar.strip().casefold() if isinstance(registrar, str) else None,
            "registration_date": registration["registered"],
            "aging_days": aging_days,
        }
    return fingerprints


def find_fingerprint_matches(seed, resolutions, infrastructure, domains, labels):
    """Return domains sharing candidate-labeled hosting ASNs with a comparable fingerprint.

    The ASN is the pivot key. Registrar agreement and registration-to-first-IP-use
    age contribute to the heuristic score; scores are evidence strengths, not
    probabilities. Registration history is evaluated at first observed IP use.
    """
    seed_domain = normalize_domain(seed)
    try:
        ip_address(seed_domain)
    except ValueError:
        pass
    else:
        raise ValueError("IP seeds are not supported; supply a domain seed")

    fingerprints = _fingerprints(seed_domain, resolutions, infrastructure, domains, labels)
    seed_fp = fingerprints.get(seed_domain)
    if seed_fp is None:
        return []

    results = []
    for candidate, candidate_fp in sorted(fingerprints.items()):
        if candidate == seed_domain:
            continue
        shared_asns = sorted(seed_fp["asns"] & candidate_fp["asns"])
        if not shared_asns:
            continue
        registrar_match = bool(seed_fp["registrar"] and candidate_fp["registrar"]
                               and seed_fp["registrar"] == candidate_fp["registrar"])
        age_delta = abs(seed_fp["aging_days"] - candidate_fp["aging_days"])
        age_similarity = max(0.0, 1.0 - age_delta / 365.0)
        score = 0.5 + (0.25 if registrar_match else 0.0) + 0.25 * age_similarity
        results.append({
            "seed": seed,
            "candidate": candidate,
            "method": "fingerprint_match",
            "evidence": {
                "shared_hosting_asns": shared_asns,
                "seed": {key: seed_fp[key] for key in
                         ("first_ip_observation_start", "registrar", "registration_date", "aging_days")},
                "candidate": {key: candidate_fp[key] for key in
                              ("first_ip_observation_start", "registrar", "registration_date", "aging_days")},
                "aging_basis": "registration date to earliest A/AAAA first_seen; this is the observation interval start, not an inferred activation date",
                "registrar_match": registrar_match,
                "aging_delta_days": age_delta,
                "aging_similarity": round(age_similarity, 6),
            },
            "score": round(min(score, 1.0), 6),
        })
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
