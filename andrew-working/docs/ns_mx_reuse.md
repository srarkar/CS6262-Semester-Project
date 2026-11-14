# Rare NS/MX reuse: understanding and running the code

This method finds domains sharing the seed's uncommon name server (NS) or mail
server (MX) during overlapping observed dates. It returns investigative leads
with evidence; sharing a server does not establish maliciousness or ownership.

## Run the demo

Use Python 3.11 or newer. The implementation uses only the standard library.
From the shared repository root, enter Andrew's workspace:

```sh
cd andrew-working
```

Run the supplied-data demo with explicitly **mocked filter eligibility**:

```sh
python3 -m pivot.ns_mx_reuse oceanoffice.com \
  --data-dir ../seed-data_no-ground-truth \
  --labels examples/mock_ns_mx_labels.json \
  --max-domain-count 10 \
  --output output/ns_mx_results.jsonl
```

Inspect the complete evidence and run the tests:

```sh
python3 -m json.tool --json-lines output/ns_mx_results.jsonl
python3 -m unittest discover -s tests -v
```

The full suite contains 26 tests: 14 for IP co-residency and 12 for NS/MX reuse.
Both NS and MX matching are verified with controlled fixtures. The supplied
synthetic dataset provides this NS demo:

| Field | Actual result |
| --- | --- |
| Seed | `oceanoffice.com` |
| Candidate | `quadravex.com` |
| Shared NS host | `dns107.ovh.net` |
| Infrastructure domain count | 2 |
| Overlap | December 12–29, 2025: 18 inclusive days |
| Method | `ns_mx_reuse` |
| Score | 0.5 |

The mock file permits only that host, with confidence 0 and an explicit `MOCK`
reason retained in the evidence. It is not a classifier. An apparently uncommon
host in a finite dataset can still belong to a public provider. The demo does not
identify either domain as malicious, and actor ownership was not consulted.

## Files and callable interface

| File | Responsibility |
| --- | --- |
| `pivot/ns_mx_reuse.py` | Host eligibility, same-type matching, evidence, rarity score, and CLI |
| `pivot/common.py` | Shared domain normalization, label validation, interval unions/intersections, and source descriptions |
| `load_data.py` | Existing shared JSON/JSONL file I/O |
| `tests/test_ns_mx_reuse.py` | Controlled NS/MX and CLI checks |
| `examples/mock_ns_mx_labels.json` | Hand-selected eligibility for the demo |
| `output/ns_mx_results.jsonl` | Generated demo results; ignored by Git |

Evaluation can import `find_ns_mx_reuse` from `pivot.ns_mx_reuse` and call
`find_ns_mx_reuse(seed, resolutions, infrastructure, labels, max_domain_count=10)`.
It returns result dictionaries without reading files or modifying its inputs.
Use `load_jsonl` and `load_json` from `load_data.py` to supply the loaded records.
The method needs neither registration data nor ground truth.

## How the algorithm works

1. Normalize the domain lookup and observed hostnames to lowercase without a
   trailing dot or surrounding whitespace. Keep the original seed in results.
2. Admit only hosts explicitly labeled `candidate`, present in infrastructure
   metadata with type `ns` or `mx`, and having a positive integer `domain_count`
   at most `max_domain_count`. Missing metadata, missing/invalid counts, missing
   labels, and noise labels cannot establish eligibility and are skipped.
3. Index observations by **record type and exact hostname**, then domain. NS
   records match NS records and MX records match MX records; metadata type must
   agree. Similar hostnames, shared providers, and A/AAAA addresses do not match.
4. For each seed host, union each domain's observed intervals and intersect the
   seed's union with each candidate's union. Count both date endpoints. Preserve
   gaps, deduplicate repeated observations, and never count an overlapping day
   twice because two sources observed it. Keep the original source date ranges.
5. Exclude the seed and candidates with no overlap. Stop at one hop and aggregate
   all supporting hosts into one record per candidate. Sort candidates by name,
   hosts by record type/hostname, and observations by dates for repeatable output.

Ten domains is a simple initial rarity limit, not a tuned detection threshold.
Change it with `--max-domain-count`. Counts come from the supplied full-history
metadata; the method does not infer missing rarity or implement a classifier.

## Output and scoring

Each JSONL record retains the contract's five top-level fields: `seed`,
`candidate`, `method`, `evidence`, and `score`. The method name is `ns_mx_reuse`.

`evidence.max_domain_count` records the configured limit.
`evidence.shared_hosts` contains one entry per matching record type/host:

- `host`, `rrtype`, and `domain_count` identify the relationship and rarity.
- `filter_label` retains the eligibility label, confidence, and reasons.
- `seed_observations` and `candidate_observations` retain source-specific dates
  for the whole relationship.
- `overlap_intervals` lists the contributing intervals and their inclusive
  `days`; `overlap_days` is their total for that host.

Each host's strength is `1 / domain_count`. The candidate's score is the maximum
host strength, rounded to six decimal places. The demo therefore scores
`1 / 2 = 0.5`. Additional hosts add evidence without inflating the score by
summing correlated signals. Overlap is an eligibility requirement; its duration
and filter confidence do not change this rarity score. This differs from the IP
method's duration score, so combined ranking needs evaluation rather than a
direct comparison of the two scores. Neither score is a maliciousness probability.

## Options, errors, and remaining work

`--labels` is required and accepts real filter output in the existing schema when
available. `--data-dir` defaults to `../seed-data_no-ground-truth`, the maximum
domain count defaults to 10, and `--output` defaults to the contracted
`output/pivot_results.jsonl`. Paths are relative to `andrew-working/`. The demo
explicitly chooses `output/ns_mx_results.jsonl` so the two demos have separate
files. Each successful run replaces its selected output.

Unknown domains or domains without eligible overlapping records produce an empty
JSONL file. IP seeds are explicitly rejected. A non-positive/non-integer limit,
missing files, invalid JSON/labels, or malformed eligible observations produces a
CLI error (exit status 2). Input errors occur before replacing the output.

Actual filtering, IP-seed support, fingerprint matching, combined ranking, and
accuracy evaluation remain separate milestones. There is no historical cutoff
mode; this baseline uses the whole synthetic history. Future timing experiments
must apply cutoffs consistently to observations, labels, and domain counts.
