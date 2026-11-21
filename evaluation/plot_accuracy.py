"""
Create accuracy-comparison graphs from the evaluation pipeline's outputs.

Run from the repository root after `python3 -m evaluation.evaluate`:

    python3 -m evaluation.plot_accuracy

Optional paths:

    python3 -m evaluation.plot_accuracy \
        --eval-dir output/eval \
        --output-dir outputs/accuracy

Requires pandas and matplotlib:
    python3 -m pip install pandas matplotlib

This script does not rerun pivots or read ground truth. It visualizes the
metrics already computed by evaluation/evaluate.py.
"""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Save figures without requiring a desktop display.
import matplotlib.pyplot as plt
import pandas as pd


RANKING_METRICS = [
    ("average_precision", "Average precision"),
    ("precision_at_5", "Precision@5"),
    ("precision_at_10", "Precision@10"),
    ("precision_at_25", "Precision@25"),
]

RECALL_METRICS = [
    ("recall_at_5", "Recall@5"),
    ("recall_at_10", "Recall@10"),
    ("recall_at_25", "Recall@25"),
    ("recall_observed", "Recall (all observed)"),
    ("recall_reachable", "Recall (one-hop reachable)"),
]


def load_inputs(eval_dir):
    """Load and validate the summary and per-seed metrics produced by evaluate.py."""
    summary_path = eval_dir / "summary.json"
    per_seed_path = eval_dir / "per_seed.jsonl"

    if not summary_path.is_file():
        raise FileNotFoundError(
            f"Missing {summary_path}. Run `python3 -m evaluation.evaluate` first."
        )
    if not per_seed_path.is_file():
        raise FileNotFoundError(
            f"Missing {per_seed_path}. Run `python3 -m evaluation.evaluate` first."
        )

    with summary_path.open(encoding="utf-8") as handle:
        summary = json.load(handle)

    per_seed = pd.read_json(per_seed_path, lines=True)
    if per_seed.empty:
        raise ValueError(f"{per_seed_path} contains no per-seed metrics.")

    if "results" not in summary or "config" not in summary:
        raise ValueError(f"{summary_path} does not have the expected evaluation schema.")

    return summary, per_seed


def overall_metric_frame(summary, metric_names):
    """Build a table from the evaluator's actor-balanced `overall` aggregates."""
    records = []
    for condition, methods in summary["results"].items():
        for method, groups in methods.items():
            overall = groups.get("overall")
            if not isinstance(overall, dict):
                continue
            row = {"condition": condition, "method": method}
            for metric, _ in metric_names:
                row[metric] = overall.get(metric)
            records.append(row)
    return pd.DataFrame(records)


def plot_metric_groups(frame, metrics, output_path, title, ylabel):
    """Plot several comparable metrics, with one panel per filter condition."""
    available = [(key, label) for key, label in metrics
                 if key in frame.columns and frame[key].notna().any()]
    if frame.empty or not available:
        return False

    conditions = list(dict.fromkeys(frame["condition"].tolist()))
    fig, axes = plt.subplots(
        1, len(conditions), figsize=(max(8, 5.2 * len(conditions)), 5),
        squeeze=False
    )
    methods = list(dict.fromkeys(frame["method"].tolist()))

    for ax, condition in zip(axes[0], conditions):
        subset = frame[frame["condition"] == condition].set_index("method")
        columns = [key for key, _ in available]
        labels = [label for _, label in available]
        plot_data = subset.reindex(methods)[columns]
        plot_data.index = methods
        plot_data.plot(kind="bar", ax=ax, width=0.82)
        ax.set_title(condition.replace("_", " ").title())
        ax.set_xlabel("")
        ax.set_ylabel(ylabel)
        ax.set_ylim(0, 1.05)
        ax.tick_params(axis="x", labelrotation=35)
        ax.grid(axis="y", alpha=0.25)
        ax.legend(labels, title="Metric", fontsize=8)

    fig.suptitle(title, fontsize=14)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return True


def plot_benign_false_leads(per_seed, output_path):
    """Show actor-domain false leads among benign and crimeware seed top-25 lists."""
    required = {"condition", "method", "seed_group", "actor_domains_in_top_25"}
    if not required.issubset(per_seed.columns):
        return False

    subset = per_seed[per_seed["seed_group"].isin(["benign", "crimeware"])]
    if subset.empty:
        return False

    grouped = (
        subset.groupby(["condition", "method", "seed_group"], as_index=False)
        ["actor_domains_in_top_25"].mean()
    )
    conditions = list(dict.fromkeys(grouped["condition"].tolist()))
    fig, axes = plt.subplots(
        1, len(conditions), figsize=(max(8, 5.2 * len(conditions)), 5),
        squeeze=False
    )

    for ax, condition in zip(axes[0], conditions):
        data = grouped[grouped["condition"] == condition]
        pivot = data.pivot(index="method", columns="seed_group",
                           values="actor_domains_in_top_25").fillna(0)
        pivot.plot(kind="bar", ax=ax, width=0.8)
        ax.set_title(condition.replace("_", " ").title())
        ax.set_xlabel("")
        ax.set_ylabel("Mean actor domains returned in top 25")
        ax.tick_params(axis="x", labelrotation=35)
        ax.grid(axis="y", alpha=0.25)
        ax.legend(title="Seed type")

    fig.suptitle("False leads from benign and crimeware seeds", fontsize=14)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return True


def plot_unique_true_positives(summary, output_path):
    """Plot unique true positives in each method's top 25, by filter condition."""
    values = summary.get("unique_true_positives_top_25", {})
    records = [
        {"condition": condition, "method": method, "unique_tp_top_25": count}
        for condition, methods in values.items()
        for method, count in methods.items()
    ]
    if not records:
        return False

    frame = pd.DataFrame(records)
    conditions = list(dict.fromkeys(frame["condition"].tolist()))
    fig, axes = plt.subplots(
        1, len(conditions), figsize=(max(8, 5.2 * len(conditions)), 5),
        squeeze=False
    )
    for ax, condition in zip(axes[0], conditions):
        data = frame[frame["condition"] == condition].set_index("method")
        data["unique_tp_top_25"].plot(kind="bar", ax=ax, legend=False)
        ax.set_title(condition.replace("_", " ").title())
        ax.set_xlabel("")
        ax.set_ylabel("Unique true positives across actor seeds")
        ax.tick_params(axis="x", labelrotation=35)
        ax.grid(axis="y", alpha=0.25)

    fig.suptitle("Unique discoveries in each method's top 25", fontsize=14)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return True


def write_comparison_csv(summary, output_path):
    """Export the actor-balanced headline metrics as a convenient comparison table."""
    metrics = RANKING_METRICS + RECALL_METRICS + [
        ("n_results", "Mean result count"),
        ("other_malicious_in_top_25", "Other malicious domains in top 25"),
    ]
    frame = overall_metric_frame(summary, metrics)
    if not frame.empty:
        frame.to_csv(output_path, index=False)
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--eval-dir", type=Path, default=Path("output/eval"),
        help="directory produced by evaluation.evaluate (default: output/eval)"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("outputs/accuracy"),
        help="directory for generated graphs and CSV (default: outputs/accuracy)"
    )
    args = parser.parse_args()

    summary, per_seed = load_inputs(args.eval_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    ranking_frame = overall_metric_frame(summary, RANKING_METRICS)
    recall_frame = overall_metric_frame(summary, RECALL_METRICS)

    generated = []
    if plot_metric_groups(
        ranking_frame, RANKING_METRICS,
        args.output_dir / "ranking_quality.png",
        "Pivot method ranking quality", "Score"
    ):
        generated.append("ranking_quality.png")

    if plot_metric_groups(
        recall_frame, RECALL_METRICS,
        args.output_dir / "recall_comparison.png",
        "Pivot method recall", "Recall"
    ):
        generated.append("recall_comparison.png")

    if plot_benign_false_leads(per_seed, args.output_dir / "false_leads.png"):
        generated.append("false_leads.png")

    if plot_unique_true_positives(summary, args.output_dir / "unique_true_positives.png"):
        generated.append("unique_true_positives.png")

    if write_comparison_csv(summary, args.output_dir / "method_comparison.csv"):
        generated.append("method_comparison.csv")

    if not generated:
        raise ValueError("No plots were generated; check that the evaluation outputs contain metrics.")

    print(f"Generated {len(generated)} comparison file(s) in {args.output_dir}:")
    for name in generated:
        print(f"  {name}")
    print("\nNote: headline metric bars use the evaluator's actor-balanced overall means.")


if __name__ == "__main__":
    main()
