"""Summarize fixed temporal before/after pairs across independent simulation worlds."""

import argparse
from collections import defaultdict
from pathlib import Path
from statistics import mean

from evaluation.compare_runs import compare_runs, load_run, write_csv
from load_data import read_json, write_json


KEY_FIELDS = ("condition", "method", "seed_group", "metric")


def summarize_worlds(root, worlds):
    """Check paired provenance and unchanged controls, then weight worlds equally."""
    if not worlds or len(set(worlds)) != len(worlds):
        raise ValueError("Specify distinct validation worlds")
    rows, reference_sources, reference_config, reference_keys = [], None, None, None
    for world in worlds:
        directory = Path(root) / str(world)
        before, _, before_manifest = load_run(directory / "before")
        after, _, after_manifest = load_run(directory / "after")
        aggregates, paired = compare_runs(directory / "before", directory / "after")
        config = before["config"]
        if read_json(Path(config["data_dir"]) / "manifest.json")["seed"] != world:
            raise ValueError(f"World {world}: dataset manifest has a different simulation seed")
        settings = {key: value for key, value in config.items()
                    if key not in ("data_dir", "truth_dir", "n_seeds")}
        # All worlds must measure the same two implementations. Supporting tools
        # may differ, but loader/evaluator/pivot code defines the measured change.
        sources = []
        for manifest in (before_manifest, after_manifest):
            sources.append({name: value for name, value in manifest["source_sha256"].items()
                            if name.startswith("pivot/") or name in ("load_data.py", "evaluation/evaluate.py")})
        if sources[0].keys() != sources[1].keys() or any(
                sources[0][name] != sources[1][name] for name in sources[0]
                if name != "pivot/temporal_behavior.py"):
            raise ValueError(f"World {world}: a control source changed")
        if any(row["before"] != row["after"] for row in paired
               if row["method"] in ("ip_coresidency", "ns_mx_reuse", "fingerprint_match")):
            raise ValueError(f"World {world}: unchanged-method metrics differ")
        keys = {tuple(row[key] for key in KEY_FIELDS) for row in aggregates}
        if reference_sources is None:
            reference_sources, reference_config, reference_keys = sources, settings, keys
        elif sources != reference_sources or settings != reference_config or keys != reference_keys:
            raise ValueError("Validation worlds use different implementations, settings, or metric groups")
        rows.extend({"world": world, **row} for row in aggregates)

    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in KEY_FIELDS)].append(row)
    summary = []
    for key, measurements in sorted(groups.items()):
        defined = [row for row in measurements if row["delta"] is not None]
        deltas = [row["delta"] for row in defined]
        summary.append({**dict(zip(KEY_FIELDS, key)), "n_worlds": len(measurements),
                        "n_defined": len(defined),
                        "before_mean": mean(row["before"] for row in defined) if defined else None,
                        "after_mean": mean(row["after"] for row in defined) if defined else None,
                        "delta_mean": mean(deltas) if deltas else None,
                        "delta_min": min(deltas) if deltas else None,
                        "delta_max": max(deltas) if deltas else None})
    return rows, summary


def plot_world_deltas(rows, path):
    """Show every world's ranking deltas; three worlds do not establish significance."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    conditions = sorted({row["condition"] for row in rows})
    worlds = sorted({row["world"] for row in rows})
    methods = ("temporal_behavior", "combined_rrf", "combined_max")
    metrics = (("average_precision", "Average precision"), ("precision_at_10", "Precision@10"),
               ("recall_at_25", "Recall@25"))
    values = {(row["world"], row["condition"], row["method"], row["metric"]): row["delta"]
              for row in rows if row["seed_group"] == "overall"}
    fig, axes = plt.subplots(len(conditions), 3, squeeze=False, figsize=(15, 4 * len(conditions)),
                             constrained_layout=True)
    for index, condition in enumerate(conditions):
        for column, (metric, label) in enumerate(metrics):
            ax = axes[index][column]
            for position, world in enumerate(worlds):
                ax.scatter([x + (position - (len(worlds) - 1) / 2) * 0.10 for x in range(len(methods))],
                           [values[world, condition, method, metric] for method in methods],
                           label=str(world), s=45)
            ax.axhline(0, color="black", linewidth=1)
            title = "Perfect filter (oracle control)" if condition == "perfect_filter" else condition.replace("_", " ").title()
            ax.set_title(f"{title}: {label}")
            ax.set_ylabel("After − before (higher is better)")
            ax.set_xticks(range(len(methods)), ["Temporal", "Combined RRF", "Combined max"])
            ax.grid(axis="y", alpha=0.2)
            ax.legend(title="Simulation seed", fontsize=8)
    fig.suptitle("Hosting-timeline refinement: individual validation worlds")
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def main():
    """Read completed world pairs without generating data or rerunning methods."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--worlds", type=int, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if any(args.output_dir.resolve().is_relative_to((args.runs_root / str(world) / phase).resolve())
               for world in args.worlds for phase in ("before", "after")):
            raise ValueError("Summary output must be outside the input run directories")
        rows, summary = summarize_worlds(args.runs_root, args.worlds)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_csv(args.output_dir / "world_metric_deltas.csv", rows)
        write_csv(args.output_dir / "replication_summary.csv", summary)
        plot_world_deltas(rows, args.output_dir / "replication_deltas.png")
        write_json(args.output_dir / "replication_summary.json", {
            "worlds": args.worlds, "aggregation": "Equal weight per world; delta = after minus before",
            "limitations": "Same actor profiles; simulation variability only; no significance claim",
            "results": summary})
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(f"Verified {len(args.worlds)} world pairs; wrote tables and a figure to {args.output_dir}")


if __name__ == "__main__":
    main()
