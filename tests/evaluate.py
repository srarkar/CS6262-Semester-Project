"""Controlled checks of evaluation metrics, filter conditions, and the benchmark run."""

import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from evaluation.evaluate import (actor_seed_metrics, average_precision, choose_seeds,
                                 evidence_correct_share, evaluate, fuse_reciprocal_rank,
                                 index_actor_infra, no_filter_labels, perfect_filter_labels,
                                 rank_candidates)
from load_data import iter_jsonl, read_json, write_json, write_jsonl
from pivot.common import validate_labels


def observation(domain, value, first, last, rrtype="A", source="forward"):
    """Keep each fixture's relationship and dates explicit."""
    return {"domain": domain, "rrtype": rrtype, "value": value,
            "first_seen": first, "last_seen": last, "source": source}


# Actor A: a1 and a2 share 10.0.0.1 at the same time; a3 uses it later; a4 has no records.
RESOLUTIONS = [
    observation("a1.example", "10.0.0.1", "2025-01-01", "2025-01-31"),
    observation("a2.example", "10.0.0.1", "2025-01-20", "2025-02-10"),
    observation("a3.example", "10.0.0.1", "2025-06-01", "2025-06-30"),
    observation("b1.example", "10.0.0.9", "2025-01-01", "2025-01-31"),
    observation("c1.example", "10.0.0.8", "2025-01-01", "2025-01-31"),
    observation("benign.example", "10.0.0.7", "2025-01-01", "2025-01-31"),
]
GROUND_TRUTH = {
    "actors": {
        "A": {"domains": ["a1.example", "a2.example", "a3.example", "a4.example"],
              "ips": ["10.0.0.1"], "ns_hosts": [], "mx_hosts": [], "cdn_fronted_domains": []},
        "B": {"domains": ["b1.example"], "ips": ["10.0.0.9"], "ns_hosts": [], "mx_hosts": [],
              "cdn_fronted_domains": []},
    },
    "domain_labels": {"a1.example": "actor:A", "a2.example": "actor:A", "a3.example": "actor:A",
                      "a4.example": "actor:A", "b1.example": "actor:B", "c1.example": "crimeware",
                      "benign.example": "benign"},
    "infra_labels": {"10.0.0.1": "actor", "10.0.0.9": "actor", "10.0.0.8": "dedicated",
                     "10.0.0.7": "shared_hosting"},
}
OBSERVED = {row["domain"] for row in RESOLUTIONS}


class MetricTests(unittest.TestCase):
    def test_average_precision_counts_missed_positives_as_zero(self):
        ranking = ["p1", "n1", "p2"]
        self.assertAlmostEqual(average_precision(ranking, {"p1", "p2", "p3"}), (1 / 1 + 2 / 3) / 3)
        self.assertIsNone(average_precision(ranking, set()))

    def test_actor_seed_metrics_use_three_recall_levels(self):
        index = index_actor_infra(RESOLUTIONS, GROUND_TRUTH)
        metrics = actor_seed_metrics(["a2.example", "c1.example", "b1.example"], "A", "a1.example",
                                     GROUND_TRUTH, OBSERVED, index)
        self.assertEqual(metrics["n_positives"], 2)      # a2, a3 (a4 is unobserved)
        self.assertEqual(metrics["n_reachable"], 1)      # only a2 overlaps a1 in time
        self.assertAlmostEqual(metrics["recall_all"], 1 / 3)
        self.assertAlmostEqual(metrics["recall_observed"], 1 / 2)
        self.assertAlmostEqual(metrics["recall_reachable"], 1.0)
        self.assertAlmostEqual(metrics["precision"], 1 / 3)
        self.assertAlmostEqual(metrics["precision_at_5"], 1 / 5)  # short lists still divide by k
        self.assertEqual(metrics["other_malicious_in_top_25"], 2)  # crimeware and actor B

    def test_rankings_are_deterministic_and_fusion_uses_rank(self):
        results = [{"candidate": "b", "score": 0.5}, {"candidate": "a", "score": 0.5},
                   {"candidate": "c", "score": 0.9}, {"candidate": "a", "score": 0.2}]
        self.assertEqual(rank_candidates(results), ["c", "a", "b"])
        # y is ranked by both methods; x and z once each, x at the better rank.
        self.assertEqual(fuse_reciprocal_rank([["x", "y"], ["y", "z"]]), ["y", "x", "z"])
        self.assertEqual(fuse_reciprocal_rank([["b"], ["a"]]), ["a", "b"])

    def test_evidence_correctness_checks_the_shared_value(self):
        results = [
            {"candidate": "a2.example", "evidence": {"shared_ips": [{"ip": "10.0.0.1"}]}},
            {"candidate": "a3.example", "evidence": {"shared_hosts": [{"host": "ns.other.example"}]}},
            {"candidate": "c1.example", "evidence": {"shared_ips": [{"ip": "10.0.0.1"}]}},
        ]
        share = evidence_correct_share(results, {"a2.example", "a3.example"}, GROUND_TRUTH["actors"]["A"])
        self.assertAlmostEqual(share, 1 / 2)


class SetupTests(unittest.TestCase):
    def test_filter_conditions_are_valid_labels(self):
        perfect = perfect_filter_labels(GROUND_TRUTH)
        validate_labels(perfect)
        validate_labels(no_filter_labels({"10.0.0.1": {}, "ns.example": {}}))
        self.assertEqual(sorted(perfect["infra"]), ["10.0.0.1", "10.0.0.8", "10.0.0.9"])

    def test_seeds_skip_unobserved_domains_and_sample_deterministically(self):
        seeds = choose_seeds(GROUND_TRUTH["domain_labels"], OBSERVED, benign_sample=5, random_seed=1)
        self.assertNotIn(("a4.example", "A"), seeds)
        self.assertIn(("benign.example", "benign"), seeds)
        self.assertIn(("c1.example", "crimeware"), seeds)
        self.assertEqual(seeds, choose_seeds(GROUND_TRUTH["domain_labels"], OBSERVED, 5, 1))


class RunTests(unittest.TestCase):
    def test_benchmark_writes_contract_results_and_scores_a_true_positive(self):
        infrastructure = {value: {"type": "ipv4", "asn": 1, "org": "x", "country": "US",
                                  "domain_count": 3, "label": "unknown"}
                          for value in ("10.0.0.1", "10.0.0.7", "10.0.0.8", "10.0.0.9")}
        domains = {row["domain"]: {"registrar": "R", "registered": "2024-01-01",
                                   "registrations": [{"registrar": "R", "registered": "2024-01-01",
                                                      "expired": None}]}
                   for row in RESOLUTIONS}
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "data"
            write_jsonl(data / "resolutions.jsonl", RESOLUTIONS)
            write_json(data / "infra.json", infrastructure)
            write_json(data / "domains.json", domains)
            write_json(data / "ground_truth.json", GROUND_TRUTH)
            output = Path(directory) / "eval"
            with contextlib.redirect_stdout(io.StringIO()):
                evaluate(data, data, output, benign_sample=5, random_seed=1)

            results = list(iter_jsonl(output / "no_filter" / "pivot_results.jsonl"))
            self.assertTrue(results)
            self.assertTrue(all(set(r) == {"seed", "candidate", "method", "evidence", "score"}
                                for r in results))
            summary = read_json(output / "summary.json")["results"]
            ip_actor_a = summary["perfect_filter"]["ip_coresidency"]["A"]
            # Seeds a1 and a2 find each other (recall 1/2); a3 never overlaps (recall 0).
            self.assertEqual(ip_actor_a["n_seeds"], 3)
            self.assertEqual(ip_actor_a["recall_observed"]["mean"], round(1 / 6 + 1 / 6, 4))


if __name__ == "__main__":
    unittest.main()
