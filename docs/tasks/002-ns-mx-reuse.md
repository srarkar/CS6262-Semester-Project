# Task 002: rare NS/MX reuse

## Milestone

Given a domain seed, find candidates sharing uncommon eligible NS or MX hosts
during overlapping dates. Implement only this method, with an importable
function, small CLI, explicit mock-label demo, controlled tests, and a Markdown
guide. Paths in this completed task now reflect main's shared layout: code in
`pivot/`, tests in `tests/`, examples in `examples/`, and documentation in `docs/`.
Use `data/seed-data_no-ground-truth/` from the repository root.

Keep the code direct and standard-library only. Reuse the existing loader and
interval behavior through a small shared helper module rather than introducing
an engine framework. Preserve the JSONL contract and use `method: ns_mx_reuse`.
Do not read actor profiles or ground truth.

## Accepted behavior

- Match exact hosts within the same record type and corresponding metadata type.
- Require explicit `candidate` eligibility and an integer domain count from 1
  through the configurable limit (default 10); skip unknown rarity and noise.
- Require inclusive date overlap, preserve gaps, deduplicate sources, retain
  provenance, exclude the seed, and stop after one hop.
- Aggregate evidence into one deterministic record per candidate.
- Score the strongest matching host as `max(1 / domain_count)`, rounded to six
  decimal places; record the limit in evidence. This is a rarity strength.
- Document the API, files, commands, score, mock filtering, and limitations in
  [the NS/MX guide](../ns_mx_reuse.md).

## Implementation and verification — November 14, 2026

Added `pivot/ns_mx_reuse.py`, `tests/ns_mx_reuse.py`, and
`examples/mock_ns_mx_labels.json`. Moved the existing naming, label, and interval
helpers into `pivot/common.py`, including a shared overlap operation used by both
methods. Updated the workspace and method guides. The code adds no dependencies.

Applied the reviewed `python-code-style`, `python-testing-patterns`, and
`crafting-effective-readmes` guidance directly from their source instructions;
see [the skill recommendations](../skills_recommendations.md). No skills or
tooling were installed. Project scope and the user's minimal-code requirements
take precedence over optional tooling examples.

Commands use the current shared layout and run from the repository root:

```sh
python3 -m unittest discover -s tests -p '*.py' -v
```

Outcome: **26 tests passed**, including all 14 original IP tests and 12 NS/MX
tests. Cases cover NS and MX, exact type/host matching, rarity limits, missing
metadata/counts, excluded/missing labels, inclusive overlap, gaps/non-overlap,
duplicate sources, provenance, self-exclusion, one-hop behavior, aggregation,
determinism, input immutability, and CLI errors/output handling.

```sh
python3 -m pivot.ns_mx_reuse oceanoffice.com \
  --data-dir data/seed-data_no-ground-truth \
  --labels examples/mock_ns_mx_labels.json \
  --max-domain-count 10 \
  --output output/ns_mx_results.jsonl

python3 -m json.tool --json-lines output/ns_mx_results.jsonl
```

Outcome: one result for `quadravex.com`, sharing NS host `dns107.ovh.net`
(`domain_count: 2`) from December 12–29, 2025, **18 inclusive days**, score **0.5**.
The evidence retains the explicit mock eligibility. MX behavior is demonstrated
with controlled tests; this supplied-data demo is an NS relationship.

The original documented IP demo also succeeded after the helper extraction.
All local Markdown links resolved, `git diff --check` passed, and the four shared
development dataset hashes still matched Task 001's original handoff hashes.

Real filter integration, IP seeds, combined scoring, and accuracy evaluation
remain separate work. No maliciousness, actor ownership, or precision/recall
claim is made.
