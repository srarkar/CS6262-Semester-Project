# Task 001: temporal IP co-residency baseline

## Outcome

Implement Andrew's first pivot method: given a domain seed and explicit filter labels, find other domains that used the same eligible IPv4/IPv6 address during overlapping observed dates. Produce explained results in the team's JSONL format and a Markdown guide that a teammate can follow from `andrew-working/`.

Paths in this task are relative to `andrew-working/`. Read `AGENTS.md`, `../data-format.md`, and the relevant sections of `../data-format-walkthrough.md`. Preserve the supplied dataset. Read only `../seed-data_no-ground-truth/` for development data. Do not inspect actor profiles or ground truth.

## Code style

Use the minimum amount of clear Python needed for this task, preferably standard library only. Keep descriptive names and direct control flow. Add functions only for useful operations; avoid class-based engine frameworks, generic registries, database layers, extra pivot methods, or speculative configuration systems. Concise docstrings and comments should explain assumptions and the reasons for non-obvious decisions. Do not trade readability for fewer lines.

The reviewed skills in `docs/skills_recommendations.md` are optional guidance, not installed prerequisites. Follow the user's simplicity requirements over their broader tooling examples.

## Required behavior

1. Accept a domain seed, configurable data directory, explicit labels-file path, and output-file path through a small CLI. Use an importable pivot function so evaluation can call it later. Domain seeds are the scope of this first task; document IP-seed input as a later integration item rather than silently claiming support.
2. Centralize file reads/writes in a small `load_data.py`. Load only the tables needed for this method. Normalize the domain lookup according to the schema, while preserving the original input in the output's `seed` field.
3. Use A/AAAA observations. Expand through infrastructure explicitly labeled `candidate`; skip missing labels and all noise labels. Require a labels file instead of treating every raw `unknown` value as eligible. A missing/invalid file should produce a useful CLI error.
4. Match exact IP values and overlapping observation intervals. Count both endpoints as observed days. Merge overlapping observations for the same domain/IP so forward/passive duplicates do not inflate overlap. Preserve disjoint intervals and source provenance.
5. Exclude the seed itself. Return one result per candidate for this method, with aggregated evidence when multiple IPs support it. Keep result ordering deterministic. Unknown domains or seeds without eligible observations should produce an empty result set, documented as such.
6. Preserve the required top-level fields: `seed`, `candidate`, `method`, `evidence`, and `score`; use `method: "ip_coresidency"`. Evidence should identify shared IPs, overlap intervals/days, infrastructure domain counts, and seed/candidate observation sources. Choose a simple documented score in [0, 1] based on the available evidence. It is a method strength, not a maliciousness probability. Leave combined scoring to evaluation.
7. Supply a small, explicitly named mock labels file for a reproducible demo because the actual filter output is unavailable. Label only the infrastructure needed for the demonstration and explain that this is mock eligibility, not a finding that it is malicious. Do not implement a noise classifier as part of this task.

## Suggested files

Keep the file layout small; adapt it if an existing implementation appears before work begins:

- `load_data.py`: shared JSON/JSONL I/O needed by this method.
- `pivot/ip_coresidency.py`: the method and its CLI; use `python3 -m pivot.ip_coresidency` from `andrew-working/`, or another equally simple documented entry point.
- `tests/test_ip_coresidency.py`: focused standard-library tests with controlled observations.
- `examples/mock_infra_labels.json`: clearly identified demo-only filter output using the existing labels schema.
- `README.md`: the understanding and running guide.

## Documentation

The README must explain what the method does, each implementation file's purpose, and the steps of the algorithm in plain language. Include the Python version and dependencies, exact commands to run the demo and tests, an actual output example, the evidence fields, the score formula, and basic error/empty-result behavior.

Explain why time overlap and infrastructure filtering matter, how duplicate observation sources are handled, what the mock labels mean, and the remaining boundaries: domain seeds only, one method, synthetic data, and actual filtering/combined scoring/evaluation still separate. Keep the guide concise enough for a teammate to read before using the code. Run the documented commands before reporting completion.

## Acceptance checks

- Controlled cases verify overlapping and non-overlapping IP use, duplicate-source observations, disjoint gaps, noise/missing labels, IPv6, self-exclusion, and empty results. Include aggregation/determinism checks where useful. Avoid elaborate fixtures and tests that only mirror implementation details.
- In the supplied observations, `accountcoast.com` and `docslink.com` share `165.80.147.127` from June 12 through June 22, 2025: **11 inclusive days**. With that IP explicitly marked `candidate` in the mock labels, the demo should emit `docslink.com` with that explanation. This is an observable relationship; its actor ownership is unknown.
- The demo and test commands succeed from `andrew-working/`, output parses as the contracted JSONL, and no delivered data files are modified.
- The final handoff states the implementation files, exact successful commands, observed demo outcome, and limitations. Do not claim precision/recall or real APT detection accuracy.

## Completion record

When implementation is complete, append the actual verification commands and their outcomes here. Until then this file is a task specification, not evidence that the code exists or passes checks.

### Implemented and verified — November 12, 2026

Added `load_data.py`, `pivot/__init__.py`, `pivot/ip_coresidency.py`,
`tests/test_ip_coresidency.py`, `examples/mock_infra_labels.json`, and `README.md`.
The standard-library implementation provides an importable domain-seed method
and CLI, explicit candidate-only eligibility, inclusive interval unions with
source provenance, one-hop expansion, deterministic aggregation, and explained
JSONL output. The README documents the interface, algorithm, score, errors,
commands, actual output, and integration boundaries. No skills were installed;
`AGENTS.md` and the skill recommendations were not changed during that implementation.

The commands below were verified during implementation. Their data paths were
updated on November 13 for the shared repository layout; run them from
`andrew-working/`.

```sh
python3 --version
```

Outcome: Python 3.11.4. No third-party dependencies required.

```sh
python3 -m unittest discover -s tests -v
```

Outcome: **14 tests passed** (final run: 0.582 seconds). Controlled cases cover
overlap/non-overlap and inclusive endpoints, duplicate sources and precise source
dates, disjoint gaps, noise/missing labels, IPv6 normalization, exact IP matching
versus shared ASN/address block, self-exclusion, multiple-IP aggregation and
determinism, bounded expansion, empty results, missing metadata, invalid inputs,
JSONL output replacement, and CLI errors for missing/malformed files and labels.

```sh
python3 -m pivot.ip_coresidency accountcoast.com \
  --data-dir ../seed-data_no-ground-truth \
  --labels examples/mock_infra_labels.json \
  --output output/pivot_results.jsonl
```

Outcome: exit 0; wrote one result for `docslink.com`, supported by
`165.80.147.127` (`domain_count: 2`). The result retains the explicit `MOCK`
eligibility reason and has `overlap_days: 12`, interval June 12–23, 2025, and
score **0.4** (`12 / 30`). This is a mock-label demo, not a maliciousness finding.

**Acceptance-example discrepancy:** the specification's June 12–22, 11-day
example is correct for forward observations only. The supplied passive
observation for `docslink.com` ends June 23, so the required union of both sources
gives 12 days. The dataset and specification above were left intact; the README
explains the discrepancy. Controlled tests verify 11 days for forward-only
observations and 12 for both sources. A separate supplied-data API check also
confirmed these two outcomes (scores 0.366667 and 0.4 respectively).

```sh
python3 -m json.tool --json-lines output/pivot_results.jsonl
```

Outcome: exit 0; parsed the generated JSONL. Additional Python assertions
verified the five contracted top-level fields, method name, candidate, IP,
domain count, inclusive interval, score, and mock provenance. The README's JSON
example equals the actual emitted record, and the importable method's output
equals the CLI's parsed output.

```sh
shasum -a 256 ../seed-data_no-ground-truth/resolutions.jsonl ../seed-data_no-ground-truth/infra.json ../seed-data_no-ground-truth/domains.json ../seed-data_no-ground-truth/manifest.json
```

Outcome: all four SHA-256 hashes matched the values recorded before
implementation:

| File | SHA-256 |
| --- | --- |
| `resolutions.jsonl` | `f34d4564142857f3d1f03a1f7c5f0926c19616c84cef7057023161f898f00600` |
| `infra.json` | `6abee5ab22e79c205074d2a4db24090be34a543788729b403632aed649416dc9` |
| `domains.json` | `17906e407663f7d4a07e896345a328e39157bca806837cfb0d7f56111791d23a` |
| `manifest.json` | `9db6102ccc62c17da95f0425f2d5b4dcc27c95fba95907f66d507479f32bdd16` |

Actor profiles and ground truth were not inspected. Delivered datasets were not
modified. Remaining integration work: real filter labels, other pivot methods,
IP-seed semantics, combined ranking, and evaluation. This baseline uses the full
synthetic observation history, has no historical cutoff mode, and makes no
precision/recall or real APT detection claim. Per-method scores are heuristic
temporal strengths, not calibrated probabilities.

### Shared repository layout verified — November 13, 2026

The implementation and notes now live in `andrew-working/`, with planning files
under `docs/` and the shared datasets at the repository root. Run commands from
`andrew-working/`; the default data directory is `../seed-data_no-ground-truth`.
Generated results and Python caches are covered by the shared ignore rules.

Verification: all 14 controlled tests passed, all local Markdown links resolved,
and the four development dataset hashes still matched the table above. Running
the demo without `--data-dir` verified the new default:

```sh
python3 -m pivot.ip_coresidency accountcoast.com \
  --labels examples/mock_infra_labels.json \
  --output output/pivot_results.jsonl
```

Outcome: one result for `docslink.com`, 12 inclusive overlap days, score 0.4.
