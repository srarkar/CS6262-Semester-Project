# Temporal hosting-activity experiment

**Handoff selection:** All-DNS temporal matching has been restored, retaining
the fingerprint fix. This report describes the archived hosting-only experiment;
its algorithm and results below are not the current default. See the
[final handoff guide](final_handoff.md) for the selected implementation and checks.

## Fixed experiment definition

This milestone compares temporal matching over **A/AAAA observations only** with
the existing timeline that includes A, AAAA, NS, and MX. Long-lived name-server
or mail records can overlap even when the domains' observed hosting periods do
not. The hypothesis is that an explicit hosting timeline gives more useful
similarity evidence. It does not assume higher benchmark accuracy.

The following choices were fixed before evaluating the change:

- Baseline: the fingerprint-corrected source snapshot in
  `output/refinement/after-registration-periods/source.zip`.
- Change only temporal record selection. Keep its five score weights, overlap
  requirement, source handling, other pivot methods, and evaluation unchanged.
- Require at least one A/AAAA observation for a temporal profile. NS/MX-only
  domains have no hosting profile and return no temporal matches.
- Keep inclusive interval endpoints, disjoint intervals, duplicate-source
  merging, IPv6, deterministic ordering, and domain-only seed behavior.
- Retain label-independent temporal matching. A/AAAA selection is not a noise
  filter: parking, CDN, and sinkhole IP observations can still contribute.
- Run the delivered seed-6262 dataset as the development comparison.
- Validate on three fresh simulation worlds: **6263, 6264, and 6265**, with
  default 5,000 benign domains, 40 crimeware domains, and unchanged actor inputs.
- Within each world, pair exactly the same seeds and data, with benign sample
  100, sampling seed 6262, NS/MX limit 10, top-k 5/10/25, and RRF constant 60.
- Report AP, Precision@10, Recall@25, observed recall, candidate counts, and
  non-actor false leads. Recompute both combinations. Keep no-filter and
  perfect-filter results separate; the latter is an evaluation-only oracle.
- Do not tune weights, replace validation worlds, or select a variant based on
  their results. Same-profile simulation worlds test random-world variability,
  not unseen actors or real DNS performance.

The stopping point is a documented, verified comparison and a recommendation
for the presentation. Additional scoring variants, filter integration, IP
seeds, and slide creation require a subsequent milestone or team decision.

## Algorithm and evidence

In the archived experiment, the public callable remains
`find_temporal_matches(seed, resolutions)`. Input
records are validated as before; only A/AAAA records enter a hosting profile.
The function remains independent of registrar, ASN, and filter labels.

For each domain it merges overlapping hosting intervals without filling gaps.
Days are inclusive: January 1–10 is ten active days. Overlapping forward and
passive observations count once in total activity; each source retains its own
coverage days. The raw `record_count` still counts input observations, including
duplicates, and is not a score feature. Profiles report hosting-only first/last
seen, active days, span, largest gap, source coverage, and distinct IP count.

A candidate needs at least one overlapping hosting day, but does not need to
share the seed's IP. The unchanged heuristic is:

```text
0.55 * temporal Jaccard similarity
+ 0.15 * observed-span similarity
+ 0.10 * activity-density similarity
+ 0.10 * source-mix similarity
+ 0.10 * distinct-IP-count similarity
```

This is a similarity strength, not a probability of maliciousness. Hosting
observations include all recorded IP use, including possible parking or CDN
use; they do not establish operational attacker activity. `activity_basis` is
added to evidence as `A/AAAA observations only`. Existing evidence keys and
top-level result fields remain unchanged. NS/MX reuse remains a separate method.

This is a change in what temporal similarity measures, rather than a claim
that the baseline miscomputed all-DNS overlap. In a controlled example with
January hosting for one domain, February hosting for another, and year-long
NS/MX observations for both, the baseline reports 365 overlap days and score
`1.0`; the hosting-only version returns no match. For two ten-day hosting
periods overlapping by five days, both versions give `0.633333` when there are
no NS/MX records. These fixtures establish behavior without an answer key.

## Files and saved artifacts

| File | Responsibility |
| --- | --- |
| `pivot/temporal_behavior.py` | Current All-DNS implementation; hosting-only source is preserved in the experiment archives |
| `tests/temporal_behavior.py` | Eight current All-DNS regression tests; experimental tests remain in the source archives |
| `evaluation/run_experiment.py` | Existing source/data snapshots and benchmark execution |
| `evaluation/compare_runs.py` | Existing paired-run checks, CSVs, and three before/after graphs |
| `evaluation/summarize_worlds.py` | Checks implementations and controls across worlds; exports equally weighted world summaries |
| `tests/summarize_worlds.py` | Five checks for aggregation, undefined values, world identity, and changed controls |

Artifacts are under `output/refinement/temporal-validation/`:

- `experiment_plan.md` and `validation_manifest.json` preserve the initial
  experiment definition, selected worlds, baseline archive hash, and opaque
  simulation-input hashes. `simulation_source.zip` preserves the generator,
  shared loader, and unchanged actor inputs for simulation reproduction.
- `before-source/` contains the verified fingerprint-corrected baseline source.
- `delivered-after/` and `delivered-comparison/` hold the development run and its
  comparison against `output/refinement/after-registration-periods/`.
- `worlds/<seed>/` holds isolated `data_public/`, evaluation-only `data_truth/`,
  `before/`, `after/`, `comparison/`, and execution logs for each fresh world.
- `summary/` contains `world_metric_deltas.csv`, `replication_summary.csv`,
  `replication_summary.json`, and `replication_deltas.png`.

Saved raw results are losslessly compressed as
`<condition>/pivot_results.jsonl.gz`; manifests record compressed artifact
hashes and verified uncompressed hashes and sizes. The rerun commands below
produce the evaluator's usual uncompressed JSONL. Metric comparisons use
`summary.json` and `per_seed.jsonl`, so neither form needs decompression.

`analysis_source.zip` and the final analysis hashes in `validation_manifest.json`
identify the comparison tools used for the final figures and tables. Benchmark
source snapshots retain the code as it stood during measurement. A final
summary-guard change detects undefined-to-defined control metric changes; it
does not change pivot behavior, evaluation, or any measured values.

Each world is paired internally; domains are not paired across different
worlds. Summary means give each world equal weight, after the evaluator's
equal-actor averaging. `delta = after - before`; undefined values remain empty
or null. `delta_min` and `delta_max` describe observed variation across the three
worlds, not confidence intervals. Ranking plots show positive deltas as better;
positive false-lead deltas are worse. All generated artifacts are Git-ignored.
World summarization also reads the public dataset manifest at its recorded
path; preserve those locations when rerunning that command. The paired
comparison command reads the metric artifacts only.

## Reproduction from the repository root

Use Python 3.11 or newer and the existing Matplotlib dependency for figures.
No new dependencies were added. Activate the project's virtual environment if
used, then run:

```sh
python3 -m unittest discover -s tests -p '*.py' -v
python3 validate_data.py
```

The following commands reproduce the archived experiment using both preserved
implementations, leaving delivered data and saved runs intact. Choose
another destination if `temporal-rerun` already exists; the run wrapper refuses
existing run directories.

```sh
temporal_run_dir="$(pwd)/output/refinement/temporal-rerun"
mkdir -p "$temporal_run_dir/before-source" "$temporal_run_dir/after-source" \
  "$temporal_run_dir/simulation-source"
python3 -m zipfile -e output/refinement/after-registration-periods/source.zip \
  "$temporal_run_dir/before-source"
python3 -m zipfile -e output/refinement/temporal-validation/analysis_source.zip \
  "$temporal_run_dir/after-source"
python3 -m zipfile -e output/refinement/temporal-validation/simulation_source.zip \
  "$temporal_run_dir/simulation-source"

python3 -m evaluation.compare_runs \
  --before output/refinement/after-registration-periods \
  --after output/refinement/temporal-validation/delivered-after \
  --output-dir "$temporal_run_dir/delivered-comparison"

for temporal_world_seed in 6263 6264 6265; do
  temporal_world_dir="$temporal_run_dir/worlds/$temporal_world_seed"
  python3 "$temporal_run_dir/simulation-source/sim/simulate.py" \
    --seed "$temporal_world_seed" \
    --public-out "$temporal_world_dir/data_public" \
    --out "$temporal_world_dir/data_truth"
  python3 validate_data.py "$temporal_world_dir/data_public"
  (
    cd "$temporal_run_dir/before-source" || exit 1
    python3 -m evaluation.run_experiment \
      --data-dir "$temporal_world_dir/data_public" \
      --truth-dir "$temporal_world_dir/data_truth" \
      --output-dir "$temporal_world_dir/before"
  )
  (
    cd "$temporal_run_dir/after-source" || exit 1
    python3 -m evaluation.run_experiment \
      --data-dir "$temporal_world_dir/data_public" \
      --truth-dir "$temporal_world_dir/data_truth" \
      --output-dir "$temporal_world_dir/after"
  )
  python3 -m evaluation.compare_runs \
    --before "$temporal_world_dir/before" --after "$temporal_world_dir/after" \
    --output-dir "$temporal_world_dir/comparison"
done

python3 -m evaluation.summarize_worlds \
  --runs-root "$temporal_run_dir/worlds" --worlds 6263 6264 6265 \
  --output-dir "$temporal_run_dir/summary"
```

In a restricted environment, set `MPLCONFIGDIR=/private/tmp/netsec-matplotlib`
and `XDG_CACHE_HOME=/private/tmp/netsec-fontcache` before graph commands.
To redraw the saved validation figure without rerunning experiments:

```sh
python3 -m evaluation.summarize_worlds \
  --runs-root output/refinement/temporal-validation/worlds \
  --worlds 6263 6264 6265 \
  --output-dir output/refinement/temporal-validation/summary
```

## Results and stopping point

### Delivered dataset (development comparison)

The before version is the fingerprint-corrected checkpoint, not the original
unrefined main commit. These no-filter values use equal-actor averaging:

| Method | AP before → after | Precision@10 before → after | Recall@25 before → after |
| --- | --- | --- | --- |
| Temporal | 0.0289 → 0.0251 | 0.0595 → 0.0852 | 0.0617 → 0.0590 |
| Combined RRF | 0.1135 → 0.0978 | 0.2610 → 0.2097 | 0.1502 → 0.1468 |
| Combined max | 0.0861 → 0.0912 | 0.1809 → 0.1886 | 0.0957 → 0.1053 |

Temporal Precision@10 increases by 2.57 percentage points, while its AP falls
by 0.0038. Its full-list observed recall falls from `0.7696` to `0.6263`, with
mean candidates falling from `4121.2393` to `3728.3709`. Both combinations'
observed recall falls from `0.9029` to `0.8141`, with mean candidates falling
from `4220.6393` to `3876.0864`. This experiment changes coverage as well as
ranking; fewer returned candidates are not a free accuracy improvement.

This coverage restriction is structural: A/AAAA intervals are a subset of the
baseline's all-DNS intervals. Requiring their overlap can only keep or remove
temporal candidates. With other methods fixed, the combined candidate union
can only stay the same or shrink, so full-list recall cannot increase. Top-k
metrics can move in either direction as the remaining candidates are rescored.

For temporal matching, mean actor-domain false leads in the top 25 rise from
`0.18` to `0.27` for benign seeds and fall from `1.125` to `0.50` for crimeware
seeds. These counts describe false associations, not an overall false-positive
rate. RRF ranking declines on this dataset, while maximum-score combination
improves its ranking metrics at the reduced recall. Raw method scores remain
incomparable confidence scales; this outcome does not calibrate them.
Fingerprint alone still has higher AP (`0.1300`) and Precision@10 (`0.2739`)
than either combination on this delivered no-filter benchmark.

All per-seed metric rows for IP co-residency, NS/MX reuse, and fingerprint
matching are exactly unchanged. Perfect-filter results are saved separately;
temporal matching is label-independent and must match its no-filter results.

### Fresh-world validation

All three preselected world pairs completed. There are 198 observed benchmark
seeds in world 6263, 196 in world 6264, and 195 in world 6265. These differences
reflect observed domain availability; each before/after pair has identical
seed identities. The delivered world is kept separate from the validation mean.

No-filter temporal results for every selected world:

| World | AP before → after | Precision@10 before → after | Recall@25 before → after | Observed recall before → after |
| --- | --- | --- | --- | --- |
| 6263 | 0.0403 → 0.0453 | 0.1025 → 0.1364 | 0.0816 → 0.0777 | 0.7603 → 0.6173 |
| 6264 | 0.0483 → 0.0358 | 0.1232 → 0.1000 | 0.0858 → 0.0615 | 0.7566 → 0.6519 |
| 6265 | 0.0423 → 0.0285 | 0.1150 → 0.0895 | 0.0774 → 0.0528 | 0.7641 → 0.6467 |

Means across the three worlds, rounded to four decimals:

| Method | AP before → after | Precision@10 before → after | Recall@25 before → after | Observed recall before → after |
| --- | --- | --- | --- | --- |
| Temporal | 0.0436 → 0.0365 | 0.1136 → 0.1086 | 0.0816 → 0.0640 | 0.7603 → 0.6386 |
| Combined RRF | 0.0884 → 0.0731 | 0.1890 → 0.1680 | 0.1120 → 0.1031 | 0.8657 → 0.8046 |
| Combined max | 0.0512 → 0.0474 | 0.0954 → 0.1009 | 0.0607 → 0.0570 | 0.8657 → 0.8046 |

Temporal AP and Precision@10 improve in one world and decline in two. Temporal
Recall@25 and full-list observed recall decline in all three worlds. Its mean
candidate count falls from `4129.7365` to `3822.2244`. The delivered world's
Precision@10 gain therefore does not repeat consistently in fresh worlds.
Combined max improves Precision@10 in all three validation worlds, while its
AP declines in all three; the delivered world's AP gain does not carry over.

Temporal actor-domain false leads average `0.1600 → 0.2000` for benign seeds
and `0.9066 → 0.3570` for crimeware seeds. Crimeware false leads fall in every
world, while benign effects vary. This is another trade-off, rather than a
general reduction in false positives. Per-world and per-actor CSVs retain the
unrounded deltas and include the separate oracle condition.

The world summary contains 1,872 world-specific aggregate rows and 624
cross-world summary rows. Each world's paired CSV retains individual seeds;
the combined validation graph shows every world, not just their average.

### Verification completed

- At the experiment checkpoint, **66 tests passed**, including eight temporal and five world-summary tests.
  Controlled cases cover non-hosting overlap, partial overlap, gaps, NS/MX-only
  domains, IPv6, duplicate observations, source provenance, missing profiles,
  deterministic output, invalid records, IP-seed rejection, and the real CLI.
- Comparison checks cover configuration, seed identity, metric checksums,
  source identity, world identity, unchanged controls, undefined values, and
  retaining improvements and regressions in the same summary.
- The delivered development data and artifacts from both previous milestones
  retain their original hashes. Every fresh public dataset passes validation.
- Measured loader, evaluator, common helpers, IP, NS/MX, and fingerprint sources
  are unchanged between each pair. All their per-seed control metrics match
  exactly, including undefined values. Both combined rankings were recomputed.
- Temporal per-seed metrics match across no-filter and perfect-filter conditions
  in every version and world, as required for this label-independent method.
- All seven new benchmark runs preserve source snapshots and input/metric
  hashes. All 14 raw-result archives pass a decompressed SHA-256 round trip.
- The archived simulator and inputs reproduce all four world-6263 public data
  files byte for byte. Documented commands pass shell syntax checks, and the
  real benchmark, comparison, and summary interfaces were exercised.
- Distinct graph types were visually inspected, and report tables were checked
  against saved metrics. There are no newly required packages.

### Recommendation and stopping point

The fixed experiment does **not** establish a consistent overall accuracy gain
from requiring overlapping hosting activity. It provides a clearer definition
of hosting similarity and reduces candidate breadth, with a substantial recall
cost and mixed ranking effects. These are useful research findings without
claiming success on every metric or on real APT infrastructure.

Andrew subsequently chose the earlier All-DNS temporal definition for handoff.
The working branch now uses All-DNS with the registration-period fingerprint
fix; hosting-only source and measurements remain archived as a measured
alternative. The [final handoff guide](final_handoff.md) records current
verification and the selected results.

**Stop here for review.** No scoring weights were tuned after seeing results,
and no additional variants, filters, IP seeds, or slides were implemented.
The next milestone belongs to the teammates preparing the paper and slides:
select the main ranking/coverage/false-lead figures, rehearse one documented
domain-seed example, and state the synthetic-data limits. Real filter output is
still absent from this checkout, IP seeds remain unsupported, and historical
cutoff experiments remain future work unless the team assigns them explicitly.
