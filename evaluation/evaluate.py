"""Benchmark the pivot methods against the simulator's ground truth.

Only this stage reads ground_truth.json. The pivots run on the dataset without
ground truth and receive only observations, metadata, and filter labels.
See evaluation/README.md for the metric definitions and run commands.
"""

import argparse
import random
from pathlib import Path
from statistics import mean, median

from load_data import (load_domains, load_ground_truth, load_infra, load_resolutions,
                       read_json, write_json, write_jsonl)
from pivot.ip_coresidency import find_ip_coresidents
from pivot.ns_mx_reuse import find_ns_mx_reuse

# Rick's two methods live on the rickdev/pivoting branch until it is merged.
try:
    from pivot.fingerprint_match import find_fingerprint_matches
except ImportError:
    find_fingerprint_matches = None
try:
    from pivot.temporal_behavior import find_temporal_matches
except ImportError:
    find_temporal_matches = None

TOP_K = (5, 10, 25)
# Standard reciprocal-rank-fusion constant: keeps one method's first place from
# outweighing several methods agreeing on a slightly lower rank.
RRF_K = 60
# Ground-truth infrastructure roles that the perfect filter treats as eligible.
PERFECT_FILTER_ELIGIBLE = ("actor", "dedicated", "self_hosted_ns", "self_hosted_mail")
# Methods whose evidence names the shared IP or host, for evidence correctness.
SHARED_INFRA_METHODS = ("ip_coresidency", "ns_mx_reuse")


def choose_seeds(domain_labels, observed_domains, benign_sample, random_seed):
    """Return [(seed, group)], where group is an actor name, 'benign', or 'crimeware'.

    Only domains with at least one observation become seeds: a seed without
    records returns nothing from every method and says nothing about them.
    Every observed actor and crimeware domain is used; benign seeds are a fixed
    random sample so runs stay comparable.
    """
    actor_seeds, crimeware_seeds, benign_domains = [], [], []
    for domain in sorted(observed_domains):
        label = domain_labels.get(domain)
        if label is None:
            continue
        if label.startswith("actor:"):
            actor_seeds.append((domain, label[len("actor:"):]))
        elif label == "crimeware":
            crimeware_seeds.append((domain, "crimeware"))
        elif label == "benign":
            benign_domains.append(domain)
    sample = random.Random(random_seed).sample(benign_domains, min(benign_sample, len(benign_domains)))
    return actor_seeds + [(domain, "benign") for domain in sorted(sample)] + crimeware_seeds


def no_filter_labels(infrastructure):
    """Label every IP/NS/MX value candidate: the lower-bound condition."""
    entry = {"label": "candidate", "confidence": 1.0, "reasons": ["no-filter evaluation condition"]}
    return {"infra": {value: dict(entry) for value in infrastructure}, "domains": {}}


def perfect_filter_labels(ground_truth):
    """Build eligibility from ground-truth roles: the upper-bound condition.

    Values whose true role is actor-controlled or single-tenant become candidate.
    All other values are left unlabeled, which every pivot treats as ineligible.
    These labels exist only inside evaluation and must not be used for tuning.
    """
    infra = {}
    for value, role in ground_truth["infra_labels"].items():
        if role in PERFECT_FILTER_ELIGIBLE:
            infra[value] = {"label": "candidate", "confidence": 1.0,
                            "reasons": [f"perfect-filter evaluation condition: ground truth {role}"]}
    return {"infra": infra, "domains": {}}


def actor_values(truth):
    """All IPs, NS hosts, and MX hosts the simulator assigned to one actor."""
    return set(truth["ips"]) | set(truth["ns_hosts"]) | set(truth["mx_hosts"])


def index_actor_infra(resolutions, ground_truth):
    """Map each actor IP/NS/MX value to {domain: [(first_seen, last_seen)]}."""
    values = set()
    for truth in ground_truth["actors"].values():
        values |= actor_values(truth)
    index = {}
    for row in resolutions:
        if row["value"] in values:
            index.setdefault(row["value"], {}).setdefault(row["domain"], []).append(
                (row["first_seen"], row["last_seen"]))
    return index


def one_hop_reachable(seed, positives, truth, infra_index):
    """Positives that used one of the actor's own values on dates overlapping the seed's use.

    This is what an ideal one-hop shared-infrastructure pivot could find. ISO
    date strings compare correctly, so two inclusive ranges overlap when the
    later start is on or before the earlier end.
    """
    reachable = set()
    for value in actor_values(truth):
        users = infra_index.get(value, {})
        for seed_first, seed_last in users.get(seed, []):
            for domain, intervals in users.items():
                if domain not in positives:
                    continue
                for first, last in intervals:
                    if max(seed_first, first) <= min(seed_last, last):
                        reachable.add(domain)
    return reachable


def rank_candidates(results):
    """Order candidates by their best score, highest first; ties break by name.

    Applied to one method's results this is that method's ranking. Applied to
    all methods' results together it is the max-score combination.
    """
    best = {}
    for result in results:
        best[result["candidate"]] = max(result["score"], best.get(result["candidate"], 0.0))
    return [candidate for candidate, _ in sorted(best.items(), key=lambda item: (-item[1], item[0]))]


def fuse_reciprocal_rank(rankings):
    """Combine rankings: each candidate earns 1 / (RRF_K + rank) from each method.

    Rank is used instead of score because method scores have different meanings
    and scales (for example, fingerprint scores never fall below 0.5).
    """
    totals = {}
    for ranking in rankings:
        for position, candidate in enumerate(ranking, 1):
            totals[candidate] = totals.get(candidate, 0.0) + 1 / (RRF_K + position)
    return [candidate for candidate, _ in sorted(totals.items(), key=lambda item: (-item[1], item[0]))]


def average_precision(ranking, positives):
    """Mean of the precision at each rank where a positive appears, over all positives.

    Positives that are never returned contribute zero, so low recall lowers AP.
    """
    if not positives:
        return None
    hits = 0
    total = 0.0
    for position, candidate in enumerate(ranking, 1):
        if candidate in positives:
            hits += 1
            total += hits / position
    return total / len(positives)


def recall(found, positives):
    """Share of positives found; undefined (None) when there are no positives."""
    return len(found & positives) / len(positives) if positives else None


def actor_seed_metrics(ranking, actor, seed, ground_truth, observed_domains, infra_index):
    """Ranking metrics for a seed from a known actor (leave-one-out).

    Precision at k divides by k even when fewer than k candidates are returned,
    so a short list is not rewarded for stopping early.
    """
    truth = ground_truth["actors"][actor]
    all_positives = set(truth["domains"]) - {seed}
    positives = all_positives & observed_domains
    reachable = one_hop_reachable(seed, positives, truth, infra_index)
    returned = set(ranking)
    labels = ground_truth["domain_labels"]
    metrics = {
        "n_results": len(ranking),
        "n_positives": len(positives),
        "n_reachable": len(reachable),
        "average_precision": average_precision(ranking, positives),
        "precision": len(returned & positives) / len(ranking) if ranking else None,
        "recall_all": recall(returned, all_positives),
        "recall_observed": recall(returned, positives),
        "recall_reachable": recall(returned, reachable),
    }
    for k in TOP_K:
        top = set(ranking[:k])
        metrics[f"precision_at_{k}"] = len(top & positives) / k
        metrics[f"recall_at_{k}"] = recall(top, positives)
    # Crimeware or another actor's domains: malicious, but wrong answers here.
    metrics["other_malicious_in_top_25"] = sum(
        1 for candidate in ranking[:25]
        if labels.get(candidate) == "crimeware"
        or (labels.get(candidate, "").startswith("actor:") and labels[candidate] != f"actor:{actor}"))
    return metrics


def non_actor_seed_metrics(ranking, ground_truth):
    """For benign and crimeware seeds every actor domain returned is a false lead."""
    labels = ground_truth["domain_labels"]
    is_actor = [labels.get(candidate, "").startswith("actor:") for candidate in ranking]
    return {"n_results": len(ranking),
            "actor_domains_in_top_25": sum(is_actor[:25]),
            "actor_domains_returned": sum(is_actor)}


def evidence_correct_share(results, positives, truth):
    """Share of true positives whose shared IP or host is one of the actor's own values.

    A true positive reached only through someone else's infrastructure was found
    by coincidence rather than because of the actor's reuse.
    """
    own = actor_values(truth)
    true_positive_results = [result for result in results if result["candidate"] in positives]
    if not true_positive_results:
        return None
    correct = 0
    for result in true_positive_results:
        evidence = result["evidence"]
        shared = ([item["ip"] for item in evidence.get("shared_ips", [])]
                  + [item["host"] for item in evidence.get("shared_hosts", [])])
        if any(value in own for value in shared):
            correct += 1
    return correct / len(true_positive_results)


def available_methods(resolutions, infrastructure, domains, max_domain_count):
    """Return [(method name, function(seed, labels))] for the pivots on this branch."""
    methods = [
        ("ip_coresidency",
         lambda seed, labels: find_ip_coresidents(seed, resolutions, infrastructure, labels)),
        ("ns_mx_reuse",
         lambda seed, labels: find_ns_mx_reuse(seed, resolutions, infrastructure, labels, max_domain_count)),
    ]
    if find_fingerprint_matches is not None:
        methods.append(("fingerprint_match",
                        lambda seed, labels: find_fingerprint_matches(seed, resolutions, infrastructure, domains, labels)))
    if find_temporal_matches is not None:
        methods.append(("temporal_behavior",
                        lambda seed, labels: find_temporal_matches(seed, resolutions)))
    return methods


def summarize(rows):
    """Aggregate per-seed rows by condition, method, and seed group.

    Undefined values (None) are left out of means and medians. The 'overall'
    entry averages the per-actor means, weighting actors equally so the actor
    with more seeds does not dominate.
    """
    groups = {}
    for row in rows:
        groups.setdefault((row["condition"], row["method"], row["seed_group"]), []).append(row)
    summary = {}
    for (condition, method, group), group_rows in sorted(groups.items()):
        metrics = {"n_seeds": len(group_rows)}
        for name in group_rows[0]:
            if name in ("condition", "method", "seed", "seed_group"):
                continue
            values = [row[name] for row in group_rows if row.get(name) is not None]
            metrics[name] = ({"mean": round(mean(values), 4), "median": round(median(values), 4)}
                             if values else None)
        summary.setdefault(condition, {}).setdefault(method, {})[group] = metrics

    for methods in summary.values():
        for groups_by_name in methods.values():
            actor_groups = [m for name, m in groups_by_name.items() if name not in ("benign", "crimeware")]
            if not actor_groups:
                continue
            overall = {}
            for name in actor_groups[0]:
                if name == "n_seeds":
                    continue
                means = [m[name]["mean"] for m in actor_groups if m.get(name) is not None]
                overall[name] = round(mean(means), 4) if means else None
            groups_by_name["overall"] = overall
    return summary


def print_summary(summary, unique_true_positives):
    """Print the headline table for each condition."""
    columns = [("AP", "average_precision"), ("P@10", "precision_at_10"), ("R@25", "recall_at_25"),
               ("R obs", "recall_observed"), ("R reach", "recall_reachable"), ("results", "n_results")]
    for condition, methods in summary.items():
        print(f"\n== {condition}  (actor-seed means, actors weighted equally)")
        print(f"{'method':18}" + "".join(f"{label:>9}" for label, _ in columns)
              + f"{'benign FP@25':>14}{'unique TP@25':>14}")
        for method, groups in methods.items():
            overall = groups["overall"]
            cells = "".join(f"{overall[key]:9.3f}" if overall.get(key) is not None else f"{'-':>9}"
                            for _, key in columns)
            benign = groups.get("benign", {}).get("actor_domains_in_top_25")
            benign_cell = f"{benign['mean']:14.3f}" if benign else f"{'-':>14}"
            unique = unique_true_positives[condition].get(method)
            unique_cell = f"{unique:14d}" if unique is not None else f"{'-':>14}"
            print(f"{method:18}{cells}{benign_cell}{unique_cell}")


def evaluate(data_dir, truth_dir, output_dir, labels_path=None, max_domain_count=10,
             benign_sample=100, random_seed=6262):
    """Run every method for every seed under each filter condition and score the results."""
    resolutions = load_resolutions(data_dir)
    infrastructure = load_infra(data_dir)
    domains = load_domains(data_dir)
    ground_truth = load_ground_truth(truth_dir)
    observed_domains = {row["domain"] for row in resolutions}
    seeds = choose_seeds(ground_truth["domain_labels"], observed_domains, benign_sample, random_seed)
    infra_index = index_actor_infra(resolutions, ground_truth)
    methods = available_methods(resolutions, infrastructure, domains, max_domain_count)

    conditions = {"no_filter": no_filter_labels(infrastructure),
                  "perfect_filter": perfect_filter_labels(ground_truth)}
    if labels_path is not None:
        conditions["real_filter"] = read_json(labels_path)

    rows = []
    unique_true_positives = {}
    for condition, labels in conditions.items():
        print(f"Running {len(methods)} method(s) for {len(seeds)} seeds: {condition}")
        contract_results = []
        unique_counts = {name: 0 for name, _ in methods}
        for seed, group in seeds:
            results_by_method = {name: function(seed, labels) for name, function in methods}
            rankings = {name: rank_candidates(results) for name, results in results_by_method.items()}
            all_results = [result for results in results_by_method.values() for result in results]
            rankings["combined_rrf"] = fuse_reciprocal_rank(list(rankings.values()))
            rankings["combined_max"] = rank_candidates(all_results)
            contract_results.extend(all_results)

            if group in ("benign", "crimeware"):
                for method, ranking in rankings.items():
                    rows.append({"condition": condition, "method": method, "seed": seed,
                                 "seed_group": group, **non_actor_seed_metrics(ranking, ground_truth)})
                continue

            truth = ground_truth["actors"][group]
            positives = (set(truth["domains"]) - {seed}) & observed_domains
            for method, ranking in rankings.items():
                row = {"condition": condition, "method": method, "seed": seed, "seed_group": group,
                       **actor_seed_metrics(ranking, group, seed, ground_truth, observed_domains, infra_index)}
                if method in SHARED_INFRA_METHODS:
                    row["evidence_correct_share"] = evidence_correct_share(
                        results_by_method[method], positives, truth)
                rows.append(row)
            # True positives in a method's top 25 that no other method has in its top 25.
            top_hits = {name: set(rankings[name][:25]) & positives for name, _ in methods}
            for name, hits in top_hits.items():
                others = set().union(*(other for other_name, other in top_hits.items() if other_name != name))
                unique_counts[name] += len(hits - others)
        unique_true_positives[condition] = unique_counts
        write_jsonl(Path(output_dir) / condition / "pivot_results.jsonl", contract_results)

    summary = summarize(rows)
    write_jsonl(Path(output_dir) / "per_seed.jsonl", rows)
    write_json(Path(output_dir) / "summary.json", {
        "config": {"data_dir": str(data_dir), "truth_dir": str(truth_dir),
                   "labels": str(labels_path) if labels_path else None,
                   "max_domain_count": max_domain_count, "benign_sample": benign_sample,
                   "random_seed": random_seed, "methods": [name for name, _ in methods],
                   "conditions": list(conditions), "top_k": list(TOP_K), "rrf_k": RRF_K,
                   "n_seeds": {group: sum(1 for _, g in seeds if g == group)
                               for group in sorted({g for _, g in seeds})}},
        "unique_true_positives_top_25": unique_true_positives,
        "results": summary,
    })
    print_summary(summary, unique_true_positives)
    print(f"\nWrote per-seed metrics, summary, and pivot results to {output_dir}")
    return summary


def main():
    """Parse the CLI options and run the benchmark."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/seed-data_no-ground-truth"),
                        help="observations the pivots run on")
    parser.add_argument("--truth-dir", type=Path, default=Path("data/seed-data_with-ground-truth"),
                        help="directory holding ground_truth.json (read by evaluation only)")
    parser.add_argument("--labels", type=Path, help="real filter output; adds the real_filter condition")
    parser.add_argument("--max-domain-count", type=int, default=10, help="NS/MX rarity threshold")
    parser.add_argument("--benign-sample", type=int, default=100, help="number of benign seeds")
    parser.add_argument("--random-seed", type=int, default=6262, help="seed for the benign sample")
    parser.add_argument("--output-dir", type=Path, default=Path("output/eval"))
    args = parser.parse_args()
    try:
        evaluate(args.data_dir, args.truth_dir, args.output_dir, args.labels,
                 args.max_domain_count, args.benign_sample, args.random_seed)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
