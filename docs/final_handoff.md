# Final implementation handoff

Andrew's implementation work is complete for this handoff. The selected version
uses **All-DNS temporal matching plus the registration-period fingerprint fix**.
The hosting-only experiment remains archived with its measured results.

## Selected behavior

| Method | Behavior |
| --- | --- |
| IP co-residency | Exact eligible IP sharing during overlapping intervals; unchanged |
| NS/MX reuse | Exact uncommon eligible host sharing during overlapping intervals; unchanged |
| Fingerprint | Compare complete historical registration periods; retain the strongest pair |
| Temporal | Compare activity timelines built from A, AAAA, NS, and MX observations |
| Combined rankings | Existing reciprocal-rank fusion and maximum-score combination; unchanged |

Temporal overlap means **observed DNS presence**, including NS/MX-only domains.
It does not establish simultaneous hosting or common ownership. Long-lived
NS/MX records can dominate a timeline. The temporal method ignores filter
labels; the other three methods require explicitly eligible infrastructure.
All scores are heuristic strengths, not calibrated maliciousness probabilities.

Intervals use inclusive days and preserve gaps. Duplicate source observations
do not double-count total active days; per-source coverage is retained.
Temporal `record_count` counts raw observations, including duplicates, and does
not affect its score. Domain seeds are supported; IP seeds are rejected.

Public callables, CLI arguments, and top-level result fields are unchanged.
File I/O remains in `load_data.py`. No experimental runtime selector or new
dependency was added.

## Verification and selected results

- All **66 controlled tests pass**, including eight tests for the selected
  All-DNS behavior and nine fingerprint registration-period regressions.
- `validate_data.py` passes for the delivered development dataset.
- Every pivot source, common helper, shared loader, and evaluator matches the
  previously measured fingerprint-corrected All-DNS checkpoint byte for byte.
- The actual temporal CLI for `agent-help7.org` produces all **4,429** results
  with identical scores, evidence, and ordering to that saved checkpoint.
- The delivered input hashes and prior research artifacts are preserved.

Consequently, the final checkpoint reuses verified existing measurements; it
does not claim a new full benchmark run. Its manifest distinguishes the final
source snapshot from the original measured source archive.

Delivered dataset, no-filter condition, actor-balanced means:

| Method | AP | Precision@10 | Recall@25 | Observed recall |
| --- | --- | --- | --- | --- |
| IP co-residency | 0.0124 | 0.0512 | 0.0192 | 0.0578 |
| NS/MX reuse | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Fingerprint | 0.1300 | 0.2739 | 0.1683 | 0.5771 |
| Temporal | 0.0289 | 0.0595 | 0.0617 | 0.7696 |
| Combined RRF | 0.1135 | 0.2610 | 0.1502 | 0.9029 |
| Combined max | 0.0861 | 0.1809 | 0.0957 | 0.9029 |

Higher is better for these four metrics. Lower false-lead counts are better.
Candidate-list size alone has no preferred direction.

## Setup and commands

Use Python 3.11 or newer from the repository root. Methods, evaluation, and
tests use the standard library. The existing overview plotting script needs
Pandas and Matplotlib; the paired-comparison plots need Matplotlib.

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install pandas matplotlib

python3 -m unittest discover -s tests -p '*.py' -v
python3 validate_data.py

python3 -m pivot.temporal_behavior agent-help7.org \
  --output output/handoff-demo/temporal_results.jsonl
```

For a new complete benchmark, use an output directory that does not exist:

```sh
python3 -m evaluation.run_experiment --output-dir output/handoff-recheck
python3 -m evaluation.plot_accuracy \
  --eval-dir output/handoff-recheck --output-dir output/handoff-recheck/figures
```

The wrapper refuses existing run directories. Existing saved metrics are enough
to regenerate the chosen version's figures without another benchmark:

```sh
python3 -m evaluation.plot_accuracy \
  --eval-dir output/refinement/final-all-dns \
  --output-dir output/refinement/final-all-dns/figures
```

Use the existing mock-label examples only for labeled method smoke tests, as
described in the root README. The real filter's `output/infra_labels.json` is
absent from this checkout. Benchmark no-filter and perfect-filter conditions
are explicit evaluation controls; neither demonstrates a working real filter.

## Results and research references

| Version | Saved measurements | Interpretation |
| --- | --- | --- |
| Original main `84f0340` | `output/refinement/before-84f0340/` | Unrefined baseline |
| **Selected All-DNS + fingerprint fix** | `output/refinement/final-all-dns/` | Verified reuse of `after-registration-periods/` results |
| Hosting-only + fingerprint fix | `output/refinement/temporal-validation/delivered-after/` | Experimental alternative, not the current default |
| Fresh-world comparisons | `output/refinement/temporal-validation/worlds/<seed>/{before,after}/` | Before = selected All-DNS; after = hosting-only |

The final directory contains `summary.json`, `per_seed.jsonl`,
`run_manifest.json`, final `source.zip`, original `measured_source.zip`, and
`figures/` with four plots plus `method_comparison.csv`. The handoff archive
`output/refinement/final-all-dns-handoff.zip` bundles the selected source,
documentation, and small result/figure artifacts for sharing. Large raw result
archives, simulation datasets, and actor recipes are excluded. These generated
files are Git-ignored and must be shared separately from source changes.
Unpack the bundle into an existing shared-repository checkout; it is an overlay,
not a replacement for the delivered data or simulator inputs. Selected figures
can be redrawn from its metrics without rerunning evaluation. Complete historical
simulation reproduction additionally needs the preserved simulation-source archive
referenced by the temporal report; that archive contains actor recipes and is
not included in the compact bundle.

Use these reports when writing:

- [Fingerprint correctness fix](fingerprint_refinement.md): valid registration
  evidence, with a ranking regression on the delivered dataset.
- [Temporal experiment](temporal_refinement.md): the three fresh-world pairs
  support retaining All-DNS for this PoC, with mixed effects across metrics.
- [Baseline and research plan](refinement_plan.md): original measurements and
  experimental controls.
- [Evaluation guide](../evaluation/README.md): metric definitions and settings.

The fresh-world experiments compare the selected version with hosting-only;
they do not independently repeat the original-versus-fixed fingerprint study.
The original experiment archives and tables are preserved. Historical
hosting-only reproduction uses archived source, because today's default is
All-DNS. World summaries need the public dataset manifests at their recorded
paths; exported CSVs/PNGs and paired metric comparisons can be shared directly.

## Remaining team work

The handoff is for implementation and research evidence. Teammates can now
prepare the paper, slides, and demonstration. Team decisions still include
real-filter integration, whether domain-only scope is sufficient, and whether
forward-versus-passive discovery timing is required by the rubric. Historical
cutoffs, IP seeds, live providers, and certificate metadata are unfinished
extensions. The delivered data is synthetic with two actor profiles; three
fresh worlds test simulation variability, not real-world APT generality.

Changes remain local and uncommitted on Andrew's branch. No merge or push is
part of this handoff. Stop implementation here unless further work is assigned.
