# Evaluation plan (proposal, v0.2)

Status: **proposal for team review.** Decisions marked *Agreed* are settled for
evaluation; the rest are proposed defaults. This plan adds no fields to the
shared data format.

## Scope

Evaluation measures how well the pivot methods recover an actor's other domains
from one seed domain. The noise filter is not scored directly; its effect is
measured by running the pivots under different filter conditions (below).

## What evaluation consumes

- `output/pivot_results.jsonl` in the existing contract (`seed`, `candidate`,
  `method`, `evidence`, `score`). One file may hold many seeds and methods.
- `ground_truth.json` from `data/seed-data_with-ground-truth/`, read only by
  `evaluation/` through `load_ground_truth()`.
- Optionally, real filter output (`output/infra_labels.json`) when it exists.

Pivots run against `data/seed-data_no-ground-truth/`. Its observation files are
byte-identical to the ground-truth copy. The dataset directory is a parameter so
a later dataset version can be evaluated the same way.

**Runner split:** evaluation owns a batch runner that calls each pivot function
for every benchmark seed and writes one contract-format `pivot_results.jsonl`.
Scoring reads only that file, so any method that writes the contract can be
scored without changes to evaluation.

| Method | Function | Branch | Uses filter labels |
|---|---|---|---|
| `ip_coresidency` | `find_ip_coresidents(seed, resolutions, infra, labels)` | main | yes |
| `ns_mx_reuse` | `find_ns_mx_reuse(seed, resolutions, infra, labels, max_domain_count=10)` | main | yes |
| `fingerprint_match` | `find_fingerprint_matches(seed, resolutions, infra, domains, labels)` | `rickdev/pivoting` | yes |
| `temporal_behavior` | `find_temporal_matches(seed, resolutions)` | `rickdev/pivoting` | no |

## Decisions

| # | Decision | Proposal | Status |
|---|---|---|---|
| 1 | Correct candidate for a seed | Other domains of the **same actor**. Crimeware and other-actor hits are false positives, also counted separately. | Agreed |
| 2 | Recall answer sets | Three levels (see below); headline uses observed same-actor domains. | Proposed |
| 3 | Benchmark seeds | Every actor domain with observations (56, leave-one-out), a fixed random sample of 100 **observed** benign domains, and all 40 crimeware domains (random seed 6262). Domain seeds only until IP-seed behavior exists. | Agreed |
| 4 | Filter conditions | **no-filter**, **perfect-filter**, and later **real-filter**. See below. | Agreed |
| 5 | Perfect-filter eligibility | Ground-truth labels `actor`, `dedicated`, `self_hosted_ns`, `self_hosted_mail` become `candidate`; every other label is excluded. | Proposed |
| 6 | Where to cut a result list | Rank-based metrics are primary. Precision and recall over the full returned list are reported but not headlined (see below). | Proposed |
| 7 | Combined ranking | Reciprocal rank fusion of the per-method rankings (`sum of 1 / (60 + rank)`), because method scores are on different scales. The per-candidate maximum score is reported as a comparison. | Proposed; owner unassigned |
| 8 | Averaging | Compute per seed, average seeds within each actor, then weight the two actors equally. Also report medians. | Proposed |
| 9 | Method parameters | `max_domain_count=10`; other methods have no parameters. Recorded with every run. Sweeps are separate experiments. | Proposed |
| 10 | Forward vs. passive | Optional extra experiment, not a core metric. If included, lead time only for methods whose evidence has `overlap_intervals` (IP and NS/MX). | Open: confirm whether the team wants it |
| 11 | `temporal_behavior` method name | Not in the v0.1 contract; Rick's branch adds it to `PIVOT_METHODS`. Needs team agreement before merge. Evaluation treats it as one more method either way. | Needs team |
| 12 | Stable evidence keys | IP: `evidence.shared_ips[].ip`; NS/MX: `evidence.shared_hosts[].host`; both include `overlap_intervals`. Fingerprint: `evidence.shared_hosting_asns`. Keys should not change without notice. | Needs pivot developers |

## Recall levels (decision 2)

For a seed from actor A, recall can be measured against three answer sets:

1. **All other A domains.** Includes domains with no DNS observations, which no
   method can find.
2. **Observed A domains** (headline). Excludes domains with no observations.
3. **One-hop reachable A domains.** Observed A domains that share at least one
   of A's IPs, NS hosts, or MX hosts with the seed during overlapping dates, per
   ground truth. This is the most an ideal one-hop shared-infrastructure pivot
   could find, so recall here measures the pivot itself rather than the data.

The gap between levels 2 and 3 shows how much is lost to one-hop search and the
overlap requirement. CDN-fronted domains are also reported as their own subgroup.

Current dataset, measured from ground truth by evaluation only:

| Actor | Domains | Observed | CDN-fronted | Average one-hop reachable share | Largest group linked through any number of hops |
|---|---|---|---|---|---|
| AMBER_KITE | 31 | 31 | 1 | 14% | 26 |
| SLATE_HERON | 27 | 25 | 5 | 5% | 9 |

The ceiling figures are evaluation context. Using them to redesign or tune the
pivots would leak ground truth into the engine.

## Filter conditions (decision 4)

Each is reported under its own name and never mixed with the others.

- **no-filter:** every IP/NS/MX value labeled `candidate`. Lower bound.
- **perfect-filter:** labels mapped from ground truth by decision 5. Upper bound.
  Evaluation-only; must not be used to tune the filter or pivots.
- **real-filter:** the filter's `output/infra_labels.json`, added when it exists.
- **mock:** the files in `examples/`. Smoke tests only; not reported as results.

`temporal_behavior` ignores labels, so its results are identical in every
condition.

## Result-list cutoff (decision 6)

Methods return very different list lengths. In a spot check of one seed per actor
under no-filter, IP co-residency returned 12 and 61 candidates, fingerprint
matching about 250, and temporal behavior about 4,400 (nearly every observed
domain). Precision over the full list therefore mostly reflects list length.

Primary metrics, per seed and method:

- Average precision over the ranked list.
- Precision and recall among the top k results, k = 5, 10, 25. Twenty-five is
  roughly one actor's size.
- Ties in score are broken by candidate name so rankings are deterministic.

Secondary: precision, recall, and result count over the full returned list.

## Other metrics

- Benign and crimeware seeds: number of actor domains in the top 25 and in the
  full list (ideally 0), and total results returned.
- Method overlap: true positives found by only one method.
- Threshold sweeps: `max_domain_count` for NS/MX and score cutoffs per method.
  Separate precision–recall curve per method, since scores mean different things.
- Evidence correctness: share of IP and NS/MX true positives whose shared IP or
  host appears in that actor's `ips`, `ns_hosts`, or `mx_hosts`.
- Forward vs. passive (optional, decision 10): run pivots on `load_resolutions(source="forward")` and on
  `source="passive"`. Compare recall, and for each true positive, the earliest
  overlap start date under each source (lead time in days).

## Outputs

Written under `output/eval/` (Git-ignored): the combined `pivot_results.jsonl`
per run, a per-seed metrics table, a summary metrics file with the run
configuration, and plots. Each method call takes 0.01 to 0.25 seconds, so the
core run (196 seeds, four methods, two filter conditions) takes about 3 minutes;
adding the forward-only and passive-only runs brings it to about 10 minutes.

## Known limits

- Two actor profiles only. Comparing methods as actors get stealthier needs more
  simulator scenarios.
- Pivots search one hop from the seed and accept only domain seeds.
- Pivots have no historical cutoff mode; lead time is measured from evidence
  dates in the full history.
- Scores are heuristic evidence strengths, not probabilities of maliciousness.
- The synthetic data is smaller and less varied than real passive DNS (19 ASNs,
  11 registrars, at most a few hundred domains per IP or host).
