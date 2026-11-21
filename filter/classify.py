"""Label shared DNS infrastructure and derive domain lifecycle features.

This is a transparent baseline heuristic for the synthetic project data. It
does not use simulator ground truth and its labels are not threat verdicts.
"""

import argparse
from datetime import date
from pathlib import Path

from load_data import (load_domains, load_infra, load_resolutions, write_json)

SHARED_DOMAIN_LIMITS = {"ipv4": 20, "ipv6": 20, "ns": 20, "mx": 20}
CDN_MARKERS = ("cloudflare", "cloudfront", "fastly", "akamai")


def _text(metadata, value):
    return " ".join(str(metadata.get(key, "")) for key in ("org", "provider", "name", "hostname", "description")) + " " + value


def classify_infrastructure(infrastructure):
    """Return one schema-compatible label for every infrastructure value."""
    labels = {}
    for value, metadata in sorted(infrastructure.items()):
        text = _text(metadata, value).casefold()
        count = metadata.get("domain_count")
        kind = metadata.get("type")

        if "parking" in text:
            label, confidence, reason = "parking", 0.98, "provider or hostname identifies parking infrastructure"
        elif "sinkhole" in text:
            label, confidence, reason = "sinkhole", 0.98, "provider or hostname identifies sinkhole infrastructure"
        elif any(marker in text for marker in CDN_MARKERS):
            label, confidence, reason = "cdn", 0.90, "provider or hostname matches a common CDN marker"
        elif type(count) is int and count >= SHARED_DOMAIN_LIMITS.get(kind, 20):
            label, confidence, reason = "shared_hosting", 0.80, f"high reuse: domain_count={count} (limit={SHARED_DOMAIN_LIMITS.get(kind, 20)})"
        elif type(count) is int and count > 0:
            label, confidence, reason = "candidate", 0.60, f"no noise rule matched; domain_count={count}"
        else:
            label, confidence, reason = "shared_hosting", 0.35, "missing or invalid domain_count; conservatively excluded"

        labels[value] = {"label": label, "confidence": confidence, "reasons": [reason]}
    return labels


def _registration_for_date(domain_metadata, observed_date):
    """Find the registration period active at an observed date, if available."""
    registrations = domain_metadata.get("registrations")
    if isinstance(registrations, list):
        active = []
        for registration in registrations:
            try:
                registered = date.fromisoformat(registration["registered"])
                expired = registration.get("expired")
                if registered <= observed_date and (expired is None or observed_date <= date.fromisoformat(expired)):
                    active.append((registered, registration))
            except (KeyError, TypeError, ValueError):
                continue
        if active:
            return max(active, key=lambda item: item[0])[1]
        return None

    try:
        registered = date.fromisoformat(domain_metadata["registered"])
    except (KeyError, TypeError, ValueError):
        return None
    return {"registered": registered.isoformat()}


def domain_features(resolutions, domains, infra_labels):
    """Build registration aging and observed-resolution lifespan features."""
    earliest_candidate_ip = {}
    max_lifespan = {}
    for row in resolutions:
        domain = row["domain"].strip().rstrip(".").casefold()
        try:
            first = date.fromisoformat(row["first_seen"])
            last = date.fromisoformat(row["last_seen"])
        except (KeyError, TypeError, ValueError):
            continue
        max_lifespan[domain] = max(max_lifespan.get(domain, 0), (last - first).days + 1)
        if row.get("rrtype") in ("A", "AAAA") and infra_labels.get(row.get("value"), {}).get("label") == "candidate":
            if domain not in earliest_candidate_ip or first < earliest_candidate_ip[domain][0]:
                earliest_candidate_ip[domain] = (first, row["value"])

    features = {}
    for domain in sorted(set(domains) | set(max_lifespan) | set(earliest_candidate_ip)):
        first_ip = earliest_candidate_ip.get(domain)
        aging_days = None
        first_ip_date = first_ip[0] if first_ip else None
        if first_ip_date and isinstance(domains.get(domain), dict):
            registration = _registration_for_date(domains[domain], first_ip_date)
            if registration:
                try:
                    aging_days = (first_ip_date - date.fromisoformat(registration["registered"])).days
                except (KeyError, TypeError, ValueError):
                    pass
        features[domain] = {
            "aging_days": aging_days,
            "first_candidate_ip": first_ip[1] if first_ip else None,
            "max_lifespan_days": max_lifespan.get(domain),
        }
    return features


def build_labels(infrastructure, resolutions, domains):
    """Create the complete infra_labels.json payload from non-truth inputs."""
    infra_labels = classify_infrastructure(infrastructure)
    return {
        "infra": infra_labels,
        "domains": domain_features(resolutions, domains, infra_labels),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/seed-data_no-ground-truth"))
    parser.add_argument("--output", type=Path, default=Path("output/infra_labels.json"))
    args = parser.parse_args()
    try:
        labels = build_labels(load_infra(args.data_dir), load_resolutions(args.data_dir), load_domains(args.data_dir))
        write_json(args.output, labels)
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.error(str(error))
    counts = {}
    for entry in labels["infra"].values():
        counts[entry["label"]] = counts.get(entry["label"], 0) + 1
    print(f"Wrote {len(labels['infra'])} infrastructure labels and {len(labels['domains'])} domain feature records to {args.output}")
    print("Labels: " + ", ".join(f"{name}={count}" for name, count in sorted(counts.items())))


if __name__ == "__main__":
    main()
