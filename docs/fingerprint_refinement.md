# Registration-period fingerprint refinement

The first refinement milestone fixes a correctness problem in fingerprint
evidence and measures its effect. Registrar, hosting ASN, and first-use aging
now come from the same registration period. On the fixed synthetic benchmark,
ranking quality declined in the no-filter condition. This is a correctness fix
with a measured ranking regression, not evidence of improved detection accuracy.

## What changed

Previously, a domain's earliest eligible IP observation supplied its registrar
and aging date, while hosting ASNs were collected across its entire history.
An old registrar could therefore be combined with a later owner's ASN.
In a controlled regression fixture, this invented combination scored `1.0`.
With complete registration periods, its best valid comparison scores `0.75`.

`pivot/fingerprint_match.py` now:

1. Reads valid registration periods, normalizes registrar names, removes exact
   duplicate periods, and orders them deterministically. Top-level registration
   fields remain supported when no registration history is supplied.
2. Intersects each eligible A/AAAA observation with each registration period.
   Observations in registration gaps contribute nothing. Registration and expiry
   dates are inclusive; an absent expiry leaves the period open-ended.
3. Collects hosting ASNs and the earliest intersecting observation separately
   for each period. Aging is elapsed days from registration to this clipped
   observation start: same-day use has age zero. It is not DNS TTL.
4. Searches **all historical period pairs**, preserving historical discovery.
   Each candidate retains its strongest complete pair. Equal rounded scores
   keep the first pair in chronological order. Seed and candidate periods do
   not have to overlap: this is feature similarity, not IP co-residency.

The scoring formula remains:

```text
shared hosting ASN required
aging_similarity = max(0, 1 - abs(seed_age - candidate_age) / 365)
score = 0.5 + (0.25 if registrar matches else 0) + 0.25 * aging_similarity
```

Scores are heuristic evidence strengths, not maliciousness probabilities.
Infrastructure must have an explicit `candidate` filter label; missing labels
and missing ASN/registration information cannot supply a fingerprint. Missing
registrars receive no registrar bonus. Invalid registration periods are skipped.
IPv6, original seed spelling, self-exclusion, and deterministic output remain
supported. IP seeds remain unsupported.

The public callable, CLI, method name, and top-level result fields are unchanged.
Existing evidence fields remain; each selected fingerprint additionally includes
`registration_expired`, and `period_policy` explains historical-pair selection.
`first_ip_observation_start` now explicitly means the start clipped to the
selected period. Evidence reports the selected pair rather than a union of
features from different owners.

## Experiment controls and measured results

The preserved baseline is the clean `84f0340` implementation. The refined run
uses the same delivered data, evaluation code, loader, parameters, seed identities,
and two filter conditions. Of the pivot methods, only fingerprint matching
changed. Both combined rankings were recomputed from all four methods.

There are 196 seeds: 56 observed actor domains, 100 deterministically sampled
benign domains, and 40 crimeware domains. Four methods plus two combinations,
under two conditions, produce 2,352 per-seed metric rows. The NS/MX limit remains
10, the sampling seed is 6262, and reciprocal-rank fusion uses constant 60.
Ground truth is used only by evaluation; the fix was specified using controlled
fixtures, without inspecting planted labels or tuning thresholds to them.

No-filter measurements below average seeds within each actor and then weight
the two actors equally. Values come from the evaluator's four-decimal summaries.

| Ranking | AP before → after | Precision@10 before → after | Recall@25 before → after |
| --- | --- | --- | --- |
| Fingerprint | 0.1419 → 0.1300 | 0.3040 → 0.2739 | 0.1814 → 0.1683 |
| Combined RRF | 0.1184 → 0.1135 | 0.2702 → 0.2610 | 0.1567 → 0.1502 |
| Combined max | 0.0862 → 0.0861 | 0.1809 → 0.1809 | 0.0957 → 0.0957 |

For fingerprint matching, Precision@10 falls by **3.01 percentage points** and
Recall@25 by **1.31 percentage points**. Full-list observed recall stays at
`0.5771`, and mean candidates per actor seed stay at `1235.5871`. Combined
observed recall stays at `0.9029`, with `4220.6393` mean candidates. The recorded
effect is on ranking rather than a change in these retrieval totals.

False leads show a trade-off. Fingerprint matching returns a mean `0.34 → 0.40`
actor domains in benign seeds' top 25, while crimeware seeds fall from
`1.95 → 1.80`. These count actor-domain false associations from non-actor seeds;
they are not an overall false-positive rate. The complete tables also include
per-actor and per-seed measurements so averages do not hide uneven effects.

Every per-seed metric for IP co-residency, NS/MX reuse, and temporal behavior is
unchanged. Every perfect-filter per-seed metric is unchanged. The perfect filter
is an evaluation-only oracle control, not evidence that an implemented filter
achieves these outcomes; temporal matching still ignores filter labels.

The results support saying: **registration-consistent evidence is more faithful
to the input history, but the unchanged scoring formula ranks the observed
positives less effectively in this benchmark.** The experiment does not isolate
why that score behaves this way. A future scoring experiment should be specified
separately and validated on independent datasets, rather than adjusting this
correctness fix until its benchmark improves.

## Code and artifact responsibilities

| File | Responsibility |
| --- | --- |
| `pivot/fingerprint_match.py` | Period construction, feature clipping, complete-pair matching and evidence |
| `tests/fingerprint_match.py` | Nine controlled regression and CLI tests |
| `evaluation/evaluate.py` | Existing benchmark, metrics, and combined rankings; unchanged |
| `evaluation/run_experiment.py` | Runs that evaluator in a fresh directory and records source/data/metric hashes |
| `evaluation/compare_runs.py` | Checks paired runs, exports deltas, and draws three comparison figures |
| `tests/compare_runs.py` | Comparison failure cases and a tiny end-to-end experiment-wrapper check |
| `load_data.py` | Existing shared JSON/JSONL I/O; unchanged |

Saved runs and discussion artifacts:

- Baseline: `output/refinement/before-84f0340/`.
- Refined run: `output/refinement/after-registration-periods/`.
- Comparison: `output/refinement/registration-period-comparison/`.

The comparison directory contains:

| File | Contents |
| --- | --- |
| `metric_deltas.csv` | 624 condition/method/group/metric rows, including actor-balanced overall means |
| `per_seed_deltas.csv` | 15,344 paired metric rows, retaining seed and group identities |
| `ranking_before_after.png` | AP, Precision@10 and Recall@25, with separate filter-condition panels |
| `false_leads_before_after.png` | Mean actor-domain false leads for benign and crimeware seeds |
| `candidate_counts_before_after.png` | Mean candidate counts for actor seeds |
| `comparison.json` | Input run paths, row counts, and delta convention |

Every delta is **after minus before**. Positive ranking deltas are better;
positive false-lead deltas are worse. Candidate count alone has no preferred
direction. Undefined values stay null in JSON and empty in CSV. CSV deltas use
the stored numeric values; normal floating-point representations can include
extra digits.

Manifests check configurations, exact per-seed identities, dataset and opaque
answer-key hashes, unchanged loader/evaluator code, and metric-file checksums.
They also record source hashes and a ZIP snapshot. The post-run manifest names
the base commit and explicitly records uncommitted changes; the base commit
alone does not identify the refined code. Supporting comparison/runner files
were finalized after measurement; the measured pivot, loader, and evaluator
hashes were checked unchanged when refreshing that snapshot.

Raw results in the two saved runs are losslessly compressed as
`<condition>/pivot_results.jsonl.gz`; their manifests record compressed and
uncompressed checksums. Summary comparisons do not require decompression.
These generated directories are ignored by Git. Share the artifacts separately
with teammates, or regenerate them; committing the source and this report alone
does not distribute the generated CSVs and figures.

## Setup, run, and verify

Use Python 3.11 or newer from the repository root. The methods, evaluator,
experiment wrapper, CSV comparison, and tests use the standard library.
Rendering comparison graphs additionally needs the project's existing
Matplotlib dependency:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install matplotlib
```

Run the controlled checks and validate the delivered development dataset:

```sh
python3 -m unittest discover -s tests -p '*.py' -v
python3 validate_data.py
```

The suite passes **53 tests**. Fingerprint coverage includes period mixing on
both sides, historical matches, boundary clipping, gaps, inclusive expiry,
IPv6, missing metadata, excluded infrastructure, duplicates, stable ties, and
CLI output. Comparison tests check mismatched data, answer-key hashes, optional
filter-label hashes, settings, evaluator code, seed identity, missing/duplicate
rows, edited metrics, undefined values, and unfavorable deltas.

To rerun the current implementation, choose a **new** output directory:

```sh
python3 -m evaluation.run_experiment \
  --output-dir output/refinement/after-registration-periods-rerun
```

The wrapper refuses an existing directory. It uses the evaluator's usual
defaults; `--data-dir`, `--truth-dir`, `--labels`, `--max-domain-count`,
`--benign-sample`, and `--random-seed` remain configurable. Existing saved runs
already contain the completed benchmark; no rerun is needed to redraw figures.
To reproduce the old behavior, use the preserved baseline sources in a separate
checkout or temporary copy. Running today's code with the old output path does
not reproduce the baseline.

Generate the comparison from the two saved runs:

```sh
MPLCONFIGDIR=/private/tmp/netsec-matplotlib \
XDG_CACHE_HOME=/private/tmp/netsec-fontcache \
python3 -m evaluation.compare_runs \
  --before output/refinement/before-84f0340 \
  --after output/refinement/after-registration-periods \
  --output-dir output/refinement/registration-period-comparison
```

The cache variables are useful in restricted environments and can be omitted
when the normal Matplotlib cache is writable. The command replaces comparison
files, refuses output within either preserved run, and reads metrics only.

## Limits of this milestone

This is one delivered synthetic dataset with two actors and correlated seeds;
there is no independent-world replication, significance claim, or evidence of
real-world APT accuracy. Registration intervals are interpreted as supplied;
coarse first/last-seen observations spanning a gap do not prove continuous DNS
activity. Searching all historical periods can connect different eras and is
explicit in evidence. The score still permits a shared ASN to qualify without
registrar agreement. Real filter integration, temporal-method refinement, IP
seeds, discovery cutoffs, and new scoring experiments remain separate work.
