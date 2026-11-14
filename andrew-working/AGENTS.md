# DNS infrastructure pivoting project agent

## Purpose and scope

Help Andrew understand, implement, and verify his contribution to a five-person class project: a proof-of-concept APT infrastructure discovery tool using synthetic DNS history. Given a seed domain or IP, the pipeline finds related infrastructure, explains the evidence, ranks candidates, and measures accuracy against hidden ground truth.

The pipeline is `simulate -> filter noise -> pivot -> score -> evaluate/demo`. Andrew's current assignment is pivoting. The team overview also lists Rick and Suraj under pivoting; individual method ownership is unresolved. Implement the method requested in the current task. When implementation is requested without a chosen method, recommend temporal IP co-residency as the first milestone. Completing one method is distinct from completing the shared engine.

Answer scope and design questions directly. A request for analysis or agent configuration is not a request to implement the whole pipeline.

## Project references

This directory is Andrew's workspace inside the shared repository. Run its CLI
and tests from `andrew-working/`. Shared schemas and datasets live one level up;
planning documents live in this directory's `docs/` folder.

Read the references relevant to the task:

- [docs/overview.md](docs/overview.md): the team's current synthetic-data PoC and estimated work distribution.
- [data-format.md](../data-format.md): shared input/output contract, format version 0.1.
- [data-format-walkthrough.md](../data-format-walkthrough.md): meanings of observations, source types, and lifecycle features.
- [docs/proposal.md](docs/proposal.md): original research motivation and broader real-data vision. Distinguish that vision from the current implementation scope.
- [docs/AI_overview.md](docs/AI_overview.md): proposed roles, methods, and schedule; these are not evidence that teammates agreed to a particular allocation.
- [docs/pivot_engine_scope.md](docs/pivot_engine_scope.md): implementation recommendations and integration decisions; treat it as a guide rather than a new team contract.

Apply the user's latest instructions. Preserve the shared file format; explain and coordinate any necessary contract change rather than silently changing it.

## Data and integration boundaries

Develop the pivot engine against `../seed-data_no-ground-truth/` when running from `andrew-working/`. Its inputs are:

- `resolutions.jsonl`: domain, A/AAAA/NS/MX type, value, first/last seen dates, and forward/passive source.
- `infra.json`: infrastructure metadata, including ASN and distinct-domain count. Its raw `label` is always `unknown`.
- `domains.json`: registrar and registration history.
- `manifest.json`: format and dataset metadata.

The filter supplies `output/infra_labels.json`, containing inferred infrastructure labels and domain timing features. Exclude infrastructure classified as parking, sinkhole, CDN, or shared hosting from eligible pivots. Define an explicit policy for missing labels; raw `unknown` is not inferred `candidate`. If filter output is unavailable, use small, clearly identified mock labels for development and disclose that limitation.

Only the evaluation stage may read `ground_truth.json`. Do not inspect or use it to design or tune pivot/filter behavior. Actor profiles are simulator inputs, not pivot features. Restrict dataset content searches to the directory without ground truth by default. Keep the delivered datasets intact.

The contract requires shared file I/O through `load_data.py`. Inspect the existing implementation first; if missing during an authorized implementation task, add a minimal shared loader or compatible interface without duplicating loading logic across methods. Keep dataset paths configurable.

The pivot output is `output/pivot_results.jsonl`. Each record contains `seed`, `candidate`, `method`, `evidence`, and a numeric `score` from 0 to 1. Supported method names are `ip_coresidency`, `ns_mx_reuse`, and `fingerprint_match`. Preserve the original seed in results. Explain per-method scores as heuristic evidence strengths, not calibrated probabilities. Combined ranking and accuracy measurement are separate integration responsibilities whose ownership needs agreement.

## Pivot methods and extensions

- **IP co-residency:** find domains sharing the exact eligible IPv4/IPv6 address during overlapping intervals. Include the IP, intervals, overlap duration, infrastructure domain count, and sources in evidence. An ASN or address-block match is supporting evidence or a separate experiment, not equivalent to exact IP sharing.
- **NS/MX reuse:** find domains sharing uncommon eligible name-server or mail-server hosts. Make rarity thresholds explicit and preserve temporal evidence.
- **Fingerprint matching:** compare observable registrar, hosting ASN, aging, and lifespan features with the seed. Derive hosting ASN from A/AAAA infrastructure. Handle missing features explicitly; do not obtain fingerprints from simulator actor profiles.
- **Forward versus passive discovery:** the source field supports a timing comparison with evaluation. This does not require a live scanning integration. For historical experiments, apply the observation cutoff to all derived features and infrastructure counts to avoid using future information.
- **TLS certificates and server metadata:** these are absent from the delivered schema. Treat certificate/banner fingerprinting as an extension requiring additional data and an agreed contract.
- **Temporal heuristics:** observation intervals support active-duration and change-rate features. DNS TTL is not supplied. Compare observed patterns without assuming that every short-lived domain is malicious.

## Implementation and verification

Prefer Python and in-memory indexes for the current JSON-based PoC; use the project's existing tools and dependencies when available. The team overview specifies no database. Inspect current scripts before giving setup or run commands.

Andrew's coding requirements:

- Write the smallest clear implementation that meets the requested functionality. Prefer descriptive names, ordinary loops, dictionaries, and straightforward functions over clever compression.
- Add a helper function only when it gives a meaningful operation a clear name or removes useful duplication. Avoid speculative abstractions, class hierarchies, plugin registries, generic frameworks, and features for hypothetical future tasks.
- Prefer the Python standard library for the baseline. Add a dependency only when the current functionality materially needs it; a recommended skill's tooling examples do not require installing those tools.
- Add concise function docstrings and comments that explain reasoning, assumptions, and non-obvious behavior, especially interval merging, filtering, and scoring. Avoid comments that merely repeat a statement.
- Maintain a Markdown guide explaining the algorithm, file responsibilities, exact setup/run/test commands, output evidence, score meaning, and limitations. Verify its commands against the implementation.
- Keep verification focused on observable behavior and important edge cases; avoid elaborate test infrastructure and tests that merely repeat implementation details.

Reviewed skill recommendations and their intended use are in [docs/skills_recommendations.md](docs/skills_recommendations.md). These are recommendations, not installed capabilities or prerequisites. Use relevant available skills selectively; Andrew's scope and simplicity requirements take precedence over generic tooling suggestions. The first implementation task is [docs/tasks/001-ip-coresidency.md](docs/tasks/001-ip-coresidency.md).

Domain-seed IP co-residency and NS/MX reuse are implemented. The second method's
guide is [docs/ns_mx_reuse.md](docs/ns_mx_reuse.md), with its completion record in
[docs/tasks/002-ns-mx-reuse.md](docs/tasks/002-ns-mx-reuse.md). Shared normalization,
label validation, and interval helpers live in `pivot/common.py`; keep file I/O
in `load_data.py`. IP seeds and combined ranking remain separate milestones.

Preserve these correctness properties:

- Keep disjoint observation intervals separate. Document the day-counting convention.
- Deduplicate overlapping forward/passive observations of the same relationship while retaining source provenance. Do not count overlapping days twice.
- Use the registration period relevant to historical observations; the latest registration may belong to a different owner.
- Treat infrastructure labeled `candidate` and discovered domains as investigative leads, not confirmed attacker assets.
- Exclude self-results, keep output deterministic, and document candidate/evidence aggregation.
- Handle IPv6, missing data, unknown seeds, domains without observations, and empty results. Domain seeds are a useful first milestone; the complete project also requires defined IP-seed behavior.
- Use bounded expansion initially. Add recursive discovery only as part of the requested scope, with limits and provenance.

For implementation changes, verify meaningful behavior with controlled fixtures covering overlap/non-overlap, excluded noise, duplicate sources, IPv6, and missing data, plus cases specific to the selected method. Keep ground-truth accuracy checks in evaluation. Report what changed, how to run it, what was actually verified, and any remaining integration dependency. Clearly identify results produced with mock labels.
