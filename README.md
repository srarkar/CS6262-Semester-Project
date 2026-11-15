# DNS infrastructure pivoting project

[Project document](https://docs.google.com/document/d/1ImxQ0zCpi_rwWDZ3IYRtTrnnUYTazehjECVKqOV5XjE/edit?usp=sharing)

This class proof of concept finds related infrastructure in synthetic DNS
history. The intended pipeline is `simulate -> filter -> pivot -> score -> evaluate`.
Candidates are investigative leads, not confirmed malicious infrastructure.

Andrew's domain-seed IP co-residency and rare NS/MX reuse methods are implemented
and ready for teammates to continue. Their APIs and JSONL output are available;
actual filtering, IP-seed support, combined scoring, and evaluation remain open.
The two demos use explicitly mocked infrastructure eligibility.

## Shared layout

The structure follows `origin/main` at commit `4e09f47`. The former
`andrew-working/` files are integrated into the shared directories.

| Path | Purpose |
| --- | --- |
| [load_data.py](load_data.py) | Shared JSON/JSONL reads and deterministic JSONL writes |
| [pivot/ip_coresidency.py](pivot/ip_coresidency.py) | Domain-seed temporal IP co-residency and CLI |
| [pivot/ns_mx_reuse.py](pivot/ns_mx_reuse.py) | Domain-seed rare NS/MX reuse and CLI |
| [pivot/common.py](pivot/common.py) | Shared normalization, label checks, and date operations |
| [tests/ip_coresidency.py](tests/ip_coresidency.py) | 14 controlled IP tests, using main's filename |
| [tests/ns_mx_reuse.py](tests/ns_mx_reuse.py) | 12 controlled NS/MX tests, using main's filename |
| `data/seed-data_no-ground-truth/` | Shared development observations and metadata |
| `data/seed-data_with-ground-truth/` | Evaluation/simulation delivery; ground truth is reserved for evaluation |
| [evaluation/evaluate.py](evaluation/evaluate.py) | Benchmark against ground truth; see the [evaluation guide](evaluation/README.md) |
| [tests/evaluate.py](tests/evaluate.py) | 7 controlled evaluation tests |
| `examples/` | Explicit mock labels for each method's demo |
| `output/` | Generated JSONL results, ignored by Git |
| [docs/overview.md](docs/overview.md) | Team's synthetic-data scope and estimated work distribution |
| [docs/proposal.md](docs/proposal.md) | Original research motivation and broader vision |
| [docs/pivot_engine_scope.md](docs/pivot_engine_scope.md) | Design context and remaining integration decisions |
| [docs/tasks/001-ip-coresidency.md](docs/tasks/001-ip-coresidency.md) | IP milestone and verification record |
| [docs/tasks/002-ns-mx-reuse.md](docs/tasks/002-ns-mx-reuse.md) | NS/MX milestone and verification record |

The schemas remain in [data-format.md](data-format.md), with a plain-language
[walkthrough](data-format-walkthrough.md). Planning documents describe proposals
and historical assignments; they do not establish new ownership for teammates.

## Run and test from the repository root

Use Python 3.11 or newer. Both methods use only the standard library.

```sh
python3 -m pivot.ip_coresidency accountcoast.com \
  --labels examples/mock_infra_labels.json \
  --output output/pivot_results.jsonl

python3 -m pivot.ns_mx_reuse oceanoffice.com \
  --labels examples/mock_ns_mx_labels.json \
  --max-domain-count 10 \
  --output output/ns_mx_results.jsonl

python3 -m unittest discover -s tests -p '*.py' -v
```

Both CLIs default to `data/seed-data_no-ground-truth`. Override `--data-dir` and
`--output` as needed. Each successful run replaces its selected output file.
The explicit test pattern is required because main's test filenames do not
start with `test`.

| Demo | Result | Observed overlap | Method strength |
| --- | --- | --- | --- |
| IP | `accountcoast.com` -> `docslink.com` through `165.80.147.127` | 12 days | 0.4 |
| NS/MX | `oceanoffice.com` -> `quadravex.com` through NS `dns107.ovh.net` | 18 days | 0.5 |

The IP score is `min(strongest_overlap_days / 30, 1)`. The NS/MX score is the
strongest shared host's `1 / domain_count`. Neither is a maliciousness
probability, and their different meanings need evaluation before combination.

See the [IP guide](pivot/README.md) and [NS/MX guide](docs/ns_mx_reuse.md) for
the algorithms, callable interfaces, evidence fields, and limitations.

## Handoff to teammates

Evaluation can import `find_ip_coresidents` from `pivot.ip_coresidency` and
`find_ns_mx_reuse` from `pivot.ns_mx_reuse`. Both accept a seed, loaded resolution
records, infrastructure metadata, and filter labels; NS/MX also accepts
`max_domain_count=10`. Use the shared loader for file I/O. Results retain the
contract's `seed`, `candidate`, `method`, `evidence`, and `score` fields.

Replace the mock labels with actual filter output through `--labels` when it is
available. Only explicit `candidate` labels permit expansion; noise and missing
labels are skipped. Neither pivot reads actor profiles or ground truth.

Remaining team work includes defining IP-seed behavior, integrating real filter
labels, assigning any fingerprint method, and implementing combined ranking and
ground-truth evaluation. Historical discovery experiments also need consistent
cutoffs across observations, labels, and domain counts. Andrew's work stops at
this handoff; the layout change adds no new discovery behavior.
