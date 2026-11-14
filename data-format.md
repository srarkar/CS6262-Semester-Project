# Data format v0.1

Dates: `YYYY-MM-DD`. Domains/hostnames: lowercase, no trailing dot.
All files are read/written through `load_data.py`. Only eval reads `ground_truth.json`.

| File | Written by | Read by |
|---|---|---|
| `data/resolutions.jsonl` | Simulator | Filter, Pivot |
| `data/infra.json` | Simulator | Filter, Pivot |
| `data/domains.json` | Simulator | Filter, Pivot |
| `data/manifest.json` | Simulator | Everyone |
| `data/actors/*.json` | Actor profiles | Simulator |
| `data/ground_truth.json` | Simulator + Actor profiles | Eval only |
| `output/infra_labels.json` | Filter | Pivot |
| `output/pivot_results.jsonl` | Pivot | Eval |

---

## `data/resolutions.jsonl`

One JSON object per line.

| Field | Type | Values |
|---|---|---|
| `domain` | string | domain name |
| `rrtype` | string | `A`, `AAAA`, `NS`, `MX` |
| `value` | string | IPv4 (A), IPv6 (AAAA), name server host (NS), mail server host (MX) |
| `first_seen` | date | |
| `last_seen` | date | `>= first_seen` |
| `source` | string | `passive`, `forward` |

```json
{"domain": "update-svc.com", "rrtype": "A", "value": "45.77.12.9", "first_seen": "2024-03-02", "last_seen": "2024-05-18", "source": "forward"}
{"domain": "update-svc.com", "rrtype": "NS", "value": "ns1.dnssvc-cloud.net", "first_seen": "2024-03-02", "last_seen": "2024-05-18", "source": "passive"}
```

## `data/infra.json`

Object keyed by every `value` in `resolutions.jsonl`.

| Field | Type | Values |
|---|---|---|
| `type` | string | `ipv4`, `ipv6`, `ns`, `mx` |
| `asn` | int | |
| `org` | string | |
| `country` | string | 2-letter code |
| `domain_count` | int | number of distinct domains that resolved to this value |
| `label` | string | always `unknown` |

```json
{
 "45.77.12.9": {"type": "ipv4", "asn": 20473, "org": "The Constant Company, LLC", "country": "US", "domain_count": 3, "label": "unknown"}
}
```

## `data/domains.json`

Object keyed by domain.

| Field | Type | Values |
|---|---|---|
| `registrar` | string | latest registration's registrar |
| `registered` | date | latest registration's date |
| `registrations` | list | oldest first: `{"registrar", "registered", "expired"}`, `expired` is a date or `null` |

```json
{
 "update-svc.com": {
  "registrar": "NameCheap, Inc.",
  "registered": "2023-08-14",
  "registrations": [{"registrar": "NameCheap, Inc.", "registered": "2023-08-14", "expired": null}]
 }
}
```

## `data/manifest.json`

```json
{
 "format_version": "0.1",
 "seed": 6262,
 "world_start": "2022-01-01",
 "world_end": "2025-12-31",
 "params": {"benign": 5000, "crimeware": 40, "n_actor_configs": 2},
 "counts": {"resolutions": 43360, "domains": 5138, "infra": 3284}
}
```

## `data/actors/<actor>.json`

| Field | Type | Values |
|---|---|---|
| `name` | string | `UPPER_SNAKE` |
| `n_domains` | int | |
| `campaign_windows` | list | `{"start", "end"}` dates |
| `registrars` | object | `{registrar: weight}` |
| `hosting_asns` | object | `{asn: weight}` |
| `ip_reuse_rate` | float | 0–1 |
| `ipv6_rate` | float | 0–1 |
| `cdn_fronting_rate` | float | 0–1 |
| `aging_days` | object | `{"mean", "std"}` |
| `active_days` | object | `{"mean", "std"}` |
| `park_first_rate` | float | 0–1 |
| `custom_ns` | object | `{"hosts": [...], "rate": 0–1}` |
| `custom_mx` | object | `{"hosts": [...], "rate": 0–1}` |
| `naming` | object | `{"styles": {style: weight}, "words": [...], "tlds": {tld: weight}}`; styles: `lure`, `tech`, `brandable`, `business`, `person`, `short`, `numbers` |
| `end_state` | object | `{"sinkhole", "parking", "abandon"}` weights |

```json
{
 "name": "AMBER_KITE",
 "n_domains": 30,
 "campaign_windows": [{"start": "2022-06-01", "end": "2022-12-31"}],
 "registrars": {"NameCheap, Inc.": 5, "Njalla": 3},
 "hosting_asns": {"20473": 5, "9009": 3},
 "ip_reuse_rate": 0.65,
 "ipv6_rate": 0.2,
 "cdn_fronting_rate": 0.1,
 "aging_days": {"mean": 200, "std": 60},
 "active_days": {"mean": 120, "std": 80},
 "park_first_rate": 0.6,
 "custom_ns": {"hosts": ["ns1.dnssvc-cloud.net", "ns2.dnssvc-cloud.net"], "rate": 0.7},
 "custom_mx": {"hosts": ["mx.dnssvc-cloud.net"], "rate": 0.4},
 "naming": {"styles": {"lure": 4, "tech": 3, "brandable": 2}, "words": ["update", "svc", "sync", "cdn"], "tlds": {"com": 5, "net": 3}},
 "end_state": {"sinkhole": 0.25, "parking": 0.35, "abandon": 0.4}
}
```

## `data/ground_truth.json`

| Field | Type | Values |
|---|---|---|
| `actors` | object | `{actor: {"domains", "ips", "ns_hosts", "mx_hosts", "cdn_fronted_domains"}}` (lists) |
| `domain_labels` | object | `{domain: "benign" \| "crimeware" \| "actor:<NAME>"}` |
| `infra_labels` | object | `{value: label}`, label is one of `cdn`, `shared_hosting`, `dedicated`, `parking`, `sinkhole`, `actor`, `dns_provider`, `registrar_ns`, `hosting_ns`, `self_hosted_ns`, `mail_provider`, `self_hosted_mail` |

```json
{
 "actors": {
  "AMBER_KITE": {
   "domains": ["update-svc.com"],
   "ips": ["45.77.12.9"],
   "ns_hosts": ["ns1.dnssvc-cloud.net"],
   "mx_hosts": ["mx.dnssvc-cloud.net"],
   "cdn_fronted_domains": []
  }
 },
 "domain_labels": {"update-svc.com": "actor:AMBER_KITE", "bakery-hub.com": "benign"},
 "infra_labels": {"45.77.12.9": "actor", "104.18.3.7": "cdn"}
}
```

---

## `output/infra_labels.json`

| Field | Type | Values |
|---|---|---|
| `infra` | object | `{value: {"label", "confidence", "reasons"}}`, label is one of `parking`, `sinkhole`, `cdn`, `shared_hosting`, `candidate`; confidence 0–1; reasons is a list of strings |
| `domains` | object | `{domain: {"aging_days", "first_candidate_ip", "max_lifespan_days"}}`, values may be `null` |

```json
{
 "infra": {
  "45.77.12.9": {"label": "candidate", "confidence": 0.7, "reasons": ["domain_count=3"]}
 },
 "domains": {
  "update-svc.com": {"aging_days": 201, "first_candidate_ip": "2024-03-02", "max_lifespan_days": 77}
 }
}
```

## `output/pivot_results.jsonl`

One JSON object per line.

| Field | Type | Values |
|---|---|---|
| `seed` | string | domain or IP |
| `candidate` | string | domain or IP |
| `method` | string | `ip_coresidency`, `ns_mx_reuse`, `fingerprint_match` |
| `evidence` | object | method-specific |
| `score` | float | 0–1 |

```json
{"seed": "update-svc.com", "candidate": "cdn-sync.net", "method": "ip_coresidency", "evidence": {"shared": "45.77.12.9", "overlap_days": 41}, "score": 0.82}
```
