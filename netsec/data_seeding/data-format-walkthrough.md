# Data format walkthrough

This explains what each file in `data-format.md` means and how the pieces fit together, using one
fake attacker domain as a running example.

---

## 1. The big picture

We're building a small version of Validin. Validin's core product is a giant history of
**"domain X pointed to Y between these dates."** Analysts start from one known-bad domain and follow
what it shares (IPs, name servers, mail servers) to find more bad domains. That's called **pivoting**.

We don't have Validin's real data, so a simulator generates a fake internet: thousands of normal
domains, some noise (parking pages, CDNs, sinkholes), and a few planted fake APTs. Because we planted
them, we know the right answers and can measure exactly how well our pivots work.

The files fall into three groups:

| Group | Files | Purpose |
|---|---|---|
| **The data** | `resolutions.jsonl`, `infra.json`, `domains.json` | What a Validin-like collector would actually give you |
| **Simulation scaffolding** | `actors/*.json`, `ground_truth.json`, `manifest.json` | Recipes for the fake APTs, the answer key, and how the data was made |
| **Our tool's outputs** | `output/infra_labels.json`, `output/pivot_results.jsonl` | What the filter and pivot engine produce |

---

## 2. Quick DNS refresher

Every line of DNS data has a **record type** (`rrtype`). We use four:

| rrtype | Question it answers | Example value |
|---|---|---|
| `A` | What IPv4 address does this domain point to? | `45.77.12.9` |
| `AAAA` | What IPv6 address does it point to? | `2a05:f480:1c00::8` |
| `NS` | Which name server is in charge of this domain's DNS? | `ns1.dnssvc-cloud.net` |
| `MX` | Which mail server receives its email? | `mx.dnssvc-cloud.net` |

Attackers change domain names constantly, but the things behind them (IPs, name servers, mail
servers) cost money and effort, so they get reused. That reuse is what we pivot on.

---

## 3. The main file: `resolutions.jsonl`

Each line is one observation: *"a sensor saw this domain point to this value from `first_seen` to
`last_seen`."*

Here's the life of one fake attacker domain, `update-svc.com`, as it would appear:

```json
{"domain": "update-svc.com", "rrtype": "A",  "value": "198.51.7.20",          "first_seen": "2023-08-15", "last_seen": "2024-02-28", "source": "forward"}
{"domain": "update-svc.com", "rrtype": "NS", "value": "ns1.parkingcrew.net",  "first_seen": "2023-08-15", "last_seen": "2024-02-28", "source": "forward"}
{"domain": "update-svc.com", "rrtype": "A",  "value": "45.77.12.9",           "first_seen": "2024-03-02", "last_seen": "2024-05-18", "source": "forward"}
{"domain": "update-svc.com", "rrtype": "A",  "value": "45.77.12.9",           "first_seen": "2024-03-19", "last_seen": "2024-05-16", "source": "passive"}
{"domain": "update-svc.com", "rrtype": "NS", "value": "ns1.dnssvc-cloud.net", "first_seen": "2024-03-02", "last_seen": "2024-05-18", "source": "forward"}
{"domain": "update-svc.com", "rrtype": "MX", "value": "mx.dnssvc-cloud.net",  "first_seen": "2024-03-02", "last_seen": "2024-05-18", "source": "forward"}
```

Reading it as a story:

1. **Aug 2023 – Feb 2024: parked.** The domain was registered and sat on a parking page
   (`198.51.7.20`, `ns1.parkingcrew.net`) for about 6 months. APTs often let domains "age" so they
   look less suspicious when they're finally used.
2. **Mar – May 2024: operational.** It switched to the attacker's server (`45.77.12.9`) and the
   attacker's own name server and mail server. This is the window where it was used in an attack.
3. **After May 2024:** no more records. The attacker abandoned it.

A domain usually has several lines at once (an A, an NS, maybe an MX), and lines change over time
as the domain moves.

### `source`: passive vs forward

Notice `45.77.12.9` appears twice with different dates:

- **`forward`** (Mar 2): a scanner looked the domain up on its own, like Validin does. It sees
  domains even when nobody is visiting them, including parked ones.
- **`passive`** (Mar 19): seen because real users' DNS queries passed through a sensor. It only
  shows up once victims start connecting, so it's later, and it often misses quiet domains entirely.

That 17-day gap is the "forward DNS finds things earlier" idea from our project title, and this
field is what lets us measure it.

---

## 4. Looking up the infrastructure: `infra.json`

`resolutions.jsonl` tells you `update-svc.com` used `45.77.12.9`. `infra.json` tells you about
`45.77.12.9` itself:

```json
"45.77.12.9":     {"type": "ipv4", "asn": 20473, "org": "The Constant Company, LLC", "country": "US", "domain_count": 3,   "label": "unknown"}
"104.18.3.7":     {"type": "ipv4", "asn": 13335, "org": "Cloudflare, Inc.",          "country": "US", "domain_count": 412, "label": "unknown"}
```

- **`asn` / `org` / `country`**: who owns the network the IP lives in. Here, a budget VPS provider
  vs. Cloudflare.
- **`domain_count`**: how many domains have ever used this value. This is the most important number
  for pivoting:
  - `412` domains on a Cloudflare IP: it's a CDN. Sharing it with a bad domain means nothing.
  - `3` domains on a cheap VPS IP: if one of them is bad, the other two are worth a look.
- **`label`**: always `"unknown"`. Real data doesn't come labeled. Figuring out "this is parking /
  CDN / worth investigating" is the filter's job.

There's one entry for every IP, name server and mail server that appears anywhere in
`resolutions.jsonl`.

---

## 5. Domain registration info: `domains.json`

This is WHOIS data: who sold the domain and when.

```json
"update-svc.com": {
  "registrar": "NameCheap, Inc.",
  "registered": "2023-08-14",
  "registrations": [
    {"registrar": "NameCheap, Inc.", "registered": "2023-08-14", "expired": null}
  ]
}
```

The registration date matters because of **domain aging**: `update-svc.com` was registered on
Aug 14, 2023 but only became operational on Mar 2, 2024, about 200 days later. Normal websites
usually go live within days.

`registrations` is a history because domains can expire and be bought again by someone else. A
domain re-registered last year shouldn't count as a 10-year-old domain:

```json
"oakvalley.com": {
  "registrar": "GoDaddy.com, LLC",
  "registered": "2024-06-02",
  "registrations": [
    {"registrar": "Tucows Domains Inc.", "registered": "2016-03-11", "expired": "2024-01-20"},
    {"registrar": "GoDaddy.com, LLC",    "registered": "2024-06-02", "expired": null}
  ]
}
```

---

## 6. Could you get this from real collection?

| File / field | Real-world source |
|---|---|
| `resolutions.jsonl` | Passive DNS providers (Validin etc.) or your own scanning. Yes. |
| `source` | Yes if you collect yourself; a provider's export may not split it. |
| `infra.json` asn / org / country | Free IP-to-ASN databases. Yes. |
| `infra.json` domain_count | Count it from your own resolution data. Yes. |
| `infra.json` label | Nobody gives you this. That's the filter's job. |
| `domains.json` registrar / registered | WHOIS / RDAP lookups. Mostly yes. |
| `domains.json` registrations history | Only from paid historical WHOIS. |
| `actors/*.json`, `ground_truth.json`, `manifest.json` | Don't exist in real life. Simulation only. |

So the filter, pivot and scoring code would run on real data unchanged. The simulation-only files
exist to create the fake world and grade our results.

---

## 7. Simulation scaffolding

### `actors/*.json`: recipes for fake APTs

Each file describes how one fake APT behaves, and the simulator follows it to plant that actor's
domains in the data. For example, AMBER_KITE:

| Setting | Value | Meaning |
|---|---|---|
| `aging_days` | mean 200 | Waits ~200 days between buying a domain and using it |
| `park_first_rate` | 0.6 | 60% of its domains sit on parking pages while aging |
| `ip_reuse_rate` | 0.65 | 65% of new domains reuse an IP it already has |
| `custom_ns` | `ns1/ns2.dnssvc-cloud.net`, rate 0.7 | 70% of its domains use its own name servers |
| `hosting_asns` | Vultr, M247, Contabo | Prefers these budget VPS providers |
| `end_state` | sinkhole / parking / abandon | What happens to domains after the attack |

The `update-svc.com` story in section 3 is exactly this recipe in action.

### `ground_truth.json`: the answer key

Lists the real answers: every domain and IP each actor owns, and the true label of every IP and
server (CDN, parking, actor, ...). **Only the evaluation code reads this.** If the filter or pivots
read it, they're cheating and the results are meaningless.

### `manifest.json`: how this dataset was made

Records the random seed and settings. Running the simulator with the same manifest settings
produces exactly the same data.

---

## 8. Our tool's outputs

### `output/infra_labels.json`: the filter's verdicts

The filter reads the data and decides which infrastructure is noise:

```json
"infra": {
  "198.51.7.20": {"label": "parking",   "confidence": 0.95, "reasons": ["domain_count=812", "parking NS"]},
  "104.18.3.7":  {"label": "cdn",       "confidence": 0.9,  "reasons": ["domain_count=412", "CDN ASN"]},
  "45.77.12.9":  {"label": "candidate", "confidence": 0.7,  "reasons": ["domain_count=3", "VPS ASN"]}
},
"domains": {
  "update-svc.com": {"aging_days": 201, "first_candidate_ip": "2024-03-02", "max_lifespan_days": 77}
}
```

`candidate` means "not obviously noise, worth pivoting on." The pivot engine skips everything else.
The `domains` part holds timing stats like aging (registration → first real use).

### `output/pivot_results.jsonl`: what the pivots found

Start from `update-svc.com` and look for related domains:

```json
{"seed": "update-svc.com", "candidate": "cdn-sync.net",   "method": "ip_coresidency",    "evidence": {"shared": "45.77.12.9", "overlap_days": 41}, "score": 0.82}
{"seed": "update-svc.com", "candidate": "patch-agent.com", "method": "ns_mx_reuse",       "evidence": {"shared_ns": "ns1.dnssvc-cloud.net"},         "score": 0.9}
{"seed": "update-svc.com", "candidate": "auth-portal.net", "method": "fingerprint_match", "evidence": {"registrar": "NameCheap, Inc.", "asn": 20473, "aging_days": 188}, "score": 0.55}
```

- **`ip_coresidency`**: `cdn-sync.net` used the same non-shared IP at overlapping times.
- **`ns_mx_reuse`**: `patch-agent.com` used the same rare name server.
- **`fingerprint_match`**: `auth-portal.net` shares nothing directly, but looks the same: same
  registrar, same hosting provider, similar aging.

`score` is how confident each method is (0–1). The evaluation stage combines scores into one ranking
and checks the results against the answer key.

---

## 9. Rules everyone follows

- Dates are always `YYYY-MM-DD`.
- Domains and hostnames are lowercase with no trailing dot.
- Read and write files only through `load_data.py`, so a format change is fixed in one place.
- Only the evaluation code opens `ground_truth.json`.
- Change the format only by group agreement.

## 10. Who touches what

```
actors/*.json ──► simulator ──► resolutions / infra / domains ──► filter ──► infra_labels ──► pivot ──► pivot_results ──► eval
                       └──────────────────────────► ground_truth ───────────────────────────────────────────────────────────┘
```
