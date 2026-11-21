"""Paired-run comparisons must reject confounds and preserve unfavorable deltas."""

import contextlib
import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evaluation.compare_runs import compare_runs
from evaluation.run_experiment import run_experiment
from load_data import iter_jsonl, read_json, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[1]


def make_run(directory, average_precision, false_leads=1, limit=10):
    """Write a tiny, complete benchmark with one actor seed and one benign seed."""
    methods = ("fingerprint_match", "combined_rrf", "combined_max")
    config = {"methods": ["fingerprint_match"], "conditions": ["no_filter"],
              "n_seeds": {"A": 1, "benign": 1}, "max_domain_count": limit, "random_seed": 6262}
    results = {"no_filter": {}}
    rows = []
    for method in methods:
        overall = {"average_precision": average_precision, "precision_at_10": 0.1,
                   "recall_at_25": 0.5, "n_results": 5, "precision": None}
        actor = {key: {"mean": value, "median": value} if value is not None else None
                 for key, value in overall.items()}
        benign = {"actor_domains_in_top_25": {"mean": false_leads, "median": false_leads},
                  "n_results": {"mean": 10, "median": 10}}
        results["no_filter"][method] = {"overall": overall, "A": {"n_seeds": 1, **actor},
                                       "benign": {"n_seeds": 1, **benign}}
        rows.extend([
            {"condition": "no_filter", "method": method, "seed": "actor.example", "seed_group": "A", **overall},
            {"condition": "no_filter", "method": method, "seed": "benign.example", "seed_group": "benign",
             "actor_domains_in_top_25": false_leads, "n_results": 10}])
    write_json(directory / "summary.json", {"config": config, "results": results})
    write_jsonl(directory / "per_seed.jsonl", rows)
    write_json(directory / "run_manifest.json", {
        "evaluation_config": config, "ground_truth_sha256": "a" * 64,
        "data_sha256": {"observations": "b" * 64},
        "source_sha256": {"load_data.py": "loader", "evaluation/evaluate.py": "evaluator"}})
    refresh_checksums(directory)


def refresh_checksums(directory):
    """Keep intentionally changed fixture metrics consistent with their manifest."""
    path = directory / "run_manifest.json"
    manifest = read_json(path)
    manifest["artifact_sha256"] = {}
    for name in ("summary.json", "per_seed.jsonl"):
        manifest["artifact_sha256"][name] = hashlib.sha256((directory / name).read_bytes()).hexdigest()
    write_json(path, manifest)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.before = Path(directory.name) / "before"
        self.after = Path(directory.name) / "after"
        make_run(self.before, 0.4)
        make_run(self.after, 0.6, false_leads=2)

    def test_aggregate_and_seed_deltas_include_improvements_and_regressions(self):
        aggregates, paired = compare_runs(self.before, self.after)
        ap = next(row for row in aggregates if row["method"] == "fingerprint_match"
                  and row["seed_group"] == "overall" and row["metric"] == "average_precision")
        self.assertAlmostEqual(ap["delta"], 0.2)
        false_leads = next(row for row in paired if row["method"] == "fingerprint_match"
                           and row["seed_group"] == "benign" and row["metric"] == "actor_domains_in_top_25")
        self.assertEqual(false_leads["delta"], 1)
        undefined = [row for row in paired if row["metric"] == "precision"]
        self.assertTrue(undefined)
        self.assertTrue(all(row["delta"] is None for row in undefined))

    def test_configuration_mismatch_is_rejected(self):
        make_run(self.after, 0.6, limit=11)
        with self.assertRaisesRegex(ValueError, "configurations differ"):
            compare_runs(self.before, self.after)

    def test_changed_data_or_answer_key_is_rejected(self):
        path = self.after / "run_manifest.json"
        original = read_json(path)
        for field, value in (("data_sha256", {"observations": "changed"}),
                             ("ground_truth_sha256", "changed")):
            with self.subTest(field=field):
                write_json(path, {**original, field: value})
                with self.assertRaisesRegex(ValueError, field):
                    compare_runs(self.before, self.after)

    def test_changed_evaluation_source_is_rejected(self):
        path = self.after / "run_manifest.json"
        manifest = read_json(path)
        manifest["source_sha256"]["evaluation/evaluate.py"] = "changed"
        write_json(path, manifest)
        with self.assertRaisesRegex(ValueError, "Evaluation source differs"):
            compare_runs(self.before, self.after)

    def test_same_filter_path_with_changed_labels_is_rejected(self):
        for directory, digest in ((self.before, "original"), (self.after, "changed")):
            summary = read_json(directory / "summary.json")
            summary["config"]["labels"] = "output/infra_labels.json"
            write_json(directory / "summary.json", summary)
            manifest = read_json(directory / "run_manifest.json")
            manifest.update(evaluation_config=summary["config"], labels_sha256=digest)
            write_json(directory / "run_manifest.json", manifest)
            refresh_checksums(directory)
        with self.assertRaisesRegex(ValueError, "Filter-label checksums"):
            compare_runs(self.before, self.after)

    def test_equal_seed_counts_with_different_identities_are_rejected(self):
        rows = list(iter_jsonl(self.after / "per_seed.jsonl"))
        rows[0]["seed"] = "different.example"
        write_jsonl(self.after / "per_seed.jsonl", rows)
        refresh_checksums(self.after)
        with self.assertRaisesRegex(ValueError, "Per-seed keys differ"):
            compare_runs(self.before, self.after)

    def test_duplicate_seed_rows_are_rejected(self):
        rows = list(iter_jsonl(self.after / "per_seed.jsonl"))
        write_jsonl(self.after / "per_seed.jsonl", rows + [rows[0]])
        refresh_checksums(self.after)
        with self.assertRaisesRegex(ValueError, "duplicate per-seed"):
            compare_runs(self.before, self.after)

    def test_incomplete_runs_are_rejected(self):
        for directory in (self.before, self.after):
            rows = list(iter_jsonl(directory / "per_seed.jsonl"))
            write_jsonl(directory / "per_seed.jsonl", rows[1:])
            refresh_checksums(directory)
        with self.assertRaisesRegex(ValueError, "incomplete or unexpected"):
            compare_runs(self.before, self.after)

    def test_changed_metrics_without_updated_provenance_are_rejected(self):
        with (self.after / "per_seed.jsonl").open("a", encoding="utf-8") as stream:
            stream.write("\n")
        with self.assertRaisesRegex(ValueError, "mismatched checksum"):
            compare_runs(self.before, self.after)

    def test_cli_prevents_overwriting_an_input_run(self):
        result = subprocess.run(
            [sys.executable, "-m", "evaluation.compare_runs", "--before", str(self.before),
             "--after", str(self.after), "--output-dir", str(self.before / "figures")],
            cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("outside the preserved input", result.stderr)
        self.assertFalse((self.before / "figures").exists())

    def test_experiment_runner_creates_a_reproducible_completed_run(self):
        data = self.before.parent / "data"
        output = self.before.parent / "experiment"
        rows = [{"domain": domain, "rrtype": "A", "value": "192.0.2.1", "first_seen": "2025-01-01",
                 "last_seen": "2025-01-10", "source": "forward"} for domain in ("a.example", "b.example")]
        write_jsonl(data / "resolutions.jsonl", rows)
        write_json(data / "infra.json", {"192.0.2.1": {"type": "ipv4", "asn": 1, "domain_count": 2}})
        write_json(data / "domains.json", {row["domain"]: {"registered": "2024-01-01", "registrar": "R"}
                                           for row in rows})
        write_json(data / "manifest.json", {"format_version": "0.1"})
        write_json(data / "ground_truth.json", {
            "actors": {"A": {"domains": [row["domain"] for row in rows], "ips": ["192.0.2.1"],
                              "ns_hosts": [], "mx_hosts": [], "cdn_fronted_domains": []}},
            "domain_labels": {row["domain"]: "actor:A" for row in rows},
            "infra_labels": {"192.0.2.1": "actor"},
        })
        with contextlib.redirect_stdout(io.StringIO()):
            run_experiment(output, data, data, benign_sample=0)
        self.assertTrue((output / "source.zip").is_file())
        aggregates, paired = compare_runs(output, output)
        self.assertTrue(aggregates and paired)
        self.assertTrue(all(row["delta"] in (0, None) for row in aggregates + paired))
        with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
            run_experiment(output, data, data)


if __name__ == "__main__":
    unittest.main()
