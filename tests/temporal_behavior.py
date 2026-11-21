"""Controlled All-DNS timeline checks without actor profiles or hidden labels."""

from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from load_data import iter_jsonl, write_jsonl
from pivot.temporal_behavior import find_temporal_matches


ROOT = Path(__file__).resolve().parents[1]


def observation(domain, first, last, rrtype="A", source="forward"):
    """Use explicit timeline fixtures; the domains need not share an IP."""
    value = {"A": "192.0.2.1", "AAAA": "2001:db8::1",
             "NS": "ns.example", "MX": "mail.example"}[rrtype]
    return {"domain": domain, "rrtype": rrtype, "value": value,
            "first_seen": first, "last_seen": last, "source": source}


class AllDnsTimelineTests(unittest.TestCase):
    def test_ns_and_mx_extend_dns_presence_across_disjoint_hosting_periods(self):
        rows = [observation("seed.example", "2025-01-01", "2025-01-10"),
                observation("peer.example", "2025-02-01", "2025-02-10")]
        self.assertEqual(find_temporal_matches("seed.example", rows), [])
        for domain in ("seed.example", "peer.example"):
            for rrtype in ("NS", "MX"):
                rows.append(observation(domain, "2025-01-01", "2025-12-31", rrtype))
        result = find_temporal_matches("seed.example", rows)[0]
        # DNS presence overlaps for the year even though IP use does not.
        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["evidence"]["overlap_days"], 365)

    def test_partial_ip_overlap_and_long_ns_records_change_the_dns_timeline(self):
        rows = [observation("seed.example", "2025-01-01", "2025-01-10"),
                observation("peer.example", "2025-01-06", "2025-01-15")]
        other_ip = dict(rows[1], value="192.0.2.2")
        rows[1] = other_ip
        result = find_temporal_matches("seed.example", rows)[0]
        # Five shared days over a fifteen-day union, with other similarities 1.
        self.assertEqual(result["score"], 0.633333)
        self.assertEqual(result["evidence"]["overlap_days"], 5)
        self.assertEqual(result["evidence"]["seed_activity"]["active_days"], 10)
        for domain in ("seed.example", "peer.example"):
            rows.append(observation(domain, "2025-01-01", "2025-12-31", "NS"))
        extended = find_temporal_matches("seed.example", rows)[0]
        self.assertEqual(extended["score"], 1.0)
        self.assertEqual(extended["evidence"]["overlap_days"], 365)
        self.assertEqual(extended["evidence"]["seed_activity"]["active_days"], 365)

    def test_ns_mx_only_domains_have_dns_profiles_and_unknown_seeds_are_empty(self):
        rows = [observation("seed.example", "2025-01-01", "2025-12-31", "NS"),
                observation("peer.example", "2025-01-01", "2025-12-31", "MX")]
        result = find_temporal_matches("seed.example", rows)[0]
        self.assertEqual(result["candidate"], "peer.example")
        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["evidence"]["seed_activity"]["unique_ip_count"], 0)
        self.assertEqual(find_temporal_matches("unknown.example", rows), [])
        self.assertEqual(find_temporal_matches("seed.example", []), [])

    def test_disjoint_hosting_intervals_do_not_fill_the_gap(self):
        rows = [observation("seed.example", "2025-01-01", "2025-01-02"),
                observation("seed.example", "2025-01-09", "2025-01-10"),
                observation("peer.example", "2025-01-04", "2025-01-06")]
        self.assertEqual(find_temporal_matches("seed.example", rows), [])
        rows[2] = observation("peer.example", "2025-01-02", "2025-01-09")
        result = find_temporal_matches("seed.example", rows)[0]
        self.assertEqual(result["evidence"]["overlap_days"], 2)
        self.assertEqual(result["evidence"]["seed_activity"]["active_days"], 4)
        self.assertEqual(result["evidence"]["seed_activity"]["max_gap_days"], 6)

    def test_duplicate_sources_merge_days_and_preserve_source_coverage(self):
        rows = [observation(domain, "2025-01-01", "2025-01-10", source=source)
                for domain in ("seed.example", "peer.example")
                for source in ("forward", "passive")]
        for records in (rows, rows + rows):
            result = find_temporal_matches("seed.example", records)[0]
            self.assertEqual(result["score"], 1.0)
            self.assertEqual(result["evidence"]["overlap_days"], 10)
            for key in ("seed_activity", "candidate_activity"):
                activity = result["evidence"][key]
                self.assertEqual(activity["active_days"], 10)
                self.assertEqual(activity["forward_days"], 10)
                self.assertEqual(activity["passive_days"], 10)

    def test_ipv6_original_seed_and_deterministic_output(self):
        rows = [observation(domain, "2025-01-01", "2025-01-10", "AAAA")
                for domain in ("seed.example", "z.example", "A.Example.")]
        original = deepcopy(rows)
        results = find_temporal_matches(" Seed.Example. ", rows)
        self.assertEqual([row["candidate"] for row in results], ["a.example", "z.example"])
        self.assertTrue(all(row["seed"] == " Seed.Example. " for row in results))
        self.assertEqual(results, find_temporal_matches(" Seed.Example. ", list(reversed(rows))))
        self.assertEqual(rows, original)

    def test_invalid_hosting_records_and_ip_seeds_fail_clearly(self):
        row = observation("seed.example", "2025-01-01", "2025-01-10")
        for invalid in (dict(row, value="bad-ip"), dict(row, last_seen="2024-01-01"),
                        dict(row, source="unknown")):
            with self.subTest(record=invalid), self.assertRaisesRegex(ValueError, "resolution 1"):
                find_temporal_matches("seed.example", [invalid])
        with self.assertRaisesRegex(ValueError, "IP seeds are not supported"):
            find_temporal_matches("192.0.2.1", [])

    def test_cli_uses_shared_loader_and_retains_contract(self):
        rows = [observation(domain, "2025-01-01", "2025-01-10")
                for domain in ("seed.example", "peer.example")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            write_jsonl(path / "resolutions.jsonl", rows)
            result = subprocess.run(
                [sys.executable, "-m", "pivot.temporal_behavior", "seed.example", "--data-dir", str(path),
                 "--output", str(path / "results.jsonl")], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = list(iter_jsonl(path / "results.jsonl"))
            self.assertEqual(set(output[0]), {"seed", "candidate", "method", "evidence", "score"})
            self.assertEqual(output[0]["method"], "temporal_behavior")


if __name__ == "__main__":
    unittest.main()
