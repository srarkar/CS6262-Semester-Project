# Pivot engine: scope and implementation guide

This is a proposed implementation scope based on the files supplied on November 12, 2026. It records what the handoff specifies and recommends a practical build order; it does not change the team's data contract or assign teammates new work.

## What the project is building

The project is a class proof of concept for finding related infrastructure in simulated DNS history. An analyst supplies one suspicious domain or IP. The tool follows shared infrastructure, produces candidate relationships with evidence, and ranks those candidates. Evaluation compares the results with the simulator's hidden answer key.

The pipeline is:

```text
Seeded DNS data -> noise filter -> pivot engine -> combined scoring and evaluation
                                      ^
                                 seed domain/IP
```

Your engine answers: **"Given this seed, what else is related, and what observations support that relationship?"** A relationship is an investigative lead, not proof that two domains belong to the same attacker.

Source priority matters:

- [overview.md](overview.md) describes the team's overall goal and lists Rick, Suraj, and Andrew under pivoting, with different approaches suggested.
- [data-format.md](../../data-format.md) specifies the delivered file formats, including the three pivot method names and the required output fields.
- [AI_overview.md](AI_overview.md) proposes detailed roles and a schedule. Its one-person-per-role allocation differs from the team overview, so individual ownership still needs agreement.
- [proposal.md](proposal.md) describes the original research motivation and a broader real-data vision. The team overview defines the current synthetic-data PoC; distinguish the two scopes when planning implementation.

## What is available now

The shared dataset in `seed-data_no-ground-truth/` at the repository root (`../seed-data_no-ground-truth/` when running from `andrew-working/`) contains:

| File | What your engine uses it for |
|---|---|
| `resolutions.jsonl` | Domain-to-IP, name-server, and mail-server observations with dates and sources |
| `infra.json` | Infrastructure type, ASN, organization, and number of distinct domains using each value |
| `domains.json` | Registrar and registration history |
| `manifest.json` | Dataset version, counts, and simulation dates |

Inspection found 43,360 observations, 5,138 domain metadata entries, and 3,284 infrastructure entries. Of those domains, 4,551 have DNS observations. All observations reference existing domain and infrastructure metadata; the distinct-domain counts match the observed records. All raw infrastructure labels are `unknown`, as specified.

The initial handoff did not contain implementation code. Tasks 001 and 002 have since added `andrew-working/load_data.py` and the domain-seed IP co-residency and NS/MX reuse methods; see the [workspace guide](../README.md). Actual filter output and evaluation code remain integration dependencies. The data handoff alone does not establish that the complete simulator can be regenerated.

Use the dataset without ground truth for engine development. Actor configuration files are simulator inputs, and `ground_truth.json` belongs exclusively to evaluation. Neither is an input to the pivot engine.

## Your deliverable and its boundaries

The pivoting work should deliver code that:

1. Accepts a seed and loads the permitted data through the shared loader.
2. Builds reusable lookups from domain to observations and from infrastructure value to domains and observation intervals.
3. Uses the filter's inferred labels to exclude noise infrastructure from expansion.
4. Runs the selected pivot methods and preserves the evidence for each result.
5. Writes `output/pivot_results.jsonl` using the existing contract.

The contract requires these fields:

| Field | Meaning |
|---|---|
| `seed` | Original input domain or IP |
| `candidate` | Related domain or IP |
| `method` | `ip_coresidency`, `ns_mx_reuse`, or `fingerprint_match` |
| `evidence` | Observations and measurements supporting the relationship |
| `score` | Method-specific strength between 0 and 1 |

You need a documented per-method score. The AI overview assigns combining methods into a final confidence ranking to the scoring/evaluation stage; confirm that boundary with Johnny. These scores are heuristic strengths, not calibrated probabilities of maliciousness.

The broader pipeline also needs data generation, infrastructure classification, evaluation against ground truth, and a presentation/demo. Those are separate components to coordinate with. JSON files and in-memory lookups are enough for the proposed engine; the overview explicitly specifies no database.

## The three methods

| Method | Candidate-generation rule | Useful evidence |
|---|---|---|
| IP co-residency | Find other domains using the seed's same eligible A/AAAA address during overlapping observation intervals | Shared IP, observation dates, overlap days, infrastructure domain count, sources |
| NS/MX reuse | Find domains using the same uncommon eligible name server or mail server | Shared hostname, NS or MX type, domain count, observation dates, sources |
| Fingerprint match | Compare registrar, hosting ASN, and aging/lifespan features with the seed | Matching features, compared feature values, differences, missing features |

Start with IP co-residency because it is easy to explain and check. Add NS/MX reuse next, then fingerprint matching. Keep thresholds and scoring rules configurable and record their meaning. A common registrar or hosting ASN alone provides weak evidence.

The fingerprint method should derive its reference features from the seed's observable data. A cluster-based version can come later, using only cautiously selected pivot results. Do not use the planted actor profiles to obtain the fingerprint.

Here is an actual relationship in the supplied observations:

```text
accountcoast.com -> 165.80.147.127 <- docslink.com

accountcoast.com: 2025-06-12 through 2025-12-31, forward source
docslink.com:    2024-12-06 through 2025-06-22, forward source
shared interval: 2025-06-12 through 2025-06-22
IP domain_count: 2
```

With an inclusive-day convention, that is 11 overlapping days. If the filter permits this IP, the engine can emit an `ip_coresidency` result explaining this connection. This example was selected from observable relationships, without consulting ground truth; its maliciousness is unknown.

## Practical build order

1. **Agree on the integration boundary.** Identify who owns `load_data.py`, who supplies filter labels and timing features, and who combines scores. Assign the methods among the pivoting contributors. Keep the existing JSON format.
2. **Build a small domain-seed baseline.** Load records, build the two lookups, and find overlapping A/AAAA co-residency. Use a small explicit mock filter output while the real filter is unavailable. Describe that run as using mock labels.
3. **Produce valid results early.** Write one line per seed/candidate/method, aggregating supporting observations in its evidence. Keep separate method results for the same candidate so evaluation can compare methods.
4. **Integrate the filter.** Consume its labels and domain timing features. Define how missing labels are handled; do not silently equate raw `unknown` with inferred `candidate`.
5. **Complete the agreed method set and IP-seed behavior.** Add rare NS/MX reuse and fingerprint matching according to the division of work. The overall project requires IP seeds too: define how their observed domains become anchors, which time intervals apply, and how those relationships are represented in the existing output format.
6. **Hand results to evaluation.** Supply the runner/API, supported seed types, scoring formulas, thresholds, and reproducible run instructions. Evaluation selects benchmark seeds and computes accuracy without exposing its answer key to the engine.

A suitable first milestone is: **given a domain and explicit filter labels, emit explained IP co-residency results in the agreed JSONL format.** That is a useful baseline, not completion of the full engine scope.

## Details that affect correctness

- Preserve time intervals. The same IP used by different domains years apart is not overlapping co-residency. Agree on inclusive or exclusive day counting and use it consistently.
- Forward and passive observations often describe the same relationship. Do not count them as independent confirmations or add their overlapping days twice. Merge overlapping intervals for the same relationship while retaining source provenance; do not bridge unobserved gaps.
- Use only A/AAAA observations for hosting-ASN features; NS/MX ASNs describe different services.
- Registration history matters: 284 domains have multiple registration periods. Historical features should use the registration period relevant to the observation, rather than applying the latest owner to all history. Coordinate this with the filter's timing calculations.
- An infrastructure label of `candidate` means eligible for investigation, not confirmed attacker infrastructure. NS/MX rarity also needs a documented rule so common DNS/mail providers do not create huge candidate sets.
- Handle missing timing features, unknown seeds, domains without observations, and empty result sets explicitly. The supplied domain metadata includes 587 domains without DNS observations.
- Start with bounded expansion and reproducible output ordering. Recursive discovery can amplify an early false positive and is an extension to agree on after the baseline works.
- Store timestamps and sources in evidence now. They allow later forward-versus-passive comparisons. Historical detection experiments also need a cutoff applied to observations and derived features to prevent using future information.

## Completion criteria and remaining team decisions

The engine is ready to hand off when its agreed methods run on the supplied data, required seed types are supported, noise filtering is integrated, output follows the contract, and each result has an explainable score and evidence. Verify behavior with small controlled cases: overlapping versus non-overlapping IP use, excluded noise, common versus rare NS/MX, duplicate source observations, IPv6, and missing data. Accuracy measurements belong to the evaluator.

The remaining decisions are individual method ownership; loader/filter ownership and delivery; precise evidence keys and score meanings; rarity thresholds and missing-label policy; IP-seed semantics; whether the initial release emits domain candidates only or also IP candidates; and the final combined-scoring owner. The current files do not settle those details.
