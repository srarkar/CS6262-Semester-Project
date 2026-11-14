
"""Controlled behavioral checks; no actor profiles or evaluation data are used."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from load_data import iter_jsonl, write_jsonl
from pivot.ip_coresidency import find_ip_coresidents


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IP = "192.0.2.1"


def observation(domain, first, last, source="forward", ip=IP, rrtype="A"):
    """Make an explicit, small DNS observation for a controlled case."""
    return {"domain": domain, "rrtype": rrtype, "value": ip,
            "first_seen": first, "last_seen": last, "source": source}


class CoresidencyTests(unittest.TestCase):
    def setUp(self):
        self.infrastructure = {IP: {"type": "ipv4", "domain_count": 2, "label": "unknown"}}
        self.labels = {"infra": {IP: {"label": "candidate", "confidence": 1.0,
                                      "reasons": ["controlled test eligibility"]}}, "domains": {}}

    def find(self, rows, seed="seed.example"):
        """Run each case with its controlled metadata and labels."""
        return find_ip_coresidents(seed, rows, self.infrastructure, self.labels)

    def test_inclusive_overlap_normalization_and_self_exclusion(self):
        rows = [observation("seed.example", "2025-06-12", "2025-12-31"),
                observation("peer.example", "2024-12-06", "2025-06-22"),
                observation("later.example", "2026-01-01", "2026-01-03"),
                observation("edge.example", "2025-12-31", "2026-01-02")]
        results = self.find(rows, seed=" Seed.Example. ")
        self.assertEqual([row["candidate"] for row in results], ["edge.example", "peer.example"])
        peer = results[1]
        self.assertEqual(peer["seed"], " Seed.Example. ")
        self.assertEqual(set(peer), {"seed", "candidate", "method", "evidence", "score"})
        self.assertEqual(peer["method"], "ip_coresidency")
        shared = peer["evidence"]["shared_ips"][0]
        self.assertEqual(shared["overlap_days"], 11)
        self.assertEqual(shared["domain_count"], 2)
        self.assertEqual(shared["overlap_intervals"], [
            {"first_seen": "2025-06-12", "last_seen": "2025-06-22", "days": 11}])
        self.assertEqual(peer["score"], 0.366667)
        self.assertEqual(results[0]["evidence"]["shared_ips"][0]["overlap_days"], 1)

    def test_duplicate_sources_union_days_and_preserve_source_dates(self):
        rows = [observation("seed.example", "2025-06-12", "2025-12-31"),
                observation("seed.example", "2025-06-14", "2025-12-29", "passive"),
                observation("peer.example", "2024-12-06", "2025-06-22"),
                observation("peer.example", "2024-12-21", "2025-06-23", "passive")]
        result = self.find(rows + rows)[0]
        self.assertEqual(self.find(rows), [result])
        shared = result["evidence"]["shared_ips"][0]
        self.assertEqual(shared["overlap_days"], 12)
        self.assertEqual(shared["overlap_intervals"], [
            {"first_seen": "2025-06-12", "last_seen": "2025-06-23", "days": 12}])
        self.assertEqual(shared["candidate_observations"], [
            {"first_seen": "2024-12-06", "last_seen": "2025-06-22", "source": "forward"},
            {"first_seen": "2024-12-21", "last_seen": "2025-06-23", "source": "passive"}])
        self.assertEqual(shared["seed_observations"][1]["first_seen"], "2025-06-14")
        self.assertEqual(result["score"], 0.4)

    def test_disjoint_intervals_do_not_bridge_gaps(self):
        rows = [observation("seed.example", "2025-01-01", "2025-01-03"),
                observation("seed.example", "2025-01-10", "2025-01-12"),
                observation("peer.example", "2025-01-02", "2025-01-11"),
                observation("gap.example", "2025-01-04", "2025-01-09")]
        results = self.find(rows)
        self.assertEqual([result["candidate"] for result in results], ["peer.example"])
        shared = results[0]["evidence"]["shared_ips"][0]
        self.assertEqual(shared["overlap_days"], 4)
        self.assertEqual(shared["overlap_intervals"], [
            {"first_seen": "2025-01-02", "last_seen": "2025-01-03", "days": 2},
            {"first_seen": "2025-01-10", "last_seen": "2025-01-11", "days": 2}])

    def test_only_explicit_candidate_labels_allow_pivots(self):
        rows = [observation("seed.example", "2025-01-01", "2025-01-10"),
                observation("peer.example", "2025-01-01", "2025-01-10")]
        for label in ("parking", "sinkhole", "cdn", "shared_hosting"):
            with self.subTest(label=label):
                self.labels["infra"][IP]["label"] = label
                self.assertEqual(self.find(rows), [])
        self.labels["infra"] = {}
        self.assertEqual(self.find(rows), [])  # Raw unknown never grants eligibility.

    def test_ipv6_equivalent_spellings_match_and_other_ips_do_not(self):
        ipv6 = "2001:db8::1"
        self.infrastructure[ipv6] = {"type": "ipv6", "domain_count": 2}
        self.labels["infra"][ipv6] = self.labels["infra"][IP].copy()
        rows = [observation("seed.example", "2025-01-01", "2025-01-10", ip=ipv6, rrtype="AAAA"),
                observation("Peer.Example.", "2025-01-08", "2025-01-12",
                            ip="2001:0db8:0000:0000:0000:0000:0000:0001", rrtype="AAAA"),
                observation("neighbor.example", "2025-01-01", "2025-01-10",
                            ip="2001:db8::2", rrtype="AAAA")]
        results = self.find(rows)
        self.assertEqual([result["candidate"] for result in results], ["peer.example"])
        shared = results[0]["evidence"]["shared_ips"][0]
        self.assertEqual(shared["ip"], ipv6)
        self.assertEqual(shared["overlap_days"], 3)

    def test_same_address_block_and_asn_are_not_exact_ip_sharing(self):
        other_ip = "192.0.2.2"
        self.infrastructure[IP]["asn"] = 64500
        self.infrastructure[other_ip] = {"type": "ipv4", "asn": 64500, "domain_count": 1}
        self.labels["infra"][other_ip] = self.labels["infra"][IP].copy()
        rows = [observation("seed.example", "2025-01-01", "2025-01-10"),
                observation("peer.example", "2025-01-01", "2025-01-10", ip=other_ip)]
        self.assertEqual(self.find(rows), [])

    def test_aggregate_multiple_ips_deterministically_without_recursive_expansion(self):
        second_ip = "192.0.2.2"
        self.infrastructure[second_ip] = {"type": "ipv4", "domain_count": 3}
        self.labels["infra"][second_ip] = self.labels["infra"][IP].copy()
        rows = [observation("seed.example", "2025-01-01", "2025-01-10"),
                observation("peer.example", "2025-01-05", "2025-01-15"),
                observation("z.example", "2025-01-01", "2025-01-02"),
                observation("seed.example", "2025-01-01", "2025-01-10", ip=second_ip),
                observation("peer.example", "2025-01-01", "2025-03-01", ip=second_ip),
                observation("second-hop.example", "2025-02-01", "2025-02-10", ip=second_ip)]
        results = self.find(rows)
        self.assertEqual(results, self.find(list(reversed(rows))))
        self.assertEqual([result["candidate"] for result in results], ["peer.example", "z.example"])
        self.assertEqual([item["ip"] for item in results[0]["evidence"]["shared_ips"]], [IP, second_ip])
        self.assertEqual(results[0]["score"], 0.333333)  # Strongest IP, not 6 + 10 days.
        rows.extend([observation("seed.example", "2025-02-01", "2025-03-31"),
                     observation("peer.example", "2025-02-01", "2025-03-31")])
        self.assertEqual(self.find(rows)[0]["score"], 1.0)

    def test_missing_metadata_and_domain_count(self):
        rows = [observation("seed.example", "2025-01-01", "2025-01-10"),
                observation("peer.example", "2025-01-01", "2025-01-10")]
        del self.infrastructure[IP]["domain_count"]
        self.assertIsNone(self.find(rows)[0]["evidence"]["shared_ips"][0]["domain_count"])
        self.infrastructure.clear()
        self.assertEqual(self.find(rows), [])

    def test_unknown_seeds_empty_data_and_non_address_observations(self):
        rows = [observation("peer.example", "2025-01-01", "2025-01-10")]
        self.assertEqual(self.find(rows), [])
        self.assertEqual(self.find([]), [])
        rows.append(observation("seed.example", "2025-01-01", "2025-01-10", rrtype="NS"))
        self.assertEqual(self.find(rows), [])
        rows.append(observation("seed.example", "2025-01-01", "2025-01-10"))
        self.assertEqual(self.find(rows, seed="metadata-only.example"), [])

    def test_invalid_seed_and_eligible_observation_errors_are_useful(self):
        for seed in ("", "192.0.2.1", "2001:db8::1"):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                self.find([], seed=seed)
        valid = observation("seed.example", "2025-01-01", "2025-01-10")
        for field, value in (("first_seen", "bad-date"), ("last_seen", "2024-01-01"),
                             ("source", "other"), ("domain", None), ("value", "bad-ip")):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "resolution 1"):
                self.find([dict(valid, **{field: value})])
        del valid["source"]
        with self.assertRaisesRegex(ValueError, "source"):
            self.find([valid])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.labels_path = self.directory / "labels.json"
        self.output = self.directory / "output" / "results.jsonl"
        self.labels = {"infra": {IP: {"label": "candidate", "confidence": 1.0,
                                      "reasons": ["controlled test eligibility"]}}, "domains": {}}
        self.labels_path.write_text(json.dumps(self.labels), encoding="utf-8")
        (self.directory / "infra.json").write_text(json.dumps(
            {IP: {"type": "ipv4", "domain_count": 2, "label": "unknown"}}), encoding="utf-8")
        write_jsonl(self.directory / "resolutions.jsonl", [
            observation("seed.example", "2025-01-01", "2025-01-10"),
            observation("peer.example", "2025-01-05", "2025-01-15")])

    def run_cli(self, seed="seed.example", labels_path=None):
        """Exercise the documented module entry point with isolated files."""
        return subprocess.run(
            [sys.executable, "-m", "pivot.ip_coresidency", seed,
             "--data-dir", str(self.directory), "--labels", str(labels_path or self.labels_path),
             "--output", str(self.output)], cwd=PROJECT_ROOT,
            text=True, capture_output=True, check=False)

    def test_success_and_empty_results_replace_output(self):
        result = self.run_cli(seed="Seed.Example.")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = list(iter_jsonl(self.output))
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["seed"], "Seed.Example.")
        self.assertEqual(output[0]["candidate"], "peer.example")
        self.assertEqual(output[0]["score"], 0.2)
        original_bytes = self.output.read_bytes()
        self.assertEqual(self.run_cli(seed="Seed.Example.").returncode, 0)
        self.assertEqual(self.output.read_bytes(), original_bytes)
        self.assertEqual(self.run_cli(seed="unknown.example").returncode, 0)
        self.assertEqual(self.output.read_bytes(), b"")

    def test_missing_or_malformed_labels_fail_without_writing_output(self):
        result = self.run_cli(labels_path=self.directory / "missing.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing.json", result.stderr)
        for contents, message in (("{", "invalid JSON"), ("[]", "'infra' object"),
                                  ('{"infra": {}, "domains": []}', "'domains' object")):
            with self.subTest(contents=contents):
                self.labels_path.write_text(contents, encoding="utf-8")
                result = self.run_cli()
                self.assertEqual(result.returncode, 2)
                self.assertIn(message, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(self.output.exists())

    def test_invalid_label_fields_fail_clearly(self):
        for field, value in (("label", "unknown"), ("label", []), ("confidence", 2),
                             ("confidence", True), ("reasons", "not a list")):
            with self.subTest(field=field, value=value):
                entry = {"label": "candidate", "confidence": 1.0, "reasons": []}
                entry[field] = value
                self.labels["infra"][IP] = entry
                self.labels_path.write_text(json.dumps(self.labels), encoding="utf-8")
                result = self.run_cli()
                self.assertEqual(result.returncode, 2)
                self.assertIn("labels infra[", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(self.output.exists())

    def test_missing_input_and_malformed_jsonl_fail_clearly(self):
        resolutions_path = self.directory / "resolutions.jsonl"
        resolutions_path.write_text("{}\n{\n", encoding="utf-8")
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn("resolutions.jsonl:2: invalid JSON", result.stderr)
        resolutions_path.unlink()
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn("resolutions.jsonl", result.stderr)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
