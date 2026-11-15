# Two new pivot methods

This bundle contains the two new independent pivot methods, the updated method contract, and focused unit tests.

## Files to add or update

- Add `pivot/fingerprint_match.py`.
- Add `pivot/temporal_behavior.py`.
- Add `tests/test_new_pivots.py`.
- In `load_data.py`, add `"temporal_behavior"` to `PIVOT_METHODS` (the bundled file already has this change).

The existing `pivot/common.py`, `pivot/ip_coresidency.py`, and `pivot/ns_mx_reuse.py` are not changed by this implementation.

## Method separation

### `fingerprint_match`

- Uses domain registration history plus A/AAAA DNS observations.
- Uses only IP infrastructure explicitly labeled `candidate` by the filter.
- Uses hosting ASN as the pivot key; it does not use NS/MX infrastructure.
- Compares registrar agreement and registration-to-first-IP-observation age.
- Chooses the registration period active at the earliest A/AAAA `first_seen` date. That date is the start of an observation interval, not a claim about the exact activation date.
- CLI requires `--labels`, like the existing infrastructure-based methods.

Example:

```text
python -m pivot.fingerprint_match seed.example --data-dir data/seed-data_no-ground-truth --labels output/infra_labels.json
```

### `temporal_behavior`

- Uses DNS observation intervals only; it does not read registrar or ASN data and does not require filter labels.
- Compares overlap/Jaccard of observed active days, lifespan, activity density, forward/passive source mix, and distinct IP counts.
- Merges overlapping intervals before counting active days, so duplicate and overlapping records do not inflate the timeline.
- A distinct IP count is a coarse history feature; it does not claim to infer exact IP transition times.

Example:

```text
python -m pivot.temporal_behavior seed.example --data-dir data/seed-data_no-ground-truth
```

Both methods emit the shared `seed`, `candidate`, `method`, `evidence`, `score` result shape. Scores are heuristic evidence strengths, not probabilities. Both are one-hop and deterministic.

## Tests

Run from the repository root:

```text
python -m unittest discover -s tests -p '*.py' -v
```

The four focused tests in this bundle pass. The existing project test suite was not included in the uploaded files, so it still needs to be run in the repository after copying these additions.
