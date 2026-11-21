"""One-hop domain discovery by similarity of DNS observation timelines."""

import argparse
from datetime import date
from ipaddress import ip_address
from pathlib import Path

from load_data import load_resolutions, write_jsonl
from pivot.common import merge_intervals, normalize_domain


def _profile_domains(resolutions):
    """Summarize observed intervals and DNS activity without registrar/ASN data."""
    grouped = {}
    for row_number, row in enumerate(resolutions, 1):
        if not isinstance(row, dict):
            raise ValueError(f"resolution {row_number}: expected an object")
        try:
            domain = normalize_domain(row["domain"])
            rrtype = row["rrtype"]
            value = row["value"]
            first = date.fromisoformat(row["first_seen"])
            last = date.fromisoformat(row["last_seen"])
            source = row["source"]
            if rrtype not in ("A", "AAAA", "NS", "MX"):
                raise ValueError("unsupported rrtype")
            if last < first:
                raise ValueError("last_seen precedes first_seen")
            if source not in ("forward", "passive"):
                raise ValueError("source must be forward or passive")
            if rrtype in ("A", "AAAA"):
                address = ip_address(value)
                if address.version != (4 if rrtype == "A" else 6):
                    raise ValueError("IP version does not match rrtype")
                value = str(address)
            elif not isinstance(value, str) or not value:
                raise ValueError("DNS value must be a nonempty string")
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"resolution {row_number}: {error}") from error
        profile = grouped.setdefault(domain, {
            "intervals": [], "sources": {"forward": [], "passive": []},
            "ip_values": set(), "rrtype_values": {"A": set(), "AAAA": set(), "NS": set(), "MX": set()},
            "record_count": 0,
        })
        interval = (first, last)
        profile["intervals"].append(interval)
        profile["sources"][source].append(interval)
        profile["rrtype_values"][rrtype].add(value)
        if rrtype in ("A", "AAAA"):
            profile["ip_values"].add(value)
        profile["record_count"] += 1

    for profile in grouped.values():
        active = merge_intervals(profile["intervals"])
        source_intervals = {name: merge_intervals(intervals)
                            for name, intervals in profile["sources"].items()}
        active_days = sum((end - start).days + 1 for start, end in active)
        start, end = active[0][0], active[-1][1]
        span_days = (end - start).days + 1
        gaps = [(active[i + 1][0] - active[i][1]).days - 1
                for i in range(len(active) - 1)]
        source_days = {
            name: sum((last - first).days + 1 for first, last in intervals)
            for name, intervals in source_intervals.items()
        }
        profile.update({
            "active_intervals": active,
            "first_seen": start,
            "last_seen": end,
            "active_days": active_days,
            "span_days": span_days,
            "max_gap_days": max(gaps, default=0),
            "source_days": source_days,
            "forward_share": source_days["forward"] / max(1, source_days["forward"] + source_days["passive"]),
            "unique_ip_count": len(profile["ip_values"]),
        })
    return grouped


def _overlap_days(left, right):
    total = 0
    for a_start, a_end in left:
        for b_start, b_end in right:
            start, end = max(a_start, b_start), min(a_end, b_end)
            if start <= end:
                total += (end - start).days + 1
    return total


def _ratio_similarity(a, b):
    return min(a, b) / max(a, b) if max(a, b) else 1.0


def find_temporal_matches(seed, resolutions):
    """Compare DNS activity timelines; intentionally does not use registrar or ASN."""
    seed_domain = normalize_domain(seed)
    try:
        ip_address(seed_domain)
    except ValueError:
        pass
    else:
        raise ValueError("IP seeds are not supported; supply a domain seed")

    profiles = _profile_domains(resolutions)
    seed_profile = profiles.get(seed_domain)
    if seed_profile is None:
        return []

    results = []
    for candidate, other in sorted(profiles.items()):
        if candidate == seed_domain:
            continue
        overlap = _overlap_days(seed_profile["active_intervals"], other["active_intervals"])
        if not overlap:
            continue
        union_days = seed_profile["active_days"] + other["active_days"] - overlap
        temporal_jaccard = overlap / union_days if union_days else 0.0
        lifespan_similarity = _ratio_similarity(seed_profile["span_days"], other["span_days"])
        density_similarity = _ratio_similarity(
            seed_profile["active_days"] / seed_profile["span_days"],
            other["active_days"] / other["span_days"])
        source_similarity = 1.0 - abs(seed_profile["forward_share"] - other["forward_share"])
        ip_similarity = _ratio_similarity(seed_profile["unique_ip_count"], other["unique_ip_count"])
        score = (0.55 * temporal_jaccard + 0.15 * lifespan_similarity
                 + 0.10 * density_similarity + 0.10 * source_similarity
                 + 0.10 * ip_similarity)
        results.append({
            "seed": seed,
            "candidate": candidate,
            "method": "temporal_behavior",
            "evidence": {
                "overlap_days": overlap,
                "temporal_jaccard": round(temporal_jaccard, 6),
                "seed_activity": _describe(seed_profile),
                "candidate_activity": _describe(other),
                "similarities": {
                    "lifespan": round(lifespan_similarity, 6),
                    "activity_density": round(density_similarity, 6),
                    "source_mix": round(source_similarity, 6),
                    "unique_ip_count": round(ip_similarity, 6),
                },
            },
            "score": round(min(max(score, 0.0), 1.0), 6),
        })
    return results


def _describe(profile):
    return {
        "first_seen": profile["first_seen"].isoformat(),
        "last_seen": profile["last_seen"].isoformat(),
        "active_days": profile["active_days"],
        "span_days": profile["span_days"],
        "max_gap_days": profile["max_gap_days"],
        "forward_days": profile["source_days"]["forward"],
        "passive_days": profile["source_days"]["passive"],
        "unique_ip_count": profile["unique_ip_count"],
        "record_count": profile["record_count"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed", help="domain seed (IP seeds are not supported)")
    parser.add_argument("--data-dir", type=Path, default=Path("data/seed-data_no-ground-truth"))
    parser.add_argument("--output", type=Path, default=Path("output/pivot_results.jsonl"))
    args = parser.parse_args()
    try:
        results = find_temporal_matches(args.seed, load_resolutions(args.data_dir))
        write_jsonl(args.output, results)
    except (OSError, ValueError) as error:
        parser.error(str(error).replace(": bad JSON:", ": invalid JSON:"))
    print(f"Wrote {len(results)} result(s) to {args.output}")


if __name__ == "__main__":
    main()
