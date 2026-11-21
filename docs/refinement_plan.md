# Pivot refinement: baseline and comparison plan

## Current checkpoint

Andrew's branch now includes the fetched main commit `84f0340`. The update adds
fingerprint matching, temporal matching, evaluation, plotting, a simulator, and
data validation. At that unmodified checkpoint the suite passed **33 tests**, and the committed
development dataset passes `validate_data.py`.

The first refinement is now complete: see the
[registration-period refinement report](fingerprint_refinement.md) for the
implementation, paired results, graphs, CSVs, and exact commands. Fingerprint
ranking declined in the no-filter benchmark despite correcting mixed-period
evidence; unchanged methods and the perfect-filter metrics stayed unchanged.

The subsequent [temporal experiment and validation](temporal_refinement.md)
compares A/AAAA hosting timelines against the fingerprint-corrected checkpoint,
with fixed weights and three preselected fresh simulation worlds.

Andrew selected All-DNS with the fingerprint fix for handoff. See the
[final implementation guide](final_handoff.md) for verification and saved results;
the hosting-only variant remains an archived experiment.

The original checkpoint below preserves and reviews the implementation before
algorithm refinement. A before/after result must come from two actual runs; an
existing method-comparison plot is not evidence of improvement over time.

## Frozen baseline

Baseline artifacts are under `output/refinement/before-84f0340/`:

- `baseline_manifest.json`: original commit, source/data hashes, and command.
- `source.zip`: evaluator, plotting, loader, pivot methods, and tests before any
  refinement. This supports reproducing the old methods after source changes.
- `per_seed.jsonl` and `summary.json`: the evaluator's measurements.
- `no_filter/` and `perfect_filter/`: raw contract-format method results,
  losslessly archived as `pivot_results.jsonl.gz` after evaluation.
- `figures/`: the existing plotting script's graphs and comparison CSV.

The baseline directory is generated output and is ignored by Git. Keep it as a
separate run; do not reuse it for refined outputs. A future run should use a
different directory such as `output/refinement/after-<revision>/`.
The manifest records compressed artifact hashes and uncompressed raw-result
hashes. Standard gzip decompression restores the original JSONL bytes. Plotting
reads the small summary/per-seed files and does not need raw results decompressed.

Commands from the repository root:

```sh
python3 -m unittest discover -s tests -p '*.py' -v
python3 validate_data.py

python3 -m evaluation.evaluate \
  --output-dir output/refinement/before-84f0340

MPLCONFIGDIR=/private/tmp/netsec-matplotlib python3 -m evaluation.plot_accuracy \
  --eval-dir output/refinement/before-84f0340 \
  --output-dir output/refinement/before-84f0340/figures
```

The evaluation and plotting commands replace files at their chosen destinations.
The baseline shown above was generated before changing pivot behavior. The
recorded commit, archived sources, and manifest identify that implementation;
running the same command against later code does not recreate the baseline.

## Baseline measurements

No-filter condition, means over actor seeds with actors weighted equally.
These are measurements before any refinement, not before/after improvements.

| Method | Average precision | Precision@10 | Recall@25 | Mean candidates |
| --- | --- | --- | --- | --- |
| `ip_coresidency` | 0.0124 | 0.0512 | 0.0192 | 138.7 |
| `ns_mx_reuse` | 0.0000 | 0.0000 | 0.0000 | 0.1 |
| `fingerprint_match` | 0.1419 | 0.3040 | 0.1814 | 1235.6 |
| `temporal_behavior` | 0.0289 | 0.0595 | 0.0617 | 4121.2 |
| `combined_rrf` | 0.1184 | 0.2702 | 0.1567 | 4220.6 |
| `combined_max` | 0.0862 | 0.1809 | 0.0957 | 4220.6 |

The fixed sample contains 56 observed actor seeds, 100 benign seeds, and 40
crimeware seeds. Fingerprinting has the strongest ranking metrics here;
combining every method does not automatically improve on the best individual
method. Temporal matching retrieves many candidates, while NS/MX contributes
no same-actor discoveries under the default benchmark. These outcomes motivate
controlled experiments; they do not justify actor-specific threshold tuning.

The perfect-filter run is an oracle control, not a guarantee that every metric
will be numerically higher. Keep its results separate from realistic filtering.

## What is implemented now

| Method | Current rule | Review target |
| --- | --- | --- |
| IP co-residency | Same eligible IP with overlapping dates; rank by capped duration | Domain count is evidence but does not influence ranking |
| NS/MX reuse | Exact eligible host, overlapping dates, at most 10 observed domains | Study the rarity/overlap trade-off without choosing thresholds from planted actor identities |
| Fingerprint | Shared hosting ASN, with registrar/aging similarities affecting score | Keep registration-period features consistent; a shared ASN currently qualifies even with no other matching features |
| Temporal | Similar All-DNS timelines using A, AAAA, NS, and MX | Selected for handoff; preserve hosting-only results as a measured alternative |

The evaluator adds reciprocal-rank fusion (`combined_rrf`) and a maximum-score
combination (`combined_max`). These must be rerun after changing any constituent
method. Scores have different meanings; raw score magnitude is not a calibrated
cross-method confidence measure.

## Findings checked without the answer key

### Registration-period mixing

The baseline `pivot/fingerprint_match.py` selected the registrar and aging date at the earliest
eligible IP observation, but unions hosting ASNs across all observations of the
domain. On a controlled example with an old registration using ASN 1 and a later
registration using ASN 2, the method returned a score of **1.0** for a candidate
using ASN 2 and the old registrar. That combination never occurred together for
the seed during one registration period.

The completed first refinement searches all historical episodes and compares
complete episode pairs. Controlled regression tests precede the change; the
report above records the measured effect without changing score weights.

### DNS timeline versus hosting timeline

The pre-experiment temporal method unions A, AAAA, NS, and MX observation intervals into
one activity timeline. A controlled pair with non-overlapping A-record activity
but year-long NS records received score **1.0** and 365 days of DNS overlap.
This follows the current definition, but it does not establish overlapping
hosting activity.

Compare an explicitly defined hosting timeline with the current all-DNS
timeline as an experiment. Preserve NS/MX timing as separate evidence when
useful. This is a modeling hypothesis, not a claim that the current metric
miscalculates its stated all-DNS overlap.

### Ranking breadth and parameter changes

IP scores currently depend only on the strongest shared IP's overlap duration.
A long overlap on widely shared infrastructure can outrank a shorter overlap on
rare infrastructure in the no-filter condition. A rarity-aware ranking is a
reasonable controlled experiment, with a test demonstrating the intended
ordering. Preserve the candidate-generation rule while testing ranking changes
so their effects can be distinguished.

NS/MX's limit of 10 and strict overlap requirement are existing design choices,
not implementation errors. Any generic parameter sweep must be specified in
advance and report false leads as well as recovered positives. Do not select a
cutoff to match the hidden actors' known infrastructure sizes.

## Before/after experiment rules

1. Preserve the baseline and fix the definition of each proposed change before
   inspecting its evaluation results. Add controlled tests for both new methods;
   the baseline suite directly covered IP, NS/MX, and evaluation. Fingerprint
   and temporal methods now both have dedicated regression coverage.
2. Change one concept at a time. Record an ablation for each change before a
   combined refined version so discussion can connect outcomes to code changes.
3. Use identical observations, domain metadata, filter conditions, benchmark
   seeds, top-k values, method parameters, and aggregation for each paired run.
   Record source revision/hashes with every output. Changed parameters are a
   separate experiment, not a hidden difference between versions.
4. Use no-filter or real inferred labels for selecting refinements. The perfect
   filter is an evaluation-only oracle condition and must not guide tuning.
   Temporal currently ignores labels, so its results should be identical across
   these filter conditions for a fixed implementation.
5. Repeat the chosen changes on independently generated datasets written to new
   directories. Keep the delivered data intact. Fresh random worlds using the
   same actor profiles test simulation variability, not unseen-actor generality.
6. Compare identical seed keys and report improvements, regressions, and no
   change. Two planted actors and correlated seeds do not justify claims about
   real APT performance or broad statistical significance.

## Discussion artifacts to produce after refinement

- A CSV with condition, method, metric, before value, after value, and absolute
  delta. Use the evaluator's actor-balanced aggregate consistently.
- Paired bars for average precision, Precision@10, and Recall@25.
- Before/after false-lead bars for benign and crimeware seeds, together with
  candidate-list size, so aggressive pruning is not mistaken for a free gain.
- Per-actor/per-seed deltas and ablation tables to show uneven effects hidden by
  averages. Confidence intervals, if added, must respect the sampling structure.
- A short discussion connecting each result to the algorithm, including the
  limitations of synthetic data and oracle filtering.

The existing `evaluation/plot_accuracy.py` reads one run. The new
`evaluation/compare_runs.py` pairs two provenance-checked runs and rejects
mismatched configurations or seed sets before drawing before/after charts.
Keep the original baseline method-comparison figures distinct from these
paired before/after figures.

## Documentation discrepancies found during review

- `evaluation/README.md` still describes older two-method results and says plots
  are not implemented, although main now contains four methods and plotting.
- The evaluator's optional-import comments still refer to Rick's methods being
  on a separate branch; they are now present on main.
- `load_data.PIVOT_METHODS` includes `temporal_behavior`, while the version 0.1
  Markdown contract lists three method names. Reconcile the documentation with
  the team before treating this as a contract revision.
