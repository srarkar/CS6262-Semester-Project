"""Validate paired benchmark runs, then export before/after metrics and graphs."""

import argparse
from collections import Counter
import csv
import hashlib
from pathlib import Path

from load_data import iter_jsonl, read_json, write_json


SEED_FIELDS = ("condition", "method", "seed", "seed_group")


def load_run(directory):
    """Read metrics only; require provenance and complete, unique seed rows."""
    manifest_path = directory / "run_manifest.json"
    if not manifest_path.exists():
        manifest_path = directory / "baseline_manifest.json"
    manifest = read_json(manifest_path)
    for name in ("summary.json", "per_seed.jsonl"):
        expected = manifest.get("artifact_sha256", {}).get(name)
        with (directory / name).open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if not expected or actual != expected:
            raise ValueError(f"{directory}: missing or mismatched checksum for {name}")
    summary = read_json(directory / "summary.json")
    config = summary["config"]
    if manifest.get("evaluation_config") != config:
        raise ValueError(f"{directory}: manifest and evaluation configuration differ")
    rows = {}
    for row in iter_jsonl(directory / "per_seed.jsonl"):
        key = tuple(row[field] for field in SEED_FIELDS)
        if key in rows:
            raise ValueError(f"{directory}: duplicate per-seed key {key}")
        rows[key] = row
    counts = Counter((key[0], key[1], key[3]) for key in rows)
    methods = set(config["methods"]) | {"combined_rrf", "combined_max"}
    expected = {(condition, method, group): count
                for condition in config["conditions"] for method in methods
                for group, count in config["n_seeds"].items()}
    if dict(counts) != expected:
        raise ValueError(f"{directory}: incomplete or unexpected seed coverage")
    return summary, rows, manifest


def compare_runs(before_dir, after_dir):
    """Reject confounded runs and return aggregate and paired-seed deltas."""
    before, before_rows, before_manifest = load_run(Path(before_dir))
    after, after_rows, after_manifest = load_run(Path(after_dir))
    if before["config"] != after["config"]:
        raise ValueError("Evaluation configurations differ; paired comparison requires identical settings")
    for field in ("data_sha256", "ground_truth_sha256"):
        if not before_manifest.get(field) or before_manifest[field] != after_manifest.get(field):
            raise ValueError(f"Run provenance differs or is missing: {field}")
    if before["config"].get("labels") and (not before_manifest.get("labels_sha256")
            or before_manifest["labels_sha256"] != after_manifest.get("labels_sha256")):
        raise ValueError("Filter-label checksums differ or are missing")
    for filename in ("load_data.py", "evaluation/evaluate.py"):
        digest = before_manifest.get("source_sha256", {}).get(filename)
        if not digest or digest != after_manifest.get("source_sha256", {}).get(filename):
            raise ValueError(f"Evaluation source differs or is missing: {filename}")
    if before_rows.keys() != after_rows.keys():
        raise ValueError("Per-seed keys differ; the benchmark populations are not paired")

    aggregates = []
    for condition, methods in before["results"].items():
        for method, groups in methods.items():
            for group, metrics in groups.items():
                other = after["results"][condition][method][group]
                if metrics.keys() != other.keys():
                    raise ValueError("Aggregate metric fields differ")
                for metric, value in metrics.items():
                    if metric == "n_seeds":
                        continue
                    left = value.get("mean") if isinstance(value, dict) else value
                    right = other[metric]
                    right = right.get("mean") if isinstance(right, dict) else right
                    aggregates.append({"condition": condition, "method": method, "seed_group": group,
                                       "metric": metric, "before": left, "after": right,
                                       "delta": right - left if left is not None and right is not None else None})
    paired = []
    for key, row in sorted(before_rows.items()):
        other = after_rows[key]
        if row.keys() != other.keys():
            raise ValueError("Per-seed metric fields differ")
        for metric, left in row.items():
            if metric in SEED_FIELDS:
                continue
            right = other[metric]
            paired.append({**dict(zip(SEED_FIELDS, key)), "metric": metric,
                           "before": left, "after": right,
                           "delta": right - left if left is not None and right is not None else None})
    return aggregates, paired


def write_csv(path, rows):
    """Keep undefined measurements empty rather than inventing zero values."""
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_comparison(rows, panels, output_path, title):
    """Use paired zero-based bars, separate filter conditions, and explicit values."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    conditions = sorted({row["condition"] for row in rows})
    methods = sorted({row["method"] for row in rows})
    values = {(row["condition"], row["method"], row["seed_group"], row["metric"]): row
              for row in rows}
    fig, axes = plt.subplots(len(conditions), len(panels), squeeze=False,
                             figsize=(7 * len(panels), 4.8 * len(conditions)), constrained_layout=True)
    for index, condition in enumerate(conditions):
        for column, (group, metric, label) in enumerate(panels):
            ax = axes[index][column]
            measurements = [values.get((condition, method, group, metric), {}) for method in methods]
            available = [(method, row) for method, row in zip(methods, measurements)
                         if row.get("before") is not None and row.get("after") is not None]
            if not available:
                ax.set_visible(False)
                continue
            names = [method for method, _ in available]
            for offset, phase, color in ((-0.19, "before", "#6b7280"), (0.19, "after", "#007f86")):
                bars = ax.bar([x + offset for x in range(len(names))],
                              [row[phase] for _, row in available], width=0.38, label=phase.title(), color=color)
                ax.bar_label(bars, fmt="%.3f" if metric != "n_results" else "%.1f", fontsize=7, padding=3)
            maximum = max(row[phase] for _, row in available for phase in ("before", "after"))
            ax.set_ylim(0, maximum * 1.25 if maximum else 1)
            ax.set_xticks(range(len(names)), names, rotation=35, ha="right")
            condition_label = "Perfect filter (oracle control)" if condition == "perfect_filter" else condition.replace("_", " ").title()
            ax.set_title(f"{condition_label} — {label}")
            ax.set_ylabel(label)
            ax.grid(axis="y", alpha=0.2)
            ax.legend()
    fig.suptitle(title)
    fig.savefig(output_path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def main():
    """Read two completed evaluation directories; never rerun or tune methods."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if any(args.output_dir.resolve().is_relative_to(path.resolve()) for path in (args.before, args.after)):
            raise ValueError("Comparison output must be outside the preserved input run directories")
        aggregates, paired = compare_runs(args.before, args.after)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_csv(args.output_dir / "metric_deltas.csv", aggregates)
        write_csv(args.output_dir / "per_seed_deltas.csv", paired)
        plot_comparison(aggregates, [("overall", "average_precision", "Average precision"),
                                    ("overall", "precision_at_10", "Precision@10"),
                                    ("overall", "recall_at_25", "Recall@25")],
                        args.output_dir / "ranking_before_after.png", "Before/after benchmark: ranking")
        plot_comparison(aggregates, [("benign", "actor_domains_in_top_25", "False leads: benign seeds"),
                                    ("crimeware", "actor_domains_in_top_25", "False leads: crimeware seeds")],
                        args.output_dir / "false_leads_before_after.png", "Mean actor domains in non-actor top-25 lists")
        plot_comparison(aggregates, [("overall", "n_results", "Mean candidates per actor seed")],
                        args.output_dir / "candidate_counts_before_after.png", "Candidate-list size")
        write_json(args.output_dir / "comparison.json", {
            "before": str(args.before), "after": str(args.after),
            "delta_definition": "after minus before; undefined values remain null/empty",
            "aggregate_rows": len(aggregates), "paired_metric_rows": len(paired),
        })
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(f"Validated paired runs; wrote CSV tables and three graphs to {args.output_dir}")


if __name__ == "__main__":
    main()
