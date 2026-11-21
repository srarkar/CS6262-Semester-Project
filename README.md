# DNS Infrastructure Pivoting Project

[Project document](https://docs.google.com/document/d/1ImxQ0zCpi_rwWDZ3IYRtTrnnUYTazehjECVKqOV5XjE/edit?usp=sharing)

This class proof of concept finds related infrastructure in synthetic DNS history. The intended pipeline is `simulate -> filter -> pivot -> score -> evaluate`.

Candidates are investigative leads, not confirmed malicious infrastructure. Ground truth is reserved for evaluation and is never used by the pivot methods.

## Shared layout

The structure follows `origin/main` at commit `4e09f47`. The former `andrew-working/` files are integrated into the shared directories.

| Path | Purpose |
| --- | --- |
| `load_data.py` | Shared JSON/JSONL reads, deterministic JSONL writes, and project configuration |
| `sim/simulate.py` | Seed data generator; rebuilds both `data/seed-data_*` folders ([guide](sim/README.md)) |
| `sim/actors/` | Planted APT profiles used by the generator |
| `validate_data.py` | Checks a dataset against the data format |
| `pivot/ip_coresidency.py` | Domain-seed temporal IP co-residency |
| `pivot/ns_mx_reuse.py` | Domain-seed rare NS/MX reuse |
| `pivot/fingerprint_match.py` | Infrastructure fingerprint matching |
| `pivot/temporal_behavior.py` | DNS temporal behavior matching |
| `pivot/common.py` | Shared normalization, label checks, and date operations |
| `tests/` | Controlled tests for pivot methods and evaluation |
| `data/seed-data_no-ground-truth/` | Shared development observations and metadata |
| `data/seed-data_with-ground-truth/` | Evaluation/simulation data; ground truth is reserved for evaluation |
| `evaluation/evaluate.py` | Benchmarks pivot methods against ground truth |
| `evaluation/plot_accuracy.py` | Generates comparison graphs and a CSV from evaluation results |
| `examples/` | Explicit mock labels for method demos |
| `output/` | Generated JSONL results and evaluation data, ignored by Git |
| `outputs/` | Generated plots and comparison tables |
| `docs/overview.md` | Team's synthetic-data scope and estimated work distribution |
| `docs/proposal.md` | Original research motivation and broader vision |
| `docs/pivot_engine_scope.md` | Design context and remaining integration decisions |
| `docs/tasks/` | Pivot milestone and verification records |

The schemas remain in [data-format.md](data-format.md), with a plain-language [walkthrough](data-format-walkthrough.md). Planning documents describe proposals and historical assignments; they do not establish new ownership for teammates.

## Environment setup

Use Python 3.11 or newer. Run the following commands from the repository root.

Create and activate a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

Upgrade pip and install the dependencies needed for evaluation and plotting:

```sh
python -m pip install --upgrade pip
python -m pip install pandas matplotlib
```

You only need to create the virtual environment once. On subsequent runs, activate it with:

```sh
source .venv/bin/activate
```

## Run and test

Run the controlled test suite from the repository root:

```sh
python -m unittest discover -s tests -p '*.py' -v
```

The explicit test pattern is required because some test filenames do not start with `test`.

To regenerate or check the seed data:

```sh
python sim/simulate.py
python validate_data.py
```

With the defaults, the output is identical to the committed data. See the [generator guide](sim/README.md) for other seeds and scenarios.

## Run the evaluation and generate graphs

The evaluation script benchmarks the four individual pivot methods and the combined rankings against the synthetic ground truth.

**1. Run the evaluation:**

```sh
python -m evaluation.evaluate
```

By default, evaluation reads the ground-truth dataset and writes its results under:

```text
output/eval/
├── per_seed.jsonl
├── summary.json
└── ...
```

**2. Generate the graphs:**

```sh
python -m evaluation.plot_accuracy
```

The plotting script reads `summary.json` and `per_seed.jsonl` from `output/eval/`. It does not rerun the pivot methods or evaluation.

**3. Find the generated plots:**

The default output directory is `outputs/accuracy/`.

```text
outputs/accuracy/
├── ranking_quality.png
├── recall_comparison.png
├── false_leads.png
├── unique_true_positives.png
└── method_comparison.csv
```

The graphs compare:

| Output | What it shows |
| --- | --- |
| `ranking_quality.png` | Average precision and Precision@5, @10, and @25 |
| `recall_comparison.png` | Recall@5, @10, @25, observed recall, and reachable recall |
| `false_leads.png` | Actor-domain results returned for benign and crimeware seeds |
| `unique_true_positives.png` | Unique true positives in each method's top 25 results |
| `method_comparison.csv` | Tabular comparison of the methods' headline metrics |

The evaluation includes two filter conditions:

- `no_filter`: Runs without filtering candidates.
- `perfect_filter`: Uses ground-truth infrastructure roles to simulate an ideal filter. This is an upper-bound comparison, not a realistic filtering result.

The evaluator can also support a real filter-label input when labels are supplied. See [evaluation/README.md](evaluation/README.md) for evaluation options and metric definitions.

**For a normal benchmark and graph regeneration, the complete command sequence is:**

```sh
source .venv/bin/activate
python -m evaluation.evaluate
python -m evaluation.plot_accuracy
```

## Pivot method demos

Both original CLIs default to `data/seed-data_no-ground-truth`. Override `--data-dir` and `--output` as needed. Each successful run replaces its selected output file.

```sh
python -m pivot.ip_coresidency accountcoast.com \
  --labels examples/mock_infra_labels.json \
  --output output/pivot_results.jsonl

python -m pivot.ns_mx_reuse oceanoffice.com \
  --labels examples/mock_ns_mx_labels.json \
  --max-domain-count 10 \
  --output output/ns_mx_results.jsonl
```

| Demo | Result | Observed overlap | Method strength |
| --- | --- | --- | --- |
| IP | `accountcoast.com` -> `docslink.com` through `165.80.147.127` | 12 days | 0.4 |
| NS/MX | `oceanoffice.com` -> `quadravex.com` through NS `dns107.ovh.net` | 18 days | 0.5 |

The IP score is `min(strongest_overlap_days / 30, 1)`. The NS/MX score is the strongest shared host's `1 / domain_count`. Neither is a maliciousness probability, and their different meanings need evaluation before combination.

See the [IP guide](pivot/README.md) and [NS/MX guide](docs/ns_mx_reuse.md) for algorithms, callable interfaces, evidence fields, and limitations.

## Handoff to teammates

The evaluation script imports the four pivot methods:

- `find_ip_coresidents` from `pivot.ip_coresidency`
- `find_ns_mx_reuse` from `pivot.ns_mx_reuse`
- `find_fingerprint_matches` from `pivot.fingerprint_match`
- `find_temporal_matches` from `pivot.temporal_behavior`

The methods operate on the shared DNS observations and metadata. Use the shared loader in `load_data.py` for file I/O.

Replace the mock labels with actual filter output through the evaluation script's label option when it is available. Only explicit `candidate` labels permit expansion; noise and missing labels are skipped.

The evaluation stage uses ground truth to measure ranking quality, recall, and false leads. Ground truth must not be passed into the pivot methods themselves.

Remaining team work includes improving and validating the pivot methods, integrating real filter labels, and refining combined ranking. Historical discovery experiments also need consistent cutoffs across observations, labels, and domain counts.
