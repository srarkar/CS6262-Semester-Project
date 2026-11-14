"""One-hop, domain-seed temporal IP co-residency using explicit filter labels."""

import argparse
from datetime import date
from ipaddress import ip_address
from pathlib import Path

from load_data import load_json, load_jsonl, write_jsonl


def normalize_domain(domain):
    """Match schema names while allowing surrounding whitespace and a DNS dot."""
    if not isinstance(domain, str) or not domain.strip().rstrip("."):
        raise ValueError("domain must be a nonempty string")
    return domain.strip().rstrip(".").lower()


def validate_labels(labels):
    """Reject malformed filter output instead of silently allowing expansion."""
    if not isinstance(labels, dict) or not isinstance(labels.get("infra"), dict):
        raise ValueError("labels must contain an 'infra' object")
    if not isinstance(labels.get("domains"), dict):
        raise ValueError("labels must contain a 'domains' object (may be empty)")
    allowed = ("candidate", "parking", "sinkhole", "cdn", "shared_hosting")
    for value, entry in labels["infra"].items():
        if not isinstance(entry, dict) or entry.get("label") not in allowed:
            raise ValueError(f"labels infra[{value!r}] has an invalid label")
        confidence = entry.get("confidence")
        reasons = entry.get("reasons")
        if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
            raise ValueError(f"labels infra[{value!r}] needs confidence in [0, 1]")
        if not isinstance(reasons, list) or any(
            not isinstance(reason, str) for reason in reasons
        ):
            raise ValueError(f"labels infra[{value!r}] needs a list of reasons")


def merge_intervals(intervals):
    """Union overlapping closed date intervals without bridging unobserved gaps."""
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def describe_observations(observations):
    """Retain exact source dates; a union must not imply earlier passive coverage."""
    return [
        {"first_seen": start.isoformat(), "last_seen": end.isoformat(), "source": source}
        for start, end, source in sorted(set(observations))
    ]


def find_ip_coresidents(seed, resolutions, infrastructure, labels):
    """Return one explained result per domain, using loaded v0.1 records.

    Only explicitly candidate-labeled IPs with infrastructure metadata are used.
    Both date endpoints count. The score is the strongest IP's overlap / 30,
    capped at 1; multiple IPs add evidence without counting their days together.
    """
    seed_domain = normalize_domain(seed)
    try:
        ip_address(seed_domain)
    except ValueError:
        pass
    else:
        raise ValueError("IP seeds are not supported; supply a domain seed")
    validate_labels(labels)
    if not isinstance(infrastructure, dict):
        raise ValueError("infra.json must contain an object")

    eligible = {}
    for value, label in labels["infra"].items():
        if label["label"] != "candidate":
            continue
        metadata = infrastructure.get(value)
        if not isinstance(metadata, dict) or metadata.get("type") not in ("ipv4", "ipv6"):
            continue
        try:
            address = str(ip_address(value))
        except ValueError:
            continue  # NS/MX filter entries are outside this method.
        eligible[address] = (metadata, label)

    by_ip = {}
    seed_ips = set()
    for row_number, row in enumerate(resolutions, 1):
        if not isinstance(row, dict):
            raise ValueError(f"resolution {row_number}: expected an object")
        if row.get("rrtype") not in ("A", "AAAA"):
            continue
        try:
            address = ip_address(row["value"])
            if address.version != (4 if row["rrtype"] == "A" else 6):
                raise ValueError("IP version does not match rrtype")
            address = str(address)
            if address not in eligible:
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
        by_ip.setdefault(address, {}).setdefault(domain, []).append((start, end, source))
        if domain == seed_domain:
            seed_ips.add(address)

    evidence_by_candidate = {}
    for address in sorted(seed_ips):
        seed_observations = by_ip[address][seed_domain]
        seed_intervals = merge_intervals([(start, end) for start, end, _ in seed_observations])
        for candidate, observations in sorted(by_ip[address].items()):
            if candidate == seed_domain:
                continue
            candidate_intervals = merge_intervals([(start, end) for start, end, _ in observations])
            overlaps = []
            for seed_start, seed_end in seed_intervals:
                for candidate_start, candidate_end in candidate_intervals:
                    start = max(seed_start, candidate_start)
                    end = min(seed_end, candidate_end)
                    if start <= end:
                        overlaps.append((start, end))
            # Union again so no observed day can contribute twice for an IP.
            overlap_intervals = merge_intervals(overlaps)
            if not overlap_intervals:
                continue
            overlap_days = sum((end - start).days + 1 for start, end in overlap_intervals)
            metadata, label = eligible[address]
            evidence_by_candidate.setdefault(candidate, []).append({
                "ip": address,
                "domain_count": metadata.get("domain_count"),
                "filter_label": label,
                "seed_observations": describe_observations(seed_observations),
                "candidate_observations": describe_observations(observations),
                "overlap_intervals": [
                    {"first_seen": start.isoformat(), "last_seen": end.isoformat(),
                     "days": (end - start).days + 1}
                    for start, end in overlap_intervals
                ],
                "overlap_days": overlap_days,
            })

    results = []
    for candidate, shared_ips in sorted(evidence_by_candidate.items()):
        strongest_overlap = max(item["overlap_days"] for item in shared_ips)
        results.append({
            "seed": seed,
            "candidate": candidate,
            "method": "ip_coresidency",
            "evidence": {"shared_ips": shared_ips},
            "score": round(min(strongest_overlap / 30, 1.0), 6),
        })
    return results


def main():
    """Load only observations, infrastructure and explicit labels; write JSONL."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed", help="domain seed (IP seeds are not supported)")
    parser.add_argument("--data-dir", type=Path, default=Path("data_seeding/seed-data-no-ground-truth"))
    parser.add_argument("--labels", type=Path, required=True, help="filter output or explicit mock labels")
    parser.add_argument("--output", type=Path, default=Path("output/pivot_results.jsonl"))
    args = parser.parse_args()
    try:
        labels = load_json(args.labels)
        validate_labels(labels)
        resolutions = load_jsonl(args.data_dir / "resolutions.jsonl")
        infrastructure = load_json(args.data_dir / "infra.json")
        results = find_ip_coresidents(args.seed, resolutions, infrastructure, labels)
        write_jsonl(args.output, results)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Wrote {len(results)} result(s) to {args.output} (labels: {args.labels})")


if __name__ == "__main__":
    main()
