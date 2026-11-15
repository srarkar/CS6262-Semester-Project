import unittest
from datetime import date

from pivot.fingerprint_match import find_fingerprint_matches
from pivot.temporal_behavior import find_temporal_matches


class FingerprintMatchTests(unittest.TestCase):
    def setUp(self):
        self.infra = {
            "192.0.2.1": {"type": "ipv4", "asn": 64500},
            "192.0.2.2": {"type": "ipv4", "asn": 64500},
            "ns.example": {"type": "ns", "asn": 64500},
        }
        self.domains = {
            "seed.example": {"registrar": "Registrar A", "registered": "2024-01-01",
                              "registrations": [{"registrar": "Registrar A", "registered": "2024-01-01", "expired": None}]},
            "candidate.example": {"registrar": "Registrar A", "registered": "2024-01-11",
                                   "registrations": [{"registrar": "Registrar A", "registered": "2024-01-11", "expired": None}]},
        }
        self.labels = {"infra": {
            "192.0.2.1": {"label": "candidate", "confidence": 0.9, "reasons": []},
            "192.0.2.2": {"label": "candidate", "confidence": 0.9, "reasons": []},
            "ns.example": {"label": "candidate", "confidence": 0.9, "reasons": []},
        }, "domains": {}}
        self.rows = [
            {"domain": "seed.example", "rrtype": "A", "value": "192.0.2.1", "first_seen": "2024-01-21", "last_seen": "2024-02-01", "source": "passive"},
            {"domain": "candidate.example", "rrtype": "A", "value": "192.0.2.2", "first_seen": "2024-02-01", "last_seen": "2024-02-10", "source": "forward"},
            {"domain": "seed.example", "rrtype": "NS", "value": "ns.example", "first_seen": "2024-01-01", "last_seen": "2024-02-01", "source": "passive"},
        ]

    def test_shared_asn_and_registration_history(self):
        results = find_fingerprint_matches("seed.example", self.rows, self.infra, self.domains, self.labels)
        self.assertEqual([r["candidate"] for r in results], ["candidate.example"])
        evidence = results[0]["evidence"]
        self.assertEqual(evidence["seed"]["aging_days"], 20)
        self.assertEqual(evidence["candidate"]["aging_days"], 21)
        self.assertTrue(evidence["registrar_match"])
        self.assertEqual(evidence["shared_hosting_asns"], ["64500"])

    def test_raw_unknown_or_non_ip_infra_is_not_used(self):
        labels = {"infra": {"ns.example": {"label": "candidate", "confidence": 1, "reasons": []}}, "domains": {}}
        self.assertEqual(find_fingerprint_matches("seed.example", self.rows, self.infra, self.domains, labels), [])


class TemporalBehaviorTests(unittest.TestCase):
    def test_temporal_similarity_and_source_evidence(self):
        rows = [
            {"domain": "seed.example", "rrtype": "A", "value": "192.0.2.1", "first_seen": "2024-01-01", "last_seen": "2024-01-10", "source": "passive"},
            {"domain": "seed.example", "rrtype": "A", "value": "192.0.2.2", "first_seen": "2024-01-11", "last_seen": "2024-01-20", "source": "forward"},
            {"domain": "candidate.example", "rrtype": "A", "value": "192.0.2.3", "first_seen": "2024-01-01", "last_seen": "2024-01-20", "source": "passive"},
            {"domain": "candidate.example", "rrtype": "AAAA", "value": "2001:db8::1", "first_seen": "2024-01-05", "last_seen": "2024-01-20", "source": "forward"},
        ]
        results = find_temporal_matches("seed.example", rows)
        self.assertEqual([r["candidate"] for r in results], ["candidate.example"])
        self.assertEqual(results[0]["evidence"]["overlap_days"], 20)
        self.assertIn("forward_days", results[0]["evidence"]["seed_activity"])
        self.assertGreater(results[0]["score"], 0)

    def test_no_temporal_overlap_means_no_candidate(self):
        rows = [
            {"domain": "seed.example", "rrtype": "A", "value": "192.0.2.1", "first_seen": "2024-01-01", "last_seen": "2024-01-02", "source": "passive"},
            {"domain": "candidate.example", "rrtype": "A", "value": "192.0.2.2", "first_seen": "2024-02-01", "last_seen": "2024-02-02", "source": "passive"},
        ]
        self.assertEqual(find_temporal_matches("seed.example", rows), [])


if __name__ == "__main__":
    unittest.main()
