Data contract
All data lives in JSON files with a fixed format, agreed on Day 1 and changed only by group agreement. Big tables use JSON Lines (.jsonl, one record per line); small lookup tables use regular JSON.
File
Written by
Read by
Contents
data/resolutions.jsonl
A
C, D
One DNS observation per line: domain, rrtype (A/AAAA/NS/MX), value, first_seen, last_seen
data/infra.json
A
C, D
Keyed by IP or NS/MX host: asn, org, country, domain_count, label (always unknown in the raw output)
data/domains.json
A
C, D
Keyed by domain: registrar, registered date
data/actors/*.json
B
A
One behavior profile per fake actor
data/ground_truth.json
A + B
E only
Actor → true domains/IPs; true infra labels (parking, sinkhole, CDN)
output/infra_labels.json
C
D
C's inferred labels + aging/lifespan stats
output/pivot_results.jsonl
D
E
seed, candidate, method, evidence, raw score

Example records:
{"domain": "update-svc.com", "rrtype": "A", "value": "45.77.12.9", "first_seen": "2024-03-02", "last_seen": "2024-05-18"}
{"seed": "update-svc.com", "candidate": "cdn-sync.net", "method": "ip_coresidency", "evidence": {"shared": "45.77.12.9", "overlap_days": 41}, "score": 0.82}
Rules:
Dates are ISO YYYY-MM-DD everywhere.
Everyone loads data through one shared load_data.py. A format change gets fixed there once.
Only E's evaluation code opens ground_truth.json. If C or D read it, the results are meaningless.
Each role commits ~50 hand-written mock records for its output file on Day 1, so nobody waits on anyone else.


Roles
There are five roles, one per person. A and B are tightly coupled and should sync daily; everyone else works off the shared files.
Role
Owner
Owns
Main deliverable
A: Simulator core
TBD
The fake DNS world
resolutions, infra, domains files
B: Actor profiles & scenarios
TBD
Planted APT behavior + ground truth
Actor configs, ground_truth.json, scenario sets
C: Noise filtering & lifecycle
TBD
Separating parking/sinkhole/CDN from candidates
infra_labels.json, aging and lifespan stats
D: Pivot engine
TBD
Finding related infrastructure
pivot_results.jsonl from 3 pivot methods
E: Scoring, evaluation & demo
TBD
Confidence scores, accuracy numbers, CLI
Results tables, pivot CLI, demo





A: Simulator core
Generates the background DNS world that the actors hide inside.
Thousands of benign domains on shared hosting and CDNs, with realistic ASNs, registrars and dates
Parking IPs (registrar default pages) and sinkhole IPs; domains that change owners, expire and get re-registered
Computes domain_count per IP/NS/MX, which the pivots use to tell shared from distinctive infrastructure
Accepts B's actor configs and a random seed, so every dataset can be regenerated exactly
Ships a small first version by Day 2; that dataset unblocks everyone else
B: Actor profiles & scenarios
Defines 3–5 fake APTs and the scenarios that test the tool.
One config per actor: preferred registrars and ASNs, uncommon NS/MX choices, domain aging time (e.g., 200 ± 60 days), IP reuse rate, noise tactics (parking first, pointing at benign IPs)
Grounds the parameters in the Atropos paper (e.g., long pre-attack provisioning, reuse of a small set of hosting providers, growing cloud-fronting)
Writes the hidden ground truth: each actor's true domains and IPs, and the true label of every noise IP
Week 2: harder scenarios: low reuse, heavy cloud-fronting, an actor that changes behavior partway through (covers "fingerprints evolving over time")
C: Noise filtering & lifecycle
Stops pivots from drowning in parking pages and CDNs.
Labels infrastructure as parking, sinkhole, CDN/shared hosting, or candidate, using heuristics (high domain_count, known parking NS patterns, short-lived resolutions)
Checks its own accuracy against the true labels with E's help (C does not read ground truth directly)
Computes per-domain temporal signals: domain aging (registration → first candidate IP) and resolution lifespan
Can borrow ideas from the public Atropos code (github.com/Astrolavos/Atropos)
D: Pivot engine
Given a seed, finds related infrastructure and records why.
Builds a graph: domains ↔ IPs ↔ NS/MX, with time windows, skipping infrastructure C labeled as noise
Pivot 1, IP co-residency: other domains on the same non-shared IP within an overlapping time window
Pivot 2, NS/MX reuse: domains sharing uncommon name servers or mail servers with the seed
Pivot 3, fingerprint match: registrar + hosting ASN + aging/timing pattern similar to the seed's cluster
Every result goes to pivot_results.jsonl with its evidence and a raw per-method score
E: Scoring, evaluation & demo
Turns pivot evidence into ranked leads and proves the tool works.
Confidence score: a weighted combination of pivot evidence, discounting shared infrastructure (high domain_count) and evidence far apart in time
Evaluation harness: for each actor, seed one domain and measure precision and recall against ground truth, per method and combined
Runs every scenario from B and builds the results tables (which methods hold up as actors get stealthier)
CLI: pivot <seed> → ranked candidates with scores and reasons; a simple graph visualization if time allows
Assembles the final presentation and report







Workflow & timeline
Work moves in one direction through shared files, so each role can build against mock data from Day 1 and switch to real simulator output once it lands.
B's configs drive A's simulator; C, D and E each read the previous stage's output. Ground truth goes straight to E, so the filter and pivots can't peek at the answers.
Days 1–2: Setup. Agree on the data contract, create the repo and load_data.py, and commit mock files. A ships a small simulated dataset; B writes the first actor config; the group picks the showcase actor.
Days 3–7: Build. Each role builds its stage against the shared files. Checkpoint on Day 4: the pipeline runs on the small dataset, even if crudely. Checkpoint on Day 7: full pipeline end-to-end, first precision/recall numbers.
Days 8–11: Harden. B adds the harder scenarios; C and D tune filters and pivots; E tunes score weights and builds the method comparison tables. Checkpoint on Day 11: results frozen.
Days 12–14: Demo. CLI polish, graph visualization if time allows, slides and report, and a rehearsed walkthrough: showcase actor seed → discovered infrastructure → scores and evidence.
Team practices
One repo, with folders sim/, filter/, pivot/, eval/, data/, output/, and load_data.py at the top level.
Branch per role, merged to main at least every other day. main must always run end-to-end.
Short async standup in the group chat each day: done, next, blocked.
Integration checkpoints on Days 4, 7 and 11: one person runs the whole pipeline from scratch on fresh data and posts the output.
Showcase actor: pick one planted actor on Day 1. Everyone tests against it, and it becomes the demo walkthrough.
Reproducible runs: every dataset is regenerated from a config file and a random seed, never hand-edited.
Done means a fresh clone can run make all (or one script): generate data → filter → pivot → score → print the results tables. And pivot <seed> returns ranked, explained candidates for the showcase actor.
