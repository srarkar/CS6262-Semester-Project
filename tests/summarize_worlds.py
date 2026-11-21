"""Check independent-world aggregation and guard against changed control methods."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from compare_runs import make_run, refresh_checksums
from evaluation.summarize_worlds import summarize_worlds
from load_data import iter_jsonl, read_json, write_json, write_jsonl


class WorldSummaryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        # Controlled worlds have opposite changes, so the summary must retain
        # the regression as well as the improvement rather than selecting one.
        for world, after_ap in ((1, 0.6), (2, 0.3)):
            data = self.root / str(world) / "data"
            write_json(data / "manifest.json", {"seed": world})
            for phase, ap in (("before", 0.4), ("after", after_ap)):
                run = self.root / str(world) / phase
                make_run(run, ap)
                summary = read_json(run / "summary.json")
                summary["config"].update(data_dir=str(data), truth_dir=str(data))
                summary["config"]["methods"] = ["temporal_behavior", "fingerprint_match"]
                for condition in summary["results"].values():
                    condition["temporal_behavior"] = deepcopy(condition["fingerprint_match"])
                    for metrics in condition["fingerprint_match"].values():
                        if "average_precision" in metrics:
                            value = metrics["average_precision"]
                            metrics["average_precision"] = ({"mean": 0.4, "median": 0.4}
                                                            if isinstance(value, dict) else 0.4)
                write_json(run / "summary.json", summary)
                rows = list(iter_jsonl(run / "per_seed.jsonl"))
                for row in rows:
                    if row["method"] == "fingerprint_match":
                        row["method"] = "temporal_behavior"
                controls = []
                for row in rows:
                    if row["method"] == "temporal_behavior":
                        control = {**row, "method": "fingerprint_match"}
                        if "average_precision" in control:
                            control["average_precision"] = 0.4
                        controls.append(control)
                # Keep an unchanged method in each pair so the guard is tested
                # against metric changes as well as source-file changes.
                rows.extend(controls)
                write_jsonl(run / "per_seed.jsonl", rows)
                manifest = read_json(run / "run_manifest.json")
                manifest["evaluation_config"] = summary["config"]
                manifest["source_sha256"].update({"pivot/common.py": "common", "pivot/fingerprint_match.py": "fp",
                    "pivot/temporal_behavior.py": phase})
                write_json(run / "run_manifest.json", manifest)
                refresh_checksums(run)

    def test_worlds_have_equal_weight_and_keep_both_directions(self):
        rows, summary = summarize_worlds(self.root, [1, 2])
        value = next(row for row in summary if row["seed_group"] == "overall"
                     and row["method"] == "temporal_behavior" and row["metric"] == "average_precision")
        self.assertEqual(value["n_worlds"], 2)
        self.assertAlmostEqual(value["delta_mean"], 0.05)
        self.assertAlmostEqual(value["delta_min"], -0.1)
        self.assertAlmostEqual(value["delta_max"], 0.2)
        undefined = [row for row in summary if row["metric"] == "precision"]
        self.assertTrue(undefined)
        self.assertTrue(all(row["n_defined"] == 0 and row["delta_mean"] is None for row in undefined))
        self.assertEqual({row["world"] for row in rows}, {1, 2})

    def test_duplicate_worlds_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "distinct validation worlds"):
            summarize_worlds(self.root, [1, 1])

    def test_wrong_world_identity_is_rejected(self):
        write_json(self.root / "1/data/manifest.json", {"seed": 999})
        with self.assertRaisesRegex(ValueError, "different simulation seed"):
            summarize_worlds(self.root, [1, 2])

    def test_changed_control_code_is_rejected(self):
        for phase in ("before", "after"):
            path = self.root / "2" / phase / "run_manifest.json"
            manifest = read_json(path)
            manifest["source_sha256"]["pivot/common.py"] = "changed"
            write_json(path, manifest)
        with self.assertRaisesRegex(ValueError, "different implementations"):
            summarize_worlds(self.root, [1, 2])

    def test_changed_control_metrics_are_rejected(self):
        run = self.root / "1/after"
        original = list(iter_jsonl(run / "per_seed.jsonl"))
        # Undefined-to-defined changes have no numeric delta, but still mean
        # the supposedly unchanged control produced different measurements.
        for field, value in (("average_precision", 0.9), ("precision", 0.3)):
            with self.subTest(field=field):
                rows = deepcopy(original)
                for row in rows:
                    if row["method"] == "fingerprint_match" and field in row:
                        row[field] = value
                write_jsonl(run / "per_seed.jsonl", rows)
                refresh_checksums(run)
                with self.assertRaisesRegex(ValueError, "unchanged-method metrics differ"):
                    summarize_worlds(self.root, [1, 2])


if __name__ == "__main__":
    unittest.main()
