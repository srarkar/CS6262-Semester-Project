"""One-hop domain discovery through rare NS/MX hosts used on overlapping dates."""

import argparse
from datetime import date
from ipaddress import ip_address
from pathlib import Path

from load_data import load_resolutions, load_infra, read_json, write_jsonl
from pivot.common import describe_observations, find_overlap_intervals, normalize_domain, validate_labels


def find_ns_mx_reuse(seed, resolutions, infrastructure, labels, max_domain_count=10):
    """Return one explained result per domain sharing an eligible NS/MX host.

    Hosts need an explicit candidate label and a positive domain_count no greater
    than max_domain_count. Overlap is required; score is the strongest matching
    host's 1 / domain_count, not a probability of maliciousness.
    """
    seed_domain = normalize_domain(seed)
    try:
        ip_address(seed_domain)
    except ValueError:
        pass
    else:
        raise ValueError("IP seeds are not supported; supply a domain seed")
    if type(max_domain_count) is not int or max_domain_count < 1:
        raise ValueError("max_domain_count must be a positive integer")
    validate_labels(labels)
    if not isinstance(infrastructure, dict):
        raise ValueError("infra.json must contain an object")

    eligible = {}
    for host, label in labels["infra"].items():
        metadata = infrastructure.get(host)
        if label["label"] != "candidate" or not isinstance(metadata, dict):
            continue
        if metadata.get("type") not in ("ns", "mx"):
            continue
        count = metadata.get("domain_count")
        # Missing or invalid counts cannot establish that a host is uncommon.
        if type(count) is not int or not 1 <= count <= max_domain_count:
            continue
        key = (metadata["type"].upper(), normalize_domain(host))
        eligible[key] = (count, label)

    by_host = {}
    seed_hosts = set()
    for row_number, row in enumerate(resolutions, 1):
        if not isinstance(row, dict):
            raise ValueError(f"resolution {row_number}: expected an object")
        if row.get("rrtype") not in ("NS", "MX"):
            continue
        try:
            # Record type is part of the key: an NS record never matches an MX.
            key = (row["rrtype"], normalize_domain(row["value"]))
            if key not in eligible:
                continue
            domain = normalize_domain(row["domain"])
            start = date.fromisoformat(row["first_seen"])
            end = date.fromisoformat(row["last_seen"])
            source = row["source"]
            if end < start:
                raise ValueError("last_seen precedes first_seen")
            if source not in ("forward", "passive"):
                raise ValueError("source must be forward or passive")
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"resolution {row_number}: {error}") from error
        by_host.setdefault(key, {}).setdefault(domain, []).append((start, end, source))
        if domain == seed_domain:
            seed_hosts.add(key)

    evidence_by_candidate = {}
    for key in sorted(seed_hosts):
        rrtype, host = key
        seed_observations = by_host[key][seed_domain]
        for candidate, observations in sorted(by_host[key].items()):
            if candidate == seed_domain:
                continue
            overlaps = find_overlap_intervals(seed_observations, observations)
            if not overlaps:
                continue
            count, label = eligible[key]
            evidence_by_candidate.setdefault(candidate, []).append({
                "host": host,
                "rrtype": rrtype,
                "domain_count": count,
                "filter_label": label,
                "seed_observations": describe_observations(seed_observations),
                "candidate_observations": describe_observations(observations),
                "overlap_intervals": [
                    {"first_seen": start.isoformat(), "last_seen": end.isoformat(),
                     "days": (end - start).days + 1}
                    for start, end in overlaps
                ],
                "overlap_days": sum((end - start).days + 1 for start, end in overlaps),
            })

    results = []
    for candidate, shared_hosts in sorted(evidence_by_candidate.items()):
        results.append({
            "seed": seed,
            "candidate": candidate,
            "method": "ns_mx_reuse",
            "evidence": {"shared_hosts": shared_hosts, "max_domain_count": max_domain_count},
            "score": round(max(1 / item["domain_count"] for item in shared_hosts), 6),
        })
    return results


def main():
    """Read shared inputs, run the method, and replace a JSONL results file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed", help="domain seed (IP seeds are not supported)")
    parser.add_argument("--data-dir", type=Path, default=Path("data/seed-data_no-ground-truth"))
    parser.add_argument("--labels", type=Path, required=True, help="filter output or explicit mock labels")
    parser.add_argument("--max-domain-count", type=int, default=10, help="maximum domains per host (default: 10)")
    parser.add_argument("--output", type=Path, default=Path("output/pivot_results.jsonl"))
    args = parser.parse_args()
    try:
        resolutions = load_resolutions(args.data_dir)
        infrastructure = load_infra(args.data_dir)
        labels = read_json(args.labels)
        results = find_ns_mx_reuse(args.seed, resolutions, infrastructure, labels, args.max_domain_count)
        write_jsonl(args.output, results)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Wrote {len(results)} result(s) to {args.output} (labels: {args.labels})")


if __name__ == "__main__":
    main()
