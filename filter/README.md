# Synthetic DNS noise filter

Run from the repository root:

```sh
python3 -m filter.classify
```

This reads only `data/seed-data_no-ground-truth/` and writes the shared
`output/infra_labels.json` format. Use `--data-dir` and `--output` to select
other paths. It does not read actor profiles or `ground_truth.json`.

The baseline applies explicit, reproducible rules to each infrastructure value:

1. Provider/hostname text containing `parking` or `sinkhole` gets that label.
2. Common CDN markers (`cloudflare`, `cloudfront`, `fastly`, `akamai`) get
   `cdn`.
3. Values used by at least 20 domains get `shared_hosting`.
4. Remaining values with a positive domain count get `candidate`. Missing or
   invalid counts are conservatively excluded as `shared_hosting`.

The domain section includes registration-to-first-candidate-IP aging, the IP
used, and the longest inclusive resolution interval. When registration history
exists, the registration active on the observation date is used. Missing values
are `null`. Lifespan is an observed interval, not proof that a domain was
continuously active between sensor observations.

These are baseline heuristics, not a trained classifier or maliciousness
verdict. The confidence field describes the strength of the rule that assigned
the label; it is not a probability. Counts and provider strings can misclassify
infrastructure, so evaluate this output against ground truth only in the
evaluation stage before relying on it for pivoting.
