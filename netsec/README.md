# DNS infrastructure pivoting project

This five-person class project explores how related infrastructure can be found
in synthetic DNS history. The full goal is to start with a domain or IP, discover
related infrastructure, explain the evidence, rank the leads, and measure accuracy
against hidden ground truth. A discovered relationship is an investigative lead,
not proof of maliciousness or common ownership.

The intended pipeline is:

```text
simulate -> filter noise -> pivot -> score -> evaluate/demo
```

## What works now

| Stage | Current state |
| --- | --- |
| Data | Delivered synthetic DNS datasets and their shared format. Simulator implementation is not present here. |
| Filter | Real filter output is not present. A small explicit mock labels file supports the demo. |
| Pivot | Domain-seed temporal IP co-residency is implemented with a CLI, importable function, and 14 controlled tests. IP seeds and the other methods are pending. |
| Score | The IP method supplies its own heuristic strength. Combining methods into a final ranking remains separate work. |
| Evaluate/demo | A reproducible mock-label demo is available. Ground-truth accuracy evaluation is not implemented here. |

Andrew's current contribution is pivoting. The team overview also lists Rick and
Suraj under pivoting; individual method ownership still needs agreement.
Completing the IP baseline does not complete the shared engine.

## Repository map

### Root files

| Path | Purpose |
| --- | --- |
| [README.md](README.md) | Repository overview, file map, run commands, and recommended next steps. |
| [AGENTS.md](AGENTS.md) | Instructions for coding agents: project scope, Andrew's coding preferences, data boundaries, and verification requirements. |
| [load_data.py](load_data.py) | Shared JSON/JSONL reads and deterministic JSONL writes. Components should use this module for shared file I/O. |

### `pivot/`, `tests/`, `examples/`, and `output/`

These folders hold the implemented method, its checks, demonstration inputs, and
generated results.

| Path | Purpose |
| --- | --- |
| [pivot/README.md](pivot/README.md) | Detailed IP co-residency guide: algorithm, callable interface, evidence fields, score formula, actual output, errors, and limitations. |
| [pivot/__init__.py](pivot/__init__.py) | Marks `pivot` as a Python package so methods can be imported and run as modules. |
| [pivot/ip_coresidency.py](pivot/ip_coresidency.py) | Finds domains sharing an exact eligible IPv4/IPv6 address during overlapping dates. Contains the importable method and CLI. |
| [tests/test_ip_coresidency.py](tests/test_ip_coresidency.py) | Standard-library tests using controlled observations and temporary files, including interval gaps, duplicate sources, filtering, IPv6, aggregation, and CLI behavior. |
| [examples/mock_infra_labels.json](examples/mock_infra_labels.json) | Hand-selected demo eligibility for one IP. Uses the filter's output schema and retains an explicit `MOCK` reason. It is not a classifier or a maliciousness finding. |
| [output/pivot_results.jsonl](output/pivot_results.jsonl) | Generated method results: one JSON object per seed/candidate/method, containing `seed`, `candidate`, `method`, `evidence`, and `score`. The demo replaces this file. |

The filter's future `output/infra_labels.json` will tell the pivot which
infrastructure is eligible. It is currently absent. Only explicit `candidate`
labels permit expansion; missing labels and noise labels are skipped.

### `data_seeding/`

Contains the delivered synthetic datasets, original archives, and the shared data
contract. Use the directory **without ground truth** for pivot/filter development.
Keep the delivered data intact.

| Path | Purpose |
| --- | --- |
| [data-format.md](data_seeding/data-format.md) | Shared version 0.1 contract for observations, infrastructure, registration history, filter labels, and pivot results. This defines the integration format. |
| [data-format-walkthrough.md](data_seeding/data-format-walkthrough.md) | Plain-language explanation of DNS observations, forward/passive sources, infrastructure metadata, and domain lifecycle features. |
| `seed-data-no-ground-truth/` | Development inputs available to the filter and pivot methods; its four files are described below. |
| `seed-data-with-ground-truth/` | Dataset delivery for evaluation and simulation context. Ground truth is reserved for evaluation; actor profiles are simulator inputs and must not become pivot features. |
| `seed-data-6262-no-ground-truth.zip` | Original archived delivery of the development dataset. An extracted copy is already available. |
| `seed-data-6262-with-ground-truth.zip` | Original archived delivery with evaluation/simulation material. It is not a pivot development input. |

Files in `data_seeding/seed-data-no-ground-truth/`:

| File | Contents and use |
| --- | --- |
| `resolutions.jsonl` | Domain-to-value observations: A, AAAA, NS, or MX records, first/last seen dates, and forward/passive source. The current method uses A/AAAA records. |
| `infra.json` | Metadata keyed by IP or server hostname: infrastructure type, ASN, organization, country, distinct-domain count, and raw label. Raw labels are `unknown`; eligibility comes from filter output. |
| `domains.json` | Registrar and registration history. Useful for later fingerprint/lifecycle features; the current IP method does not load it. |
| `manifest.json` | Dataset version, generation parameters, date range, and counts. Describes the dataset rather than supplying detection evidence. |

The shared contract also describes `ground_truth.json` and `actors/*.json`.
Only evaluation may read the former. Actor profiles describe how the simulator
plants behavior; they must not be used to design or tune the pivot.

### `working/`

Planning, research context, task specifications, and implementation records live
here. These documents have different roles; proposed assignments and older
inventories are not the current implementation status.

| Path | Purpose |
| --- | --- |
| [overview.md](working/overview.md) | Team's synthetic-data proof of concept, overall pipeline, and estimated work distribution. |
| [proposal.md](working/proposal.md) | Original research motivation, references, and broader real-data vision. That vision extends beyond the current synthetic-data implementation. |
| [AI_overview.md](working/AI_overview.md) | Proposed roles, methods, and schedule. It does not establish that teammates accepted a particular allocation. |
| [pivot_engine_scope.md](working/pivot_engine_scope.md) | Pivot design and integration guidance, method descriptions, and remaining decisions. Its initial inventory predates the implemented IP baseline. |
| [skills_recommendations.md](working/skills_recommendations.md) | Optional reviewed skill suggestions and their intended use. They are not installed capabilities or dependencies. |
| [tasks/001-ip-coresidency.md](working/tasks/001-ip-coresidency.md) | First implementation task, acceptance checks, and appended completion record with actual commands and outcomes. |

Python may generate `__pycache__/` folders beside source files during execution.
They contain interpreter bytecode caches, not project source or input data.

## Run the current baseline

Use **Python 3.11 or newer**; the baseline was verified with Python 3.11.4.
It uses only the standard library, so no packages need installing. Run these
commands from the repository root.

Run the demo with **mock filter labels**:

```sh
python3 -m pivot.ip_coresidency accountcoast.com \
  --data-dir data_seeding/seed-data-no-ground-truth \
  --labels examples/mock_infra_labels.json \
  --output output/pivot_results.jsonl
```

Inspect the generated JSONL, then run the tests:

```sh
python3 -m json.tool --json-lines output/pivot_results.jsonl
python3 -m unittest discover -s tests -v
```

The demo emits `docslink.com` through `165.80.147.127`, with **12 inclusive
overlap days** and score **0.4**. The task's 11-day example describes the forward
observations alone; the passive observation extends the combined overlap through
June 23, 2025. The [method guide](pivot/README.md) shows the complete record and
explains the difference.

This method takes one hop, preserves disjoint intervals, and deduplicates
overlapping forward/passive days. Its score is the strongest shared IP's overlap
days divided by 30, capped at 1, rather than a maliciousness probability.
`--labels` is required; dataset and output paths are configurable. Unknown
domains or domains without eligible observations produce an empty output;
IP seeds are explicitly rejected for now.

## Recommended next steps for Andrew

1. **Understand and rehearse the implemented method.** Read
   [the method guide](pivot/README.md), then `load_data.py`,
   `pivot/ip_coresidency.py`, and the tests. Run the demo and explain one
   result's IP, time overlap, sources, and score. This is the baseline you can
   already show the team.
2. **Confirm the integration owners and method split.** Coordinate with Rick and
   Suraj on who owns IP co-residency, NS/MX reuse, and fingerprint matching.
   Confirm who supplies filter labels, maintains the shared loader, and combines
   scores with Johnny/the evaluation contributor. The planning documents do not
   settle those assignments.
3. **Integrate real filter output.** Obtain `output/infra_labels.json` in the
   existing contract, then pass it with `--labels` instead of the mock file.
   Check candidate/noise/missing-label behavior together. This removes the
   immediate mock-data dependency without changing the method.
4. **Choose the next agreed pivot milestone.** If another method belongs to you,
   NS/MX reuse is a natural next step: define uncommon-host thresholds and
   preserve temporal evidence. If the team needs IP seeds first, agree on their
   candidate domains, applicable observation windows, and evidence before
   implementing them. Fingerprinting can follow using observable registrar,
   hosting ASN, aging, and lifespan features.
5. **Hand the baseline to evaluation.** Share the callable interface and example
   JSONL, agree on evidence keys and score meanings, and have the evaluator choose
   benchmark seeds and measure accuracy using hidden ground truth. Keep
   combined ranking separate from the method's score. For later forward/passive
   timing experiments, agree on a cutoff applied consistently to observations,
   filter features, and infrastructure counts.

The immediate priority is to confirm ownership and replace mock eligibility with
real filter labels. The existing baseline is ready for that discussion.
