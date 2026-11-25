# Evaluation

Scores the pivot methods against the simulator's ground truth: from one seed
domain, how well does each method recover the seed actor's other domains? The
decisions behind these metrics are in [docs/evaluation_plan.md](../docs/evaluation_plan.md).

This is the only stage that reads `ground_truth.json`. The pivots run on
`data/seed-data_no-ground-truth/` and receive only observations, metadata, and
filter labels.

## Run from the repository root

Python 3.11 or newer; standard library only.

```sh
python3 -m evaluation.evaluate
python3 -m unittest discover -s tests -p '*.py' -v
```

To include the heuristic filter as a separate evaluation condition, generate
its labels first and pass them explicitly:

```sh
python3 -m filter.classify
python3 -m evaluation.evaluate --labels output/infra_labels.json
```

The first command takes about 45 seconds with the two methods on `main`. It
prints a summary table per filter condition and writes to `output/eval/`
(Git-ignored, replaced on each run).

| Option | Default | Meaning |
|---|---|---|
| `--data-dir` | `data/seed-data_no-ground-truth` | Observations the pivots run on |
| `--truth-dir` | `data/seed-data_with-ground-truth` | Directory holding `ground_truth.json` |
| `--labels` | none | Real filter output; adds a `real_filter` condition |
| `--max-domain-count` | 10 | NS/MX rarity threshold |
| `--benign-sample` | 100 | Number of benign seeds |
| `--random-seed` | 6262 | Seed for the benign sample |
| `--output-dir` | `output/eval` | Where results are written |

## What it does

1. **Seeds.** Every actor domain with at least one observation (56), a fixed
   random sample of 100 observed benign domains, and every observed crimeware
   domain (40).
2. **Filter conditions.** Each seed is run under:
   - `no_filter`: every IP/NS/MX value is `candidate` (lower bound);
   - `perfect_filter`: only values whose ground-truth role is `actor`,
     `dedicated`, `self_hosted_ns`, or `self_hosted_mail` are `candidate`
     (upper bound; must not be used to tune pivots);
   - `real_filter`: the file passed with `--labels`, if any.
3. **Methods.** `ip_coresidency` and `ns_mx_reuse`, plus `fingerprint_match`
   and `temporal_behavior` automatically when their modules are present (they
   are on the `rickdev/pivoting` branch). Two combined rankings are added:
   - `combined_rrf`: reciprocal rank fusion, each candidate scoring
     `1 / (60 + rank)` per method, because method scores are on different scales;
   - `combined_max`: candidates ordered by their highest score from any method.
4. **Ranking.** Each method's candidates are sorted by score, highest first,
   with ties broken by candidate name so every run is identical.

## Metrics

A correct answer for a seed is another domain of the **same actor**. Crimeware
and other actors' domains are wrong answers, counted separately.

Per actor seed and method:

| Field | Meaning |
|---|---|
| `average_precision` | Mean precision at each rank where a correct answer appears, over all observed correct answers. Missed answers count as zero. |
| `precision_at_k`, `recall_at_k` | Within the top k results, k = 5, 10, 25. Precision divides by k even when fewer results are returned. |
| `precision` | Over the full returned list (undefined when nothing is returned) |
| `recall_all` | Against every other domain of the actor, including domains with no observations |
| `recall_observed` | Against other actor domains with at least one observation (headline) |
| `recall_reachable` | Against actor domains that used one of the actor's own IPs, NS hosts, or MX hosts on dates overlapping the seed's use: what an ideal one-hop pivot could find |
| `other_malicious_in_top_25` | Crimeware or other-actor domains in the top 25 |
| `evidence_correct_share` | IP and NS/MX only: share of correct answers whose shared IP or host is the actor's own, rather than a coincidental match |
| `n_results`, `n_positives`, `n_reachable` | List and answer-set sizes |

Per benign or crimeware seed: `actor_domains_in_top_25`, `actor_domains_returned`,
and `n_results`. Every actor domain returned from these seeds is a false lead.

Per condition: `unique_true_positives_top_25` counts correct answers in one
method's top 25 that no other method has in its top 25, summed over seeds.

**Averaging.** Values are averaged over seeds within each actor (mean and
median); the `overall` entry averages the actor means with the actors weighted
equally. Undefined values are left out.

## Output files

| File | Contents |
|---|---|
| `output/eval/<condition>/pivot_results.jsonl` | Every method's raw results for every seed, in the shared contract format |
| `output/eval/per_seed.jsonl` | One row per condition, method, and seed with the metrics above |
| `output/eval/summary.json` | Run configuration, unique-true-positive counts, and aggregated metrics |

## Current results (`main` methods only)

Means over actor seeds, actors weighted equally:

| Condition | Method | AP | P@10 | R@25 | Recall (observed) | Recall (reachable) | Avg results |
|---|---|---|---|---|---|---|---|
| no_filter | ip_coresidency | 0.012 | 0.051 | 0.019 | 0.058 | 0.326 | 138.7 |
| no_filter | ns_mx_reuse | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.1 |
| perfect_filter | ip_coresidency | 0.017 | 0.050 | 0.017 | 0.017 | 0.305 | 0.5 |
| perfect_filter | ns_mx_reuse | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.0 |

The combined rankings equal `ip_coresidency` here because NS/MX returns almost
nothing. Two observations, both from ground truth and therefore evaluation
context, not tuning targets:

- AMBER_KITE's own name servers are each used by 18 domains and its mail server
  by 12, above the default `max_domain_count` of 10, so NS/MX never considers them.
- SLATE_HERON's name servers are used by 3 domains each but produce no results,
  so those domains' uses do not overlap in time.

## Limitations

- Ground truth has two actors; results are not statistically strong.
- Pivots accept domain seeds only and search one hop.
- Threshold sweeps, forward vs. passive comparison, the CDN-fronted subgroup,
  and plots are not implemented yet.
- Scores are heuristic evidence strengths, not probabilities of maliciousness.
