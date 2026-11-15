# Seed data generator

`sim/simulate.py` builds the synthetic DNS world in `data/`. The committed seed data is
one run of it (seed 6262). Standard library only.

## Files

| Path | Purpose |
| --- | --- |
| `sim/simulate.py` | The generator |
| `sim/actors/*.json` | Planted APT profiles (simulator input, not pivot features) |
| `validate_data.py` | Checks a dataset against [data-format.md](../data-format.md) |

## Run from the repository root

```sh
python3 sim/simulate.py          # rebuilds both data/seed-data_* folders
python3 validate_data.py         # checks data/seed-data_no-ground-truth
python3 validate_data.py data/seed-data_with-ground-truth
```

With the default seed and the committed actor profiles, the output is byte-identical to the
committed data, so rerunning it changes nothing.

One run writes two folders:

| Folder | Contents | For |
| --- | --- | --- |
| `data/seed-data_no-ground-truth/` | `resolutions.jsonl`, `infra.json`, `domains.json`, `manifest.json` | Filter and pivot development |
| `data/seed-data_with-ground-truth/` | The same, plus `ground_truth.json` and `actors/` | Evaluation only |

Other datasets (new seed, smaller test set, extra scenarios) go in their own folders so the
shared seed data stays intact:

```sh
python3 sim/simulate.py --seed 7 --public-out data/seed7_no-gt --out data/seed7_with-gt
python3 sim/simulate.py --benign 500 --public-out data/small_no-gt --out data/small_with-gt
python3 sim/simulate.py --actors scenarios/low_reuse --public-out data/low-reuse_no-gt --out data/low-reuse_with-gt
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--seed` | 6262 | Random seed; same seed gives the same world |
| `--benign` | 5000 | Benign domains (plus ~40 small hosting companies' own domains) |
| `--crimeware` | 40 | Non-APT malicious domains (short-lived, mostly sinkholed) |
| `--actors` | `sim/actors` | Folder of actor profiles to plant |
| `--public-out` | `data/seed-data_no-ground-truth` | Folder without ground truth |
| `--out` | `data/seed-data_with-ground-truth` | Folder with ground truth; `--out ""` skips it |

## What the world contains

Simulated window: 2022-01-01 to 2025-12-31.

- **Benign owners** that behave like real registrants:
  - individuals (1–2 sites, many abandoned within a year)
  - businesses (1–4 sites, sometimes their own `ns1.<domain>`)
  - agencies (5–20 client sites on 1–3 shared servers)
  - domain investors (5–25 parked domains registered in bursts)
  - startups (2–6 domains registered together, often short-lived)
- **40 small hosting companies** with their own name servers, shared by a few to a few dozen sites.
- **Churn:** late launches, CDN edge IPs rotating, hosting moves, expiry, drop-catch parking.
- **Noise infrastructure:** CDNs, shared hosting, parking pages, sinkholes, 40 crimeware domains.
- **Two planted actors** (`sim/actors/`):
  - `AMBER_KITE`: long aging, parks first, reuses budget-VPS IPs, runs its own name servers.
  - `SLATE_HERON`: short aging, little IP reuse, often behind CDNs, reuses one custom mail server.
- **Two sensors:** `forward` (active scanning, sees quiet domains within days) and `passive`
  (only sees domains with real traffic, later). Forward sees actor infrastructure 17–20 days
  earlier (median) in the seed data.

## Actors don't stand out on any single field

Actors use the same name generator, registrars, hosting, lifecycle and sensor rules as benign
domains; only their habits differ. How well each per-domain feature alone separates actor from
benign domains in the seed data (AUC: 0.5 = no signal, 1.0 = perfect giveaway):

| Feature | AUC |
| --- | --- |
| Name length, hyphens, digits | 0.46–0.59 |
| Privacy registrar | 0.59 |
| Ever parked, re-registered | 0.50–0.53 |
| Smallest IP / NS domain_count | 0.41–0.48 |
| Has MX | 0.67 |
| Aging (registration → live) | 0.72 |
| Short live time (domains registered 2022+) | 0.69 |
| Number of records, passive lag | 0.75–0.84 |

The higher ones are real APT tendencies the project is meant to use, but none suffices alone.
Each pivot also has look-alikes: 232 benign name servers are shared by 5–40 domains (like
AMBER_KITE's), and 258 benign dedicated IPs are shared by 2–6 domains (like actor IP reuse).

## Adding an actor

Copy `sim/actors/amber_kite.json` and edit it. Fields are listed in `data-format.md`. Registrars
and hosting ASNs must be ones the simulator knows (`REGISTRARS` and `ASNS` at the top of
`simulate.py`). Write the result to a new folder rather than overwriting the shared seed data
unless the team agrees.

## Limitations

- 5,000 domains is far smaller than real passive DNS.
- Not modeled: IP recycling between customers, TLS certificates and HTTP banners, DNS TTLs,
  actors changing behaviour partway through.
- Parameters are loosely based on published findings (Atropos); the data makes no claims about
  real APT behaviour.
