"""Domain names, filter labels, and date intervals shared by both pivot methods."""


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


def find_overlap_intervals(seed_observations, candidate_observations):
    """Intersect observed date unions so duplicates and sources cannot inflate days."""
    seed_intervals = merge_intervals([(start, end) for start, end, _ in seed_observations])
    candidate_intervals = merge_intervals([(start, end) for start, end, _ in candidate_observations])
    overlaps = []
    for seed_start, seed_end in seed_intervals:
        for candidate_start, candidate_end in candidate_intervals:
            start = max(seed_start, candidate_start)
            end = min(seed_end, candidate_end)
            if start <= end:
                overlaps.append((start, end))
    return merge_intervals(overlaps)


def describe_observations(observations):
    """Retain exact source dates; a union must not imply earlier passive coverage."""
    return [
        {"first_seen": start.isoformat(), "last_seen": end.isoformat(), "source": source}
        for start, end, source in sorted(set(observations))
    ]
