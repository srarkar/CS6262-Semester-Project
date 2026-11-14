# Temporal IP co-residency baseline

See the [repository guide](../README.md) for the project map and next steps.
For the second method, see [rare NS/MX reuse](../docs/ns_mx_reuse.md).

Given a domain seed, find other domains that used the **same eligible IP on
overlapping observed dates**. This is Andrew's first pivot method for the class
project's synthetic DNS data. Each result is an investigative lead with evidence;
it does not establish common ownership or maliciousness.

## Run from `andrew-working/`

Use **Python 3.11 or newer** (verified with Python 3.11.4). Everything uses the
standard library; there are no packages to install or setup steps beyond having
Python available. Run these commands from **`andrew-working/`**, the parent
of this `pivot/` directory. From the shared repository root, first run:

```sh
cd andrew-working
```

Run the reproducible demo with **mock filter labels**:

```sh
python3 -m pivot.ip_coresidency accountcoast.com \
  --data-dir ../seed-data_no-ground-truth \
  --labels examples/mock_infra_labels.json \
  --output output/pivot_results.jsonl
```

The command creates the Git-ignored output directory and replaces the output file. It reports
one result for `docslink.com`. Inspect the complete JSONL record:

```sh
python3 -m json.tool --json-lines output/pivot_results.jsonl
```

Run the controlled tests:

```sh
python3 -m unittest discover -s tests -v
```

The IP method's 14 tests cover inclusive overlap and non-overlap, disjoint gaps, duplicate
observations and source dates, excluded/missing labels, IPv6, exact IP matching
versus a shared ASN or block, aggregation and determinism, self-exclusion, empty
results, missing metadata, and useful input/CLI errors. They use small fixtures
and temporary files without evaluation data. The discovery command also runs
12 NS/MX tests, for 26 tests in total.

`--labels` is required. When the real filter is available, supply its
`output/infra_labels.json` in place of the mock file. `--data-dir` and `--output`
are configurable and default to the paths shown above. An unknown domain or a
domain without eligible A/AAAA observations succeeds with an empty JSONL file.
IP seeds are rejected explicitly. Missing files, invalid JSON, invalid label
entries, and malformed eligible observations produce a CLI error (exit status 2).
Input errors occur before writing the output.

## Files and callable interface

| File | Responsibility |
| --- | --- |
| `load_data.py` | Shared UTF-8 JSON/JSONL reads and deterministic JSONL writes. |
| `pivot/ip_coresidency.py` | IP eligibility/index, interval matching, evidence, score, and CLI. |
| `pivot/common.py` | Domain normalization, label checks, interval operations, and source descriptions shared with NS/MX reuse. |
| `tests/test_ip_coresidency.py` | Standard-library behavioral and CLI tests with controlled data. |
| `examples/mock_infra_labels.json` | Demo-only eligibility for `165.80.147.127`; all other infrastructure is ineligible. |
| `output/pivot_results.jsonl` | Generated results in the shared output contract. |

Evaluation can import `find_ip_coresidents` from `pivot.ip_coresidency` and call
`find_ip_coresidents(seed, resolutions, infrastructure, labels)`. It returns a
list of result dictionaries. Pass loaded records using `load_jsonl` and
`load_json` from `load_data`; the pivot function performs no file I/O and does
not modify its inputs.

The CLI loads only `resolutions.jsonl`, `infra.json`, and the explicit labels
file. This method does not need domain registration history or the manifest.
Actor profiles and ground truth are never inputs. The supplied datasets remain
unchanged.

## Algorithm and policies

1. Normalize domain lookup to lowercase with no trailing dot or surrounding
   whitespace. Preserve the exact original input in the output's `seed` field.
2. Admit only IPs explicitly labeled `candidate` in the filter output and present
   in `infra.json` with type `ipv4` or `ipv6`. Missing labels or infrastructure
   metadata are skipped. Raw infrastructure `unknown` never grants eligibility.
   Parking, sinkhole, CDN, and shared-hosting labels are excluded: shared public
   services would otherwise create misleading relationships.
3. Index A/AAAA observations by canonical IP and domain, keeping dates and source.
   Canonicalization lets equivalent IPv6 spellings identify the same address.
   NS/MX reuse, shared ASNs, and nearby IP addresses do not create matches.
4. For each seed IP, merge overlapping intervals separately for each domain.
   Intersect the seed's intervals with each other domain's intervals and union
   those intersections. Both endpoints count: June 12 through June 22 is 11 days.
   Disjoint intervals remain separate; an unobserved gap contributes no days.
   Forward/passive overlap and repeated rows never count a day twice for an IP.
5. Exclude the seed, emit one record per candidate, and aggregate supporting IPs
   under `evidence.shared_ips`. Expansion stops after this one hop. Results sort
   by candidate name, IPs by canonical address text, and observations/overlaps by
   date. Identical source observations are deduplicated, and their original date
   ranges remain visible rather than assigning every source the merged range.

The labels file uses the existing `infra` / `domains` schema. Label entries
require a supported `label`, numeric `confidence` in [0, 1], and a string list
of `reasons`. The `domains` object may be empty; its timing features are unused.
Missing infrastructure `domain_count` is reported as `null`; it is not invented
or used for scoring. This baseline does not attempt to repair invalid datasets
or infer missing observations.

## Actual demo result and evidence

This is the emitted record, reformatted for reading:

```json
{
  "seed": "accountcoast.com",
  "candidate": "docslink.com",
  "method": "ip_coresidency",
  "evidence": {
    "shared_ips": [
      {
        "ip": "165.80.147.127",
        "domain_count": 2,
        "filter_label": {
          "label": "candidate",
          "confidence": 0.0,
          "reasons": ["MOCK eligibility for the co-residency demo; not a classifier or maliciousness finding"]
        },
        "seed_observations": [
          {"first_seen": "2025-06-12", "last_seen": "2025-12-31", "source": "forward"},
          {"first_seen": "2025-06-14", "last_seen": "2025-12-29", "source": "passive"}
        ],
        "candidate_observations": [
          {"first_seen": "2024-12-06", "last_seen": "2025-06-22", "source": "forward"},
          {"first_seen": "2024-12-21", "last_seen": "2025-06-23", "source": "passive"}
        ],
        "overlap_intervals": [
          {"first_seen": "2025-06-12", "last_seen": "2025-06-23", "days": 12}
        ],
        "overlap_days": 12
      }
    ]
  },
  "score": 0.4
}
```

Each shared IP includes its infrastructure distinct-domain count, the eligibility
label and reasons, original seed/candidate source observations, deduplicated
overlap intervals, and their total inclusive days. The observations describe the
whole domain/IP relationship; `overlap_intervals` identifies which dates actually
contribute. `domain_count` comes from the full supplied infrastructure history.

**The task's 11-day example uses forward observations only.** In the supplied
file, `docslink.com`'s passive record extends to June 23, so combining both sources
correctly gives **12 days**, June 12–23. The controlled tests verify both the
forward-only 11-day case and the combined-source 12-day case. The baseline uses
both sources and preserves this difference in evidence.

For each IP, strength is `min(overlap_days / 30, 1.0)`. The result's score is the
maximum strength across its shared IPs, rounded to six decimal places. Thus the
demo scores `12 / 30 = 0.4`; 30 or more overlapping days scores 1. Additional IPs
add evidence without summing overlapping calendar days across IPs. Thirty days
is a simple illustrative saturation point, not a tuned detection threshold.
Scores measure temporal evidence strength, **not maliciousness probabilities**;
label confidence and domain count do not affect this baseline's score.

## Integration boundaries

The mock file is hand-selected eligibility for a reproducible demonstration,
with confidence 0.0 and an explicit `MOCK` reason retained in the result. It is
not a noise classifier or a finding that the IP or domains are malicious.
Actual filter output remains an integration dependency.

This implements domain-seed IP co-residency on synthetic data. IP-seed semantics,
fingerprint matching, recursive discovery, combined ranking, and
ground-truth accuracy evaluation remain separate work. There is no live scanning
or historical cutoff mode: results use the whole supplied observation history.
Any later historical experiment must apply its cutoff to observations, filter
features, and infrastructure domain counts together. No precision, recall, or
real APT detection accuracy is claimed.

NS/MX reuse is implemented separately in `pivot/ns_mx_reuse.py`; it uses the same
interval helpers and JSONL fields, with its own evidence and rarity score.
