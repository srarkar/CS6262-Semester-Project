"""Controlled NS/MX behavior and CLI checks without evaluation data."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from load_data import load_jsonl, write_jsonl
from pivot.ns_mx_reuse import find_ns_mx_reuse


WORKSPACE = Path(__file__).resolve().parents[1]
NS = "ns.small.example"
MX = "mail.small.example"


def observation(domain, rrtype="NS", host=NS, first="2025-01-01", last="2025-01-10", source="forward"):
    """Keep each fixture's relationship, dates, and source explicit."""
    return {"domain": domain, "rrtype": rrtype, "value": host,
            "first_seen": first, "last_seen": last, "source": source}


class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.infrastructure = {
            NS: {"type": "ns", "domain_count": 2, "label": "unknown"},
            MX: {"type": "mx", "domain_count": 3, "label": "unknown"},
        }
        self.labels = {"infra": {
            host: {"label": "candidate", "confidence": 0.0, "reasons": ["controlled test eligibility"]}
            for host in (NS, MX)
        }, "domains": {}}

    def find(self, rows, seed="seed.example", max_domain_count=10):
        """Use the same small inputs for each independently initialized case."""
        return find_ns_mx_reuse(seed, rows, self.infrastructure, self.labels, max_domain_count)

    def test_ns_and_mx_matches_normalize_names_and_preserve_seed(self):
        for rrtype, host, count in (("NS", NS, 2), ("MX", MX, 3)):
            with self.subTest(rrtype=rrtype):
                rows = [observation("seed.example", rrtype, host),
                        observation("Peer.Example.", rrtype, host.upper() + ".",
                                    first="2025-01-10", last="2025-01-12")]
                results = self.find(rows, seed=" Seed.Example. ")
                self.assertEqual(len(results), 1)
                result = results[0]
                self.assertEqual(set(result), {"seed", "candidate", "method", "evidence", "score"})
                self.assertEqual(result["seed"], " Seed.Example. ")
                self.assertEqual(result["candidate"], "peer.example")
                self.assertEqual(result["method"], "ns_mx_reuse")
                self.assertEqual(result["score"], round(1 / count, 6))
                shared = result["evidence"]["shared_hosts"][0]
                self.assertEqual((shared["rrtype"], shared["host"]), (rrtype, host))
                self.assertEqual(shared["domain_count"], count)
                self.assertEqual(shared["overlap_intervals"], [
                    {"first_seen": "2025-01-10", "last_seen": "2025-01-10", "days": 1}])

    def test_common_hosts_and_unknown_rarity_are_excluded(self):
        rows = [observation("seed.example"), observation("peer.example")]
        self.infrastructure[NS]["domain_count"] = 11
        self.assertEqual(self.find(rows), [])
        result = self.find(rows, max_domain_count=11)[0]
        self.assertEqual(result["evidence"]["max_domain_count"], 11)
        self.assertEqual(result["score"], 0.090909)
        for count in (None, 0, -1, True, "2", 2.5):
            with self.subTest(count=count):
                self.infrastructure[NS]["domain_count"] = count
                self.assertEqual(self.find(rows), [])
        del self.infrastructure[NS]["domain_count"]
        self.assertEqual(self.find(rows), [])
        self.infrastructure.clear()
        self.assertEqual(self.find(rows), [])

    def test_only_explicit_candidate_labels_allow_expansion(self):
        rows = [observation("seed.example"), observation("peer.example")]
        for label in ("parking", "sinkhole", "cdn", "shared_hosting"):
            with self.subTest(label=label):
                self.labels["infra"][NS]["label"] = label
                self.assertEqual(self.find(rows), [])
        self.labels["infra"].clear()
        self.assertEqual(self.find(rows), [])

    def test_disjoint_intervals_do_not_bridge_gaps_or_match_later_use(self):
        rows = [observation("seed.example", last="2025-01-03"),
                observation("seed.example", first="2025-01-10", last="2025-01-12"),
                observation("peer.example", first="2025-01-02", last="2025-01-11"),
                observation("gap.example", first="2025-01-04", last="2025-01-09"),
                observation("later.example", first="2025-01-13", last="2025-01-15")]
        results = self.find(rows)
        self.assertEqual([row["candidate"] for row in results], ["peer.example"])
        shared = results[0]["evidence"]["shared_hosts"][0]
        self.assertEqual(shared["overlap_days"], 4)
        self.assertEqual(shared["overlap_intervals"], [
            {"first_seen": "2025-01-02", "last_seen": "2025-01-03", "days": 2},
            {"first_seen": "2025-01-10", "last_seen": "2025-01-11", "days": 2}])

    def test_duplicate_sources_union_days_and_retain_source_dates(self):
        rows = [observation("seed.example"), observation("peer.example", first="2025-01-05"),
                observation("peer.example", first="2025-01-07", last="2025-01-12", source="passive")]
        results = self.find(rows)
        self.assertEqual(results, self.find(rows + rows))
        shared = results[0]["evidence"]["shared_hosts"][0]
        self.assertEqual(shared["overlap_days"], 6)
        self.assertEqual(shared["candidate_observations"], [
            {"first_seen": "2025-01-05", "last_seen": "2025-01-10", "source": "forward"},
            {"first_seen": "2025-01-07", "last_seen": "2025-01-12", "source": "passive"}])

    def test_record_types_and_exact_hostnames_must_match(self):
        for seed_type, other_type in (("NS", "MX"), ("MX", "NS")):
            with self.subTest(seed_type=seed_type):
                self.infrastructure[NS]["type"] = seed_type.lower()
                rows = [observation("seed.example", seed_type), observation("peer.example", other_type),
                        observation("sibling.example", seed_type, host="other.small.example"),
                        observation("address.example", "A")]
                self.assertEqual(self.find(rows), [])
        self.infrastructure[NS]["type"] = "ipv4"
        self.assertEqual(self.find([observation("seed.example"), observation("peer.example")]), [])

    def test_hosts_aggregate_deterministically_without_mutating_inputs(self):
        rows = [observation("seed.example"), observation("peer.example"), observation("z.example"),
                observation("seed.example", "MX", MX), observation("peer.example", "MX", MX)]
        original = deepcopy((rows, self.infrastructure, self.labels))
        results = self.find(rows)
        self.assertEqual(results, self.find(list(reversed(rows))))
        self.assertEqual([row["candidate"] for row in results], ["peer.example", "z.example"])
        hosts = results[0]["evidence"]["shared_hosts"]
        self.assertEqual([(item["rrtype"], item["host"]) for item in hosts], [("MX", MX), ("NS", NS)])
        self.assertEqual(results[0]["score"], 0.5)  # Strongest host, not a sum of repeated evidence.
        self.assertEqual((rows, self.infrastructure, self.labels), original)

    def test_unknown_seeds_and_second_hop_domains_are_not_returned(self):
        rows = [observation("seed.example"), observation("peer.example"),
                observation("peer.example", "MX", MX), observation("second-hop.example", "MX", MX)]
        self.assertEqual([row["candidate"] for row in self.find(rows)], ["peer.example"])
        self.assertEqual(self.find(rows, seed="unknown.example"), [])
        self.assertEqual(self.find([]), [])

    def test_invalid_seeds_thresholds_and_eligible_rows_fail_clearly(self):
        for seed in ("", "192.0.2.1", "2001:db8::1"):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                self.find([], seed=seed)
        for limit in (0, -1, True, 2.5, "10"):
            with self.subTest(limit=limit), self.assertRaisesRegex(ValueError, "positive integer"):
                self.find([], max_domain_count=limit)
        for field, value in (("first_seen", "bad-date"), ("last_seen", "2024-01-01"),
                             ("source", "other"), ("domain", None), ("value", None)):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "resolution 1"):
                self.find([dict(observation("seed.example"), **{field: value})])
        with self.assertRaisesRegex(ValueError, "resolution 1"):
            self.find([None])


class CliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.output = self.directory / "output" / "results.jsonl"
        self.labels = self.directory / "labels.json"
        self.labels.write_text(json.dumps({"infra": {
            NS: {"label": "candidate", "confidence": 0.0, "reasons": ["controlled test eligibility"]}
        }, "domains": {}}), encoding="utf-8")
        (self.directory / "infra.json").write_text(json.dumps(
            {NS: {"type": "ns", "domain_count": 2, "label": "unknown"}}), encoding="utf-8")
        write_jsonl(self.directory / "resolutions.jsonl", [observation("seed.example"), observation("peer.example")])

    def run_cli(self, *extra, seed="seed.example"):
        """Exercise the real module entry point using isolated input/output files."""
        return subprocess.run(
            [sys.executable, "-m", "pivot.ns_mx_reuse", seed,
             "--data-dir", str(self.directory), "--labels", str(self.labels),
             "--output", str(self.output), *extra],
            cwd=WORKSPACE, text=True, capture_output=True, check=False)

    def test_success_threshold_and_empty_output(self):
        result = self.run_cli(seed="Seed.Example.")
        self.assertEqual(result.returncode, 0, result.stderr)
        records = load_jsonl(self.output)
        self.assertEqual(records[0]["seed"], "Seed.Example.")
        self.assertEqual(records[0]["candidate"], "peer.example")
        self.assertEqual(records[0]["method"], "ns_mx_reuse")
        self.assertEqual(records[0]["score"], 0.5)
        original = self.output.read_bytes()
        self.assertEqual(self.run_cli(seed="Seed.Example.").returncode, 0)
        self.assertEqual(self.output.read_bytes(), original)
        self.assertEqual(self.run_cli("--max-domain-count", "1").returncode, 0)
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertEqual(self.run_cli(seed="unknown.example").returncode, 0)
        self.assertEqual(self.output.read_bytes(), b"")

    def test_missing_or_invalid_labels_leave_existing_output_intact(self):
        write_jsonl(self.output, [{"previous": "result"}])
        original = self.output.read_bytes()
        for contents, message in ((None, "labels.json"), ("{", "invalid JSON"), ("[]", "'infra' object")):
            with self.subTest(contents=contents):
                if contents is None:
                    self.labels.unlink()
                else:
                    self.labels.write_text(contents, encoding="utf-8")
                result = self.run_cli()
                self.assertEqual(result.returncode, 2)
                self.assertIn(message, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(self.output.read_bytes(), original)

    def test_invalid_threshold_and_input_report_errors_without_output(self):
        result = self.run_cli("--max-domain-count", "0")
        self.assertEqual(result.returncode, 2)
        self.assertIn("positive integer", result.stderr)
        resolutions = self.directory / "resolutions.jsonl"
        resolutions.write_text("{}\n{\n", encoding="utf-8")
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn("resolutions.jsonl:2: invalid JSON", result.stderr)
        resolutions.unlink()
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn("resolutions.jsonl", result.stderr)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
