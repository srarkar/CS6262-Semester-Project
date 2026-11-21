"""Controlled registration-history regressions; no hidden actor data is used."""

from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from load_data import iter_jsonl, write_json, write_jsonl
from pivot.fingerprint_match import find_fingerprint_matches


ROOT = Path(__file__).resolve().parents[1]


def observation(domain, ip, first, last=None):
    """Make a small explicit hosting observation."""
    return {"domain": domain, "rrtype": "AAAA" if ":" in ip else "A", "value": ip,
            "first_seen": first, "last_seen": last or first, "source": "forward"}


def registration(registrar, registered, expired=None):
    """Use the same registration-history fields as the shared contract."""
    return {"registrar": registrar, "registered": registered, "expired": expired}


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.infra = {"192.0.2.1": {"type": "ipv4", "asn": 1},
                      "192.0.2.2": {"type": "ipv4", "asn": 2},
                      "2001:db8::1": {"type": "ipv6", "asn": 1}}
        self.labels = {"infra": {
            ip: {"label": "candidate", "confidence": 1.0, "reasons": ["controlled eligibility"]}
            for ip in self.infra
        }, "domains": {}}
        self.history = {"registrations": [
            registration("Old Registrar", "2024-01-01", "2024-06-30"),
            registration("New Registrar", "2025-01-01")]}

    def find(self, rows, domains, seed="seed.example"):
        """Exercise the public method using only controlled records."""
        return find_fingerprint_matches(seed, rows, self.infra, domains, self.labels)

    def test_seed_does_not_mix_old_registrar_with_new_owner_asn(self):
        rows = [observation("seed.example", "192.0.2.1", "2024-01-01"),
                observation("seed.example", "192.0.2.2", "2025-01-01"),
                observation("peer.example", "192.0.2.2", "2024-01-01")]
        domains = {"seed.example": self.history,
                   "peer.example": registration("Old Registrar", "2024-01-01")}
        result = self.find(rows, domains)[0]
        self.assertEqual(result["score"], 0.75)
        self.assertFalse(result["evidence"]["registrar_match"])
        self.assertEqual(result["evidence"]["seed"]["registrar"], "new registrar")
        self.assertEqual(result["evidence"]["seed"]["registration_date"], "2025-01-01")
        self.assertEqual(result["evidence"]["shared_hosting_asns"], ["2"])

    def test_candidate_features_also_stay_in_one_registration_period(self):
        rows = [observation("seed.example", "192.0.2.2", "2024-01-01"),
                observation("peer.example", "192.0.2.1", "2024-01-01"),
                observation("peer.example", "192.0.2.2", "2025-01-01")]
        domains = {"seed.example": registration("Old Registrar", "2024-01-01"),
                   "peer.example": self.history}
        result = self.find(rows, domains)[0]
        self.assertEqual(result["score"], 0.75)
        self.assertEqual(result["evidence"]["candidate"]["registrar"], "new registrar")

    def test_historical_registration_remains_searchable(self):
        rows = [observation("seed.example", "192.0.2.1", "2024-01-01"),
                observation("seed.example", "192.0.2.2", "2025-01-01"),
                observation("peer.example", "192.0.2.1", "2024-01-01")]
        domains = {"seed.example": self.history,
                   "peer.example": registration("Old Registrar", "2024-01-01")}
        result = self.find(rows, domains)[0]
        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["evidence"]["seed"]["registration_date"], "2024-01-01")
        self.assertEqual(result["evidence"]["seed"]["registration_expired"], "2024-06-30")

    def test_observation_spanning_periods_is_clipped_before_aging(self):
        rows = [observation("seed.example", "192.0.2.1", "2023-01-01", "2025-02-01"),
                observation("peer.example", "192.0.2.1", "2025-01-01")]
        domains = {"seed.example": self.history,
                   "peer.example": registration("New Registrar", "2025-01-01")}
        result = self.find(rows, domains)[0]
        self.assertEqual(result["score"], 1.0)
        episode = result["evidence"]["seed"]
        self.assertEqual(episode["registration_date"], "2025-01-01")
        self.assertEqual(episode["first_ip_observation_start"], "2025-01-01")
        self.assertEqual(episode["aging_days"], 0)
        self.assertIsNone(episode["registration_expired"])

    def test_registration_gap_is_excluded_and_expiry_day_is_inclusive(self):
        peer = observation("peer.example", "192.0.2.1", "2024-06-30")
        domains = {"seed.example": self.history,
                   "peer.example": registration("Old Registrar", "2024-01-01")}
        gap = observation("seed.example", "192.0.2.1", "2024-07-01", "2024-12-31")
        self.assertEqual(self.find([gap, peer], domains), [])
        boundary = observation("seed.example", "192.0.2.1", "2024-06-30")
        self.assertEqual(self.find([boundary, peer], domains)[0]["score"], 1.0)

    def test_single_period_ipv6_and_original_seed_are_preserved(self):
        rows = [observation("seed.example", "2001:db8::1", "2024-01-01"),
                observation("Peer.Example.", "2001:0db8::1", "2024-01-01")]
        domains = {name: registration(" Registrar ", "2024-01-01")
                   for name in ("seed.example", "peer.example")}
        results = self.find(rows, domains, seed=" Seed.Example. ")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["seed"], " Seed.Example. ")
        self.assertEqual(results[0]["candidate"], "peer.example")
        self.assertEqual(results[0]["method"], "fingerprint_match")
        self.assertEqual(results[0]["score"], 1.0)

    def test_filtering_and_missing_registration_metadata_still_apply(self):
        rows = [observation("seed.example", "192.0.2.1", "2024-01-01"),
                observation("peer.example", "192.0.2.1", "2024-01-01")]
        domains = {name: registration("Registrar", "2024-01-01")
                   for name in ("seed.example", "peer.example")}
        self.labels["infra"]["192.0.2.1"]["label"] = "parking"
        self.assertEqual(self.find(rows, domains), [])
        self.labels["infra"]["192.0.2.1"]["label"] = "candidate"
        domains["peer.example"] = {"registrations": [registration("R", "invalid-date")]}
        self.assertEqual(self.find(rows, domains), [])
        self.assertEqual(self.find([], {}), [])

    def test_episode_ties_duplicates_and_input_order_are_deterministic(self):
        history = {"registrations": [registration("R", "2024-01-01", "2024-06-30"),
                                      registration("R", "2025-01-01")]}
        domains = {"seed.example": history, "peer.example": registration("R", "2024-01-01")}
        rows = [observation("seed.example", "192.0.2.1", "2024-01-01"),
                observation("seed.example", "192.0.2.1", "2025-01-01"),
                observation("peer.example", "192.0.2.1", "2024-01-01")]
        original = deepcopy((rows, domains, self.labels))
        results = self.find(rows, domains)
        reordered = deepcopy(domains)
        reordered["seed.example"]["registrations"].reverse()
        self.assertEqual(results, self.find(list(reversed(rows)) + rows, reordered))
        self.assertEqual(results[0]["evidence"]["seed"]["registration_date"], "2024-01-01")
        self.assertEqual((rows, domains, self.labels), original)

    def test_cli_uses_shared_loader_and_retains_contract_fields(self):
        rows = [observation("seed.example", "192.0.2.1", "2024-01-01"),
                observation("peer.example", "192.0.2.1", "2024-01-01")]
        domains = {name: registration("R", "2024-01-01") for name in ("seed.example", "peer.example")}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            write_jsonl(path / "resolutions.jsonl", rows)
            write_json(path / "infra.json", self.infra)
            write_json(path / "domains.json", domains)
            write_json(path / "labels.json", self.labels)
            result = subprocess.run(
                [sys.executable, "-m", "pivot.fingerprint_match", "seed.example",
                 "--data-dir", str(path), "--labels", str(path / "labels.json"),
                 "--output", str(path / "results.jsonl")],
                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = list(iter_jsonl(path / "results.jsonl"))
            self.assertEqual(set(output[0]), {"seed", "candidate", "method", "evidence", "score"})
            self.assertEqual(output[0]["candidate"], "peer.example")


if __name__ == "__main__":
    unittest.main()
