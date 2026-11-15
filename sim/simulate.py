"""Stage A: generate the synthetic DNS world (see data-format.md and sim/README.md).

Run from the repository root:

    python sim/simulate.py     # rebuilds both data/seed-data_* folders (seed 6262)
    python sim/simulate.py --seed 7 --public-out data/seed7_no-gt --out data/seed7_with-gt

Same seed + same actor configs (sim/actors/) + same args => byte-identical output.

Design goal: no single field gives the actors away. Benign domains come from "owners"
(individuals, businesses, agencies, domain investors, startups) who also register domains in
batches, park them, launch late, abandon projects, share one server across several sites and run
their own name servers. Actors go through the same name generator, the same lifecycle helpers and
the same sensor model, and differ only in the habits set in data/actors/*.json.

What the world contains:
- benign domains grouped by owner, on shared hosting, small reseller hosts, CDNs, cloud and VPS
- parking (registrar landing pages, domain investor portfolios) and sinkhole infrastructure
- "crimeware" domains: short-lived non-APT malicious noise, mostly sinkholed
- planted APT actors, driven by data/actors/*.json
- two sensors: passive DNS (sees domains with real traffic, with a delay) and forward DNS
  (Validin-style active scanning: also sees quiet/staging domains, usually earlier)
"""
from __future__ import annotations

import argparse
import ipaddress
import random
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SIM_DIR.parent))
import load_data as ld  # noqa: E402

WORLD_START = date(2022, 1, 1)
WORLD_END = date(2025, 12, 31)

# asn: (org, country, kind). kind drives how the simulator uses it.
ASNS = {
    13335: ("Cloudflare, Inc.", "US", "cdn"),
    20940: ("Akamai International B.V.", "NL", "cdn"),
    54113: ("Fastly, Inc.", "US", "cdn"),
    16509: ("Amazon.com, Inc.", "US", "cloud"),
    15169: ("Google LLC", "US", "cloud"),
    8075: ("Microsoft Corporation", "US", "cloud"),
    26496: ("GoDaddy.com, LLC", "US", "shared"),
    46606: ("Unified Layer", "US", "shared"),
    22612: ("Namecheap, Inc.", "US", "shared"),
    47583: ("Hostinger International Limited", "LT", "shared"),
    14061: ("DigitalOcean, LLC", "US", "vps"),
    20473: ("The Constant Company, LLC", "US", "vps"),
    16276: ("OVH SAS", "FR", "vps"),
    24940: ("Hetzner Online GmbH", "DE", "vps"),
    63949: ("Akamai Connected Cloud", "US", "vps"),
    9009: ("M247 Europe SRL", "RO", "vps"),
    51167: ("Contabo GmbH", "DE", "vps"),
    15348: ("Tucows.com Co.", "CA", "dns"),
    29169: ("Gandi SAS", "FR", "dns"),
    2639: ("Zoho Corporation", "US", "mail"),
    64500: ("Synthetic Parking Services", "US", "parking"),   # documentation-range ASNs:
    64501: ("Synthetic Sinkhole Operator", "US", "sinkhole"),  # obviously fake on purpose
}
KIND_ASNS = defaultdict(list)
for _asn, (_o, _c, _k) in ASNS.items():
    KIND_ASNS[_k].append(_asn)

# registrar: (weight for benign domains, ASN its default name servers live in)
REGISTRARS = {
    "GoDaddy.com, LLC": (30, 26496),
    "NameCheap, Inc.": (20, 22612),
    "Tucows Domains Inc.": (8, 15348),
    "Porkbun LLC": (7, 16509),
    "Squarespace Domains LLC": (8, 15169),
    "Cloudflare, Inc.": (8, 13335),
    "Hostinger Operations, UAB": (7, 47583),
    "NameSilo, LLC": (5, 13335),
    "Gandi SAS": (4, 29169),
    "OVH sas": (3, 16276),
    "Njalla": (1, 9009),  # privacy registrar: over-represented among actors, but not exclusive
}
BENIGN_REGISTRARS = {k: v[0] for k, v in REGISTRARS.items()}

# ---------------------------------------------------------------- naming
GENERIC = ["acme", "alpha", "bay", "bear", "blue", "bright", "city", "coast", "craft", "creek",
           "delta", "eagle", "east", "eco", "farm", "first", "fox", "fresh", "garden", "global",
           "gold", "green", "health", "hill", "home", "island", "joy", "lake", "life", "lion",
           "local", "market", "media", "metro", "moon", "north", "oak", "ocean", "one", "peak",
           "pine", "pixel", "prime", "pro", "quick", "red", "river", "rock", "sage", "smart",
           "solar", "south", "spark", "star", "stone", "sun", "travel", "tree", "true", "urban",
           "valley", "vista", "wave", "west", "wild", "wolf", "works", "yoga", "zen", "daily",
           "news", "press", "forum", "report", "policy", "summit", "world", "voice", "times"]
TECH = ["cloud", "sync", "auth", "login", "portal", "app", "api", "data", "secure", "net", "hub",
        "soft", "labs", "systems", "digital", "update", "mail", "drive", "office", "service",
        "svc", "connect", "link", "host", "web", "online", "tech", "dev", "ops", "stack", "code",
        "byte", "logic", "verify", "account", "pay", "support", "help", "desk", "remote", "vpn",
        "agent", "patch", "cdn", "telemetry", "edge", "node", "server", "box", "files", "share",
        "docs", "meet", "team", "analytics", "track", "status", "monitor", "backup", "safe"]
BUSINESS = ["law", "dental", "realty", "plumbing", "cafe", "bakery", "studio", "consulting",
            "fitness", "salon", "auto", "roofing", "clinic", "group", "partners", "accounting",
            "photo", "designs", "builders", "insurance", "travel", "events", "academy", "foods",
            "ministry", "embassy", "visa", "conference", "institute", "foundation"]
PLACES = ["austin", "denver", "boston", "portland", "atlanta", "miami", "dallas", "seattle",
          "phoenix", "chicago", "berlin", "london", "toronto", "sydney", "lyon", "oslo", "dublin",
          "madrid", "kyiv", "seoul", "taipei", "delhi", "dubai", "vienna"]
FIRST = ["john", "maria", "alex", "sarah", "david", "emma", "li", "chen", "raj", "priya", "omar",
         "fatima", "lucas", "sofia", "noah", "mia", "ivan", "olga", "kenji", "yuki", "anna", "max"]
LAST = ["smith", "garcia", "kim", "nguyen", "patel", "mueller", "rossi", "silva", "cohen",
        "tanaka", "ivanov", "brown", "lee", "khan", "martin", "lopez", "novak", "park"]
SYLLABLES = ["zen", "tra", "vo", "lix", "qua", "ro", "nex", "ti", "ka", "mo", "ly", "sor", "vex",
             "dra", "po", "fy", "ar", "io", "um", "zo", "ri", "ta", "ne", "va", "lo", "xa"]
ALNUM = "abcdefghijklmnopqrstuvwxyz0123456789"

BENIGN_STYLES = {"brandable": 26, "business": 20, "tech": 22, "person": 10, "short": 14, "numbers": 5, "lure": 3}
BENIGN_LURE_WORDS = TECH  # benign IT/SaaS sites also use "lure-ish" names
BENIGN_TLDS = {"com": 55, "net": 9, "org": 9, "io": 4, "co": 4, "info": 3, "xyz": 3, "shop": 2,
               "online": 2, "de": 3, "co.uk": 3, "ca": 2, "fr": 1, "nl": 1}
CRIME_TLDS = {"top": 4, "xyz": 3, "shop": 2, "online": 2, "click": 2, "icu": 1, "com": 3}

# ---------------------------------------------------------------- infrastructure
CF_NAMES = ["ada", "bob", "cruz", "dana", "elle", "fred", "gina", "hank", "ivy", "jay",
            "kate", "leo", "mia", "nash", "olga", "pete", "rita", "sam", "tess", "vick"]
PARKING_PROVIDERS = [  # (ns hosts, number of landing-page IPs)
    (["ns1.parkingcrew.net", "ns2.parkingcrew.net"], 3),
    (["ns1.bodis.com", "ns2.bodis.com"], 3),
    (["ns1.sedoparking.com", "ns2.sedoparking.com"], 2),
]
SINKHOLE_NS = ["ns1.sinkhole-op.org", "ns2.sinkhole-op.org"]
MX_PROVIDERS = {  # name: (weight, asn)
    "google": (40, 15169), "outlook": (25, 8075), "privateemail": (10, 22612),
    "zoho": (10, 2639), "hostinger": (8, 47583), "self": (7, None),
}

# ---------------------------------------------------------------- benign owners
# type: (weight, domain count range, registration spread in days, hosting kind weights,
#        share of popular domains, probability a domain is a short-lived project)
OWNER_TYPES = {
    "individual": (45, (1, 2), 400, {"shared": 45, "cdn": 25, "vps": 15, "cloud": 15}, 0.25, 0.45),
    "business":   (33, (1, 4), 700, {"shared": 30, "cdn": 25, "cloud": 25, "vps": 20}, 0.45, 0.15),
    "agency":     (7, (5, 20), 1400, {"vps": 70, "cloud": 30}, 0.10, 0.25),
    "investor":   (8, (5, 25), 0, {}, 0.0, 0.0),
    "startup":    (7, (2, 6), 60, {"cloud": 50, "cdn": 40, "vps": 10}, 0.30, 0.55),
}


class World:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.segments: list[tuple] = []          # (domain, rrtype, value, start, end, quiet)
        self.meta: dict[str, dict] = {}          # value -> {type, asn, org, country}
        self.truth: dict[str, str] = {}          # value -> true infra label
        self.regs: dict[str, list[dict]] = {}    # domain -> registrations
        self.domain_labels: dict[str, str] = {}
        self.popular: dict[str, bool] = {}       # drives passive DNS visibility
        self.used_ips: set[str] = set()
        self._v4_prefix: dict[int, tuple[int, int]] = {}
        self._v6_prefix: dict[int, str] = {}
        taken = set()
        for asn in sorted(ASNS):
            while True:
                a, b = self.rng.randint(23, 223), self.rng.randint(0, 255)
                if a not in (100, 127, 169, 172, 192, 198, 203) and (a, b) not in taken:
                    taken.add((a, b))
                    break
            self._v4_prefix[asn] = (a, b)
            self._v6_prefix[asn] = f"2a0{self.rng.randint(1, 9)}:{self.rng.randint(0x1000, 0xffff):x}"
        self._build_shared_pools()
        self._build_resellers(40)

    # ------------------------------------------------------------ primitives

    def wchoice(self, weights: dict):
        keys = list(weights)
        return self.rng.choices(keys, weights=[float(weights[k]) for k in keys])[0]

    def rand_date(self, a: date, b: date) -> date:
        return a + timedelta(days=self.rng.randint(0, max(0, (b - a).days)))

    def _register(self, value: str, typ: str, asn: int, label: str) -> str:
        org, country, _ = ASNS[asn]
        if value not in self.meta:
            self.meta[value] = {"type": typ, "asn": asn, "org": org, "country": country}
        self.truth.setdefault(value, label)
        return value

    def new_v4(self, asn: int, label: str) -> str:
        a, b = self._v4_prefix[asn]
        while True:
            ip = f"{a}.{b}.{self.rng.randint(0, 255)}.{self.rng.randint(1, 254)}"
            if ip not in self.used_ips:
                self.used_ips.add(ip)
                return self._register(ip, "ipv4", asn, label)

    def new_v6(self, asn: int, label: str) -> str:
        p = self._v6_prefix[asn]
        while True:
            raw = f"{p}:{self.rng.randint(0, 0xffff):x}::{self.rng.randint(1, 0xffff):x}"
            ip = str(ipaddress.ip_address(raw))
            if ip not in self.used_ips:
                self.used_ips.add(ip)
                return self._register(ip, "ipv6", asn, label)

    def host(self, name: str, typ: str, asn: int, label: str) -> str:
        return self._register(name, typ, asn, label)

    def seg(self, domain, rrtype, value, start, end, quiet=False):
        if start <= end and end >= WORLD_START and start <= WORLD_END:
            self.segments.append((domain, rrtype, value, start, end, quiet))

    def add_domain(self, domain, registrar, registered, label, popular):
        self.regs[domain] = [{"registrar": registrar, "registered": registered, "expired": None}]
        self.domain_labels[domain] = label
        self.popular[domain] = popular

    # ------------------------------------------------------------ names

    def name(self, style: str, words=None, tlds=None) -> str:
        r = self.rng
        if style == "brandable":
            w1, w2 = r.sample(GENERIC, 2)
            base = r.choice([w1 + w2, f"{w1}-{w2}"])
        elif style == "business":
            a = r.choice([r.choice(PLACES), r.choice(LAST), r.choice(GENERIC)])
            b = r.choice(BUSINESS)
            base = r.choice([a + b, f"{a}-{b}"])
        elif style == "tech":
            a, b = r.choice(TECH), r.choice(TECH + GENERIC)
            if a == b:
                b = r.choice(GENERIC)
            base = r.choice([a + b, f"{a}-{b}", f"{a}{b}{r.randint(1, 9)}", b + a])
        elif style == "person":
            f, l_ = r.choice(FIRST), r.choice(LAST)
            base = r.choice([f + l_, f"{f}-{l_}", f"{f}{l_}{r.randint(1, 99)}"])
        elif style == "short":
            base = "".join(r.choices(SYLLABLES, k=r.randint(2, 3)))
        elif style == "numbers":
            base = f"{r.choice(GENERIC + TECH)}{r.randint(10, 9999)}"
        elif style == "lure":
            a, b = r.choice(words or BENIGN_LURE_WORDS), r.choice(TECH + GENERIC)
            if a == b:
                b = r.choice(GENERIC)
            base = r.choice([f"{a}-{b}", a + b, f"{b}-{a}", f"{a}-{b}{r.randint(1, 9)}"])
        elif style == "gibberish":
            base = "".join(r.choices(ALNUM, k=r.randint(6, 12)))
        else:
            raise ValueError(f"unknown naming style {style!r}")
        return f"{base}.{self.wchoice(tlds or BENIGN_TLDS)}"

    def unique_name(self, style, words=None, tlds=None) -> str:
        for _ in range(1000):
            d = self.name(style, words, tlds)
            if d not in self.regs:
                return d
        raise RuntimeError("could not find a unique domain name")

    # ------------------------------------------------------------ shared infrastructure

    def _build_shared_pools(self):
        self.cdn_v4 = {asn: [self.new_v4(asn, "cdn") for _ in range(12)] for asn in KIND_ASNS["cdn"]}
        self.cdn_v6 = {asn: [self.new_v6(asn, "cdn") for _ in range(6)] for asn in KIND_ASNS["cdn"]}
        self.shared_v4 = {asn: [self.new_v4(asn, "shared_hosting") for _ in range(30)] for asn in KIND_ASNS["shared"]}
        self.parking = []
        for ns, n_ips in PARKING_PROVIDERS:
            for h in ns:
                self.host(h, "ns", 64500, "parking")
            self.parking.append((ns, [self.new_v4(64500, "parking") for _ in range(n_ips)]))
        self.sinkhole_ips = [self.new_v4(64501, "sinkhole") for _ in range(3)]
        for h in SINKHOLE_NS:
            self.host(h, "ns", 64501, "sinkhole")
        self.crime_ips = [self.new_v4(self.rng.choice(KIND_ASNS["vps"]), "dedicated") for _ in range(6)]

    def _build_resellers(self, n: int):
        """Small hosting companies on rented VPSes, each with its own name servers.
        Their NS hosts are shared by a handful to a few dozen domains, just like an actor's."""
        r = self.rng
        self.resellers = []
        self.reseller_weights = []
        for i in range(n):
            for _ in range(1000):
                base = r.choice([r.choice(GENERIC), "".join(r.choices(SYLLABLES, k=2))])
                d = f"{base}{r.choice(['', '-'])}{r.choice(['host', 'hosting', 'web', 'servers', 'cloud', 'net'])}.{self.wchoice({'com': 6, 'net': 3, 'io': 1})}"
                if d not in self.regs:
                    break
            asn = r.choice(KIND_ASNS["vps"])
            ips = [self.new_v4(asn, "shared_hosting") for _ in range(r.randint(1, 3))]
            ns = [self.host(f"ns{k}.{d}", "ns", asn, "hosting_ns") for k in (1, 2)]
            registrar = self.wchoice(BENIGN_REGISTRARS)
            reg = WORLD_START - timedelta(days=r.randint(200, 4000))
            self.add_domain(d, registrar, reg, "benign", True)
            self.seg(d, "A", ips[0], WORLD_START, WORLD_END)
            for h in ns:
                self.seg(d, "NS", h, WORLD_START, WORLD_END)
            self.resellers.append({"domain": d, "asn": asn, "ips": ips, "ns": ns})
            self.reseller_weights.append(1 / (i + 1) ** 0.8)

    def registrar_ns(self, registrar: str) -> list[str]:
        r = self.rng
        if registrar == "GoDaddy.com, LLC":
            n = r.randint(1, 40) * 2 - 1
            hosts = [f"ns{n:02d}.domaincontrol.com", f"ns{n + 1:02d}.domaincontrol.com"]
        elif registrar == "NameCheap, Inc.":
            hosts = ["dns1.registrar-servers.com", "dns2.registrar-servers.com"]
        elif registrar == "Tucows Domains Inc.":
            hosts = ["ns1.hover.com", "ns2.hover.com"]
        elif registrar == "Porkbun LLC":
            hosts = [f"{c}.porkbun.com" for c in r.sample(["curitiba", "maceio", "salvador", "fortaleza"], 2)]
        elif registrar == "Squarespace Domains LLC":
            x = r.choice("abcde")
            hosts = [f"ns-cloud-{x}1.googledomains.com", f"ns-cloud-{x}2.googledomains.com"]
        elif registrar == "Cloudflare, Inc.":
            return self.cloudflare_ns()
        elif registrar == "Hostinger Operations, UAB":
            hosts = ["ns1.dns-parking.com", "ns2.dns-parking.com"]  # real-world confounder: not parking!
        elif registrar == "NameSilo, LLC":
            hosts = ["ns1.dnsowl.com", "ns2.dnsowl.com"]
        elif registrar == "Gandi SAS":
            n = r.randint(1, 120)
            hosts = [f"ns-{n}-a.gandi.net", f"ns-{n}-b.gandi.net"]
        elif registrar == "OVH sas":
            n = r.randint(10, 120)
            hosts = [f"dns{n}.ovh.net", f"ns{n}.ovh.net"]
        elif registrar == "Njalla":
            hosts = ["1-you.njalla.no", "2-can.njalla.in"]
        else:
            raise ValueError(f"unknown registrar {registrar!r}")
        asn = REGISTRARS[registrar][1]
        return [self.host(h, "ns", asn, "registrar_ns") for h in hosts]

    def cloudflare_ns(self) -> list[str]:
        return [self.host(f"{n}.ns.cloudflare.com", "ns", 13335, "dns_provider") for n in self.rng.sample(CF_NAMES, 2)]

    def aws_ns(self) -> list[str]:
        n, m = self.rng.randint(1, 2000), self.rng.randint(0, 63)
        return [self.host(f"ns-{n}.awsdns-{m:02d}.com", "ns", 16509, "dns_provider"),
                self.host(f"ns-{n + 512}.awsdns-{m:02d}.net", "ns", 16509, "dns_provider")]

    def cdn_ns(self, asn: int, registrar: str) -> list[str]:
        if asn == 13335:
            return self.cloudflare_ns()
        return self.aws_ns() if self.rng.random() < 0.4 else self.registrar_ns(registrar)

    def vanity_ns(self, main_domain: str, asn: int) -> list[str]:
        return [self.host(f"ns{k}.{main_domain}", "ns", asn, "self_hosted_ns") for k in (1, 2)]

    def pick_mx_provider(self, dedicated: bool) -> str:
        weights = {k: v[0] for k, v in MX_PROVIDERS.items() if dedicated or k != "self"}
        return self.wchoice(weights)

    def mx_hosts(self, provider: str, domain: str, ip_asn: int | None) -> list[str]:
        if provider == "self" and ip_asn is None:
            provider = "google"
        if provider == "google":
            return [self.host(h, "mx", 15169, "mail_provider") for h in ("aspmx.l.google.com", "alt1.aspmx.l.google.com")]
        if provider == "outlook":
            return [self.host(f"{domain.replace('.', '-')}.mail.protection.outlook.com", "mx", 8075, "mail_provider")]
        if provider == "privateemail":
            return [self.host(h, "mx", 22612, "mail_provider") for h in ("mx1.privateemail.com", "mx2.privateemail.com")]
        if provider == "zoho":
            return [self.host(h, "mx", 2639, "mail_provider") for h in ("mx.zoho.com", "mx2.zoho.com")]
        if provider == "hostinger":
            return [self.host(h, "mx", 47583, "mail_provider") for h in ("mx1.hostinger.com", "mx2.hostinger.com")]
        return [self.host(f"mail.{domain}", "mx", ip_asn, "self_hosted_mail")]

    # ------------------------------------------------------------ hosting plans and lifecycle

    def make_plan(self, kind: str, registrar: str, main_domain: str, vanity: bool = False, n_ips: int | None = None) -> dict:
        """How an owner hosts its sites. Owners reuse one plan across their domains."""
        r = self.rng
        plan = {"kind": kind, "reseller": None, "v4": None, "v6": None}
        if kind == "cdn":
            asn = r.choice(KIND_ASNS["cdn"])
            ns = self.cdn_ns(asn, registrar)
        elif kind == "shared":
            if r.random() < 0.35:
                res = r.choices(self.resellers, weights=self.reseller_weights)[0]
                plan["reseller"], asn, ns = res, res["asn"], res["ns"]
            else:
                asn = r.choice(KIND_ASNS["shared"])
                ns = self.registrar_ns(registrar)
        else:  # cloud / vps: dedicated server(s), possibly shared by several of the owner's sites
            asn = r.choice(KIND_ASNS[kind])
            n = n_ips or (1 if r.random() < 0.8 else r.randint(2, 3))
            plan["v4"] = [self.new_v4(asn, "dedicated") for _ in range(n)]
            if r.random() < (0.3 if kind == "cloud" else 0.2):
                plan["v6"] = [self.new_v6(asn, "dedicated")]
            if vanity:
                ns = self.vanity_ns(main_domain, asn)
            elif asn == 16509 and r.random() < 0.6:
                ns = self.aws_ns()
            elif r.random() < 0.35:
                ns = self.cloudflare_ns()
            else:
                ns = self.registrar_ns(registrar)
        plan["asn"], plan["ns"] = asn, ns
        plan["mx"] = self.pick_mx_provider(kind in ("cloud", "vps")) if r.random() < 0.55 else None
        return plan

    def apply_plan(self, domain: str, plan: dict, s: date, e: date):
        r = self.rng
        kind, asn = plan["kind"], plan["asn"]
        if kind == "cdn":  # CDNs rotate the edge IPs they hand out every few months
            v6 = r.random() < 0.6
            a = s
            while a <= e:
                b = min(e, a + timedelta(days=r.randint(90, 400)))
                for ip in r.sample(self.cdn_v4[asn], 2):
                    self.seg(domain, "A", ip, a, b)
                if v6:
                    for ip in r.sample(self.cdn_v6[asn], 2):
                        self.seg(domain, "AAAA", ip, a, b)
                a = b + timedelta(days=1)
        elif kind == "shared":
            pool = plan["reseller"]["ips"] if plan["reseller"] else self.shared_v4[asn]
            self.seg(domain, "A", r.choice(pool), s, e)
        else:
            self.seg(domain, "A", r.choice(plan["v4"]), s, e)
            if plan["v6"]:
                self.seg(domain, "AAAA", r.choice(plan["v6"]), s, e)
        for h in plan["ns"]:
            self.seg(domain, "NS", h, s, e)
        if plan["mx"]:
            for h in self.mx_hosts(plan["mx"], domain, asn if kind in ("cloud", "vps") else None):
                self.seg(domain, "MX", h, s, e)

    def park(self, domain, start, end, provider=None):
        ns, ips = provider or self.rng.choice(self.parking)
        self.seg(domain, "A", self.rng.choice(ips), start, end, True)
        for h in ns:
            self.seg(domain, "NS", h, start, end, True)

    def pre_launch(self, domain, registrar, start, end, park_prob):
        """Registered but not live yet: a parking page, or just the registrar's name servers."""
        if start > end:
            return
        if self.rng.random() < park_prob:
            self.park(domain, start, end)
        else:
            for h in self.registrar_ns(registrar):
                self.seg(domain, "NS", h, start, end, True)

    def sinkhole(self, domain, start, end):
        self.seg(domain, "A", self.rng.choice(self.sinkhole_ips), start, end, True)
        for h in SINKHOLE_NS:
            self.seg(domain, "NS", h, start, end, True)

    def lapse(self, domain, registrar, after: date):
        """Site taken down. The registration runs to its next anniversary and then expires;
        some expired domains get drop-caught and parked by a domain investor."""
        r = self.rng
        reg = self.regs[domain][-1]["registered"]
        years = max(1, (after - reg).days // 365 + 1)
        exp = reg + timedelta(days=365 * years)
        for h in self.registrar_ns(registrar):
            self.seg(domain, "NS", h, after, min(exp, WORLD_END), True)
        if exp > WORLD_END:
            return
        self.regs[domain][-1]["expired"] = exp
        if r.random() < 0.3:
            rereg = exp + timedelta(days=r.randint(5, 60))
            if rereg < WORLD_END - timedelta(days=5):
                self.regs[domain].append({"registrar": self.wchoice(BENIGN_REGISTRARS), "registered": rereg, "expired": None})
                self.park(domain, rereg + timedelta(days=1), WORLD_END)

    def launch_delay(self) -> int:
        x = self.rng.random()
        if x < 0.55:
            return self.rng.randint(0, 20)
        if x < 0.80:
            return self.rng.randint(20, 150)
        return self.rng.randint(150, 600)  # registered early, launched much later

    # ------------------------------------------------------------ populations

    def gen_benign(self, n: int):
        r = self.rng
        made = 0
        while made < n:
            otype = self.wchoice({k: v[0] for k, v in OWNER_TYPES.items()})
            _, (lo, hi), spread, kinds, popular_p, short_p = OWNER_TYPES[otype]
            size = min(r.randint(lo, hi), n - made)
            registrar = self.wchoice(BENIGN_REGISTRARS)
            base = self.rand_date(WORLD_START - timedelta(days=3000), WORLD_END - timedelta(days=30))
            bursts = [self.rand_date(WORLD_START - timedelta(days=1500), WORLD_END - timedelta(days=30))
                      for _ in range(r.randint(1, 3))]
            domains = []
            for i in range(size):
                style = "business" if otype == "business" and i == 0 and r.random() < 0.6 else self.wchoice(BENIGN_STYLES)
                d = self.unique_name(style)
                if otype == "investor":
                    reg = r.choice(bursts) + timedelta(days=r.randint(0, 10))
                else:
                    reg = base + timedelta(days=r.randint(0, spread))
                reg = min(reg, WORLD_END - timedelta(days=20))
                d_registrar = registrar if r.random() < 0.9 else self.wchoice(BENIGN_REGISTRARS)
                self.add_domain(d, d_registrar, reg, "benign", r.random() < popular_p)
                domains.append((d, reg, d_registrar))
            made += size

            if otype == "investor":  # a portfolio parked with one parking provider
                provider = r.choice(self.parking)
                for d, reg, _ in domains:
                    self.park(d, reg + timedelta(days=r.randint(0, 5)), WORLD_END, provider)
                continue

            main = domains[0][0]
            kind = self.wchoice(kinds)
            vanity = kind in ("cloud", "vps") and r.random() < {"agency": 0.6, "business": 0.15}.get(otype, 0.03)
            plan = self.make_plan(kind, registrar, main, vanity, n_ips=r.randint(1, 3) if otype == "agency" else None)
            for d, reg, d_registrar in domains:
                live = reg + timedelta(days=self.launch_delay())
                self.pre_launch(d, d_registrar, reg + timedelta(days=1), live - timedelta(days=1),
                                0.5 if (live - reg).days > 20 else 0.1)
                if live > WORLD_END:
                    continue
                p = plan if r.random() < 0.85 else self.make_plan(self.wchoice(kinds), d_registrar, d)
                if r.random() < short_p:  # abandoned project
                    end = live + timedelta(days=int(r.lognormvariate(4.6, 0.8)) + 10)  # median ~110 days
                    self.apply_plan(d, p, live, min(end, WORLD_END))
                    if end < WORLD_END:
                        self.lapse(d, d_registrar, end + timedelta(days=1))
                elif r.random() < 0.35:  # moved hosting once
                    cut = self.rand_date(live, WORLD_END)
                    self.apply_plan(d, p, live, cut)
                    self.apply_plan(d, self.make_plan(self.wchoice(kinds), d_registrar, d), cut + timedelta(days=1), WORLD_END)
                else:
                    self.apply_plan(d, p, live, WORLD_END)

    def gen_crimeware(self, n: int):
        r = self.rng
        for _ in range(n):
            d = self.unique_name("gibberish" if r.random() < 0.5 else "tech", tlds=CRIME_TLDS)
            registrar = r.choice(["NameSilo, LLC", "NameCheap, Inc.", "Porkbun LLC"])
            reg = self.rand_date(WORLD_START, WORLD_END - timedelta(days=40))
            self.add_domain(d, registrar, reg, "crimeware", True)
            s = reg + timedelta(days=r.randint(0, 3))
            e = s + timedelta(days=r.randint(2, 20))
            ip = r.choice(self.crime_ips) if r.random() < 0.5 else self.new_v4(r.choice(KIND_ASNS["vps"]), "dedicated")
            self.seg(d, "A", ip, s, e)
            for h in self.registrar_ns(registrar):
                self.seg(d, "NS", h, s, e)
            if r.random() < 0.6:
                self.sinkhole(d, e + timedelta(days=1), WORLD_END)
            else:
                self.lapse(d, registrar, e + timedelta(days=1))

    def gen_actor(self, cfg: dict) -> dict:
        r = self.rng
        name = cfg["name"]
        label = f"actor:{name}"
        hosting_asns = {int(k): v for k, v in cfg["hosting_asns"].items()}
        for asn in hosting_asns:
            if asn not in ASNS:
                raise ValueError(f"{name}: unknown ASN {asn}; add it to ASNS in sim/simulate.py")
        for reg_name in cfg["registrars"]:
            if reg_name not in REGISTRARS:
                raise ValueError(f"{name}: unknown registrar {reg_name!r}; add it to REGISTRARS in sim/simulate.py")
        main_asn = max(hosting_asns, key=hosting_asns.get)
        windows = [(ld.to_date(w["start"]), ld.to_date(w["end"])) for w in cfg["campaign_windows"]]
        naming = cfg["naming"]
        pool_v4: list[str] = []
        pool_v6: list[str] = []
        truth = {"domains": [], "ips": set(), "ns_hosts": [], "mx_hosts": [], "cdn_fronted_domains": []}

        def actor_ip(pool, new_fn):
            if pool and r.random() < cfg["ip_reuse_rate"]:
                return r.choice(pool)
            ip = new_fn(self.wchoice(hosting_asns), "actor")
            pool.append(ip)
            truth["ips"].add(ip)
            return ip

        # Domains behind the actor's own NS/MX hosts (e.g. dnssvc-cloud.net), set up before the campaigns.
        ns_hosts = [self.host(h, "ns", main_asn, "actor") for h in cfg["custom_ns"]["hosts"]]
        mx_hosts = [self.host(h, "mx", main_asn, "actor") for h in cfg["custom_mx"]["hosts"]]
        truth["ns_hosts"], truth["mx_hosts"] = ns_hosts, mx_hosts
        for d in sorted({h.split(".", 1)[1] for h in ns_hosts + mx_hosts}):
            registrar = self.wchoice(cfg["registrars"])
            reg = windows[0][0] - timedelta(days=r.randint(20, 60))
            self.add_domain(d, registrar, reg, label, False)
            truth["domains"].append(d)
            self.seg(d, "A", actor_ip(pool_v4, self.new_v4), reg + timedelta(days=2), WORLD_END)
            for h in self.registrar_ns(registrar):
                self.seg(d, "NS", h, reg + timedelta(days=2), WORLD_END)

        for _ in range(cfg["n_domains"]):
            d = self.unique_name(self.wchoice(naming["styles"]), naming.get("words"), naming["tlds"])
            registrar = self.wchoice(cfg["registrars"])
            reg = self.rand_date(*r.choice(windows))
            self.add_domain(d, registrar, reg, label, False)
            truth["domains"].append(d)
            aging = max(1, int(r.gauss(cfg["aging_days"]["mean"], cfg["aging_days"]["std"])))
            active = max(5, int(r.gauss(cfg["active_days"]["mean"], cfg["active_days"]["std"])))
            op_start = reg + timedelta(days=aging)
            op_end = op_start + timedelta(days=active)

            self.pre_launch(d, registrar, reg + timedelta(days=1), op_start - timedelta(days=1), cfg["park_first_rate"])

            if r.random() < cfg["cdn_fronting_rate"]:
                truth["cdn_fronted_domains"].append(d)
                asn = r.choice(KIND_ASNS["cdn"])
                ip_asn = None
                for ip in r.sample(self.cdn_v4[asn], 2):
                    self.seg(d, "A", ip, op_start, op_end)
                ns = self.cdn_ns(asn, registrar)
            else:
                ip = actor_ip(pool_v4, self.new_v4)
                ip_asn = self.meta[ip]["asn"]
                self.seg(d, "A", ip, op_start, op_end)
                if r.random() < cfg["ipv6_rate"]:
                    self.seg(d, "AAAA", actor_ip(pool_v6, self.new_v6), op_start, op_end)
                ns = ns_hosts if (ns_hosts and r.random() < cfg["custom_ns"]["rate"]) else (
                    self.cloudflare_ns() if r.random() < 0.3 else self.registrar_ns(registrar))
            for h in ns:
                self.seg(d, "NS", h, op_start, op_end)
            if mx_hosts and r.random() < cfg["custom_mx"]["rate"]:
                mx = mx_hosts
            elif r.random() < 0.3:
                mx = self.mx_hosts(self.pick_mx_provider(ip_asn is not None), d, ip_asn)
            else:
                mx = []
            for h in mx:
                self.seg(d, "MX", h, op_start, op_end)

            end = self.wchoice(cfg["end_state"])
            after = op_end + timedelta(days=1)
            if end == "sinkhole":
                gap = after + timedelta(days=r.randint(0, 30))
                self.sinkhole(d, gap, WORLD_END)
            elif end == "parking":
                park_end = after + timedelta(days=r.randint(60, 300))
                self.park(d, after, park_end)
                self.lapse(d, registrar, park_end + timedelta(days=1))
            else:
                self.lapse(d, registrar, after)

        truth["ips"] = sorted(truth["ips"])
        truth["domains"].sort()
        truth["cdn_fronted_domains"].sort()
        return truth

    # ------------------------------------------------------------ sensors

    def observe(self) -> list[dict]:
        """Turn true segments into passive and forward sensor observations.
        Same rules for every domain; only popularity (real user traffic) differs."""
        r = self.rng
        forward_cov: dict[str, bool] = {}
        passive_cov: dict[str, bool] = {}
        out: dict[tuple, list[list[date]]] = defaultdict(list)
        for domain, rrtype, value, start, end, quiet in self.segments:
            popular = self.popular.get(domain, False)
            if domain not in forward_cov:
                forward_cov[domain] = r.random() < 0.9
                passive_cov[domain] = r.random() < (0.98 if popular else 0.7)
            s, e = max(start, WORLD_START), min(end, WORLD_END)
            if forward_cov[domain]:  # periodic active scan: sees it within a few days
                fs, fe = s + timedelta(days=r.randint(0, 2)), e - timedelta(days=r.randint(0, 2))
                if fs <= fe:
                    out[(domain, rrtype, value, "forward")].append([fs, fe])
            if passive_cov[domain] and (not quiet or r.random() < 0.1):
                delay = r.randint(0, 2) if popular else r.randint(0, 30)
                ps, pe = s + timedelta(days=delay), e - timedelta(days=r.randint(0, 3))
                if ps <= pe:
                    out[(domain, rrtype, value, "passive")].append([ps, pe])

        records = []
        for (domain, rrtype, value, source), ranges in out.items():
            ranges.sort()
            merged = [ranges[0]]
            for a, b in ranges[1:]:
                if a <= merged[-1][1] + timedelta(days=1):
                    merged[-1][1] = max(merged[-1][1], b)
                else:
                    merged.append([a, b])
            for a, b in merged:
                records.append({"domain": domain, "rrtype": rrtype, "value": value,
                                "first_seen": a.isoformat(), "last_seen": b.isoformat(), "source": source})
        records.sort(key=lambda x: (x["domain"], x["rrtype"], x["first_seen"], x["value"], x["source"]))
        return records


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=6262)
    ap.add_argument("--benign", type=int, default=5000, help="number of benign domains (plus ~40 reseller domains)")
    ap.add_argument("--crimeware", type=int, default=40, help="number of non-APT malicious domains")
    ap.add_argument("--actors", default=str(SIM_DIR / "actors"), help="folder of actor configs")
    ap.add_argument("--public-out", default=str(ld.DATA_DIR / "seed-data_no-ground-truth"),
                    help="output folder without ground truth (for filter/pivot development)")
    ap.add_argument("--out", default=str(ld.DATA_DIR / "seed-data_with-ground-truth"),
                    help="output folder with ground truth and actor profiles (for evaluation); pass '' to skip")
    args = ap.parse_args()

    world = World(args.seed)
    world.gen_benign(args.benign)
    world.gen_crimeware(args.crimeware)
    actor_files = sorted(Path(args.actors).glob("*.json"))
    actors = {}
    for p in actor_files:
        cfg = ld.read_json(p)
        actors[cfg["name"]] = world.gen_actor(cfg)
    records = world.observe()

    domain_sets = defaultdict(set)
    for rec in records:
        domain_sets[rec["value"]].add(rec["domain"])
    infra = {v: {**world.meta[v], "domain_count": len(ds), "label": "unknown"} for v, ds in sorted(domain_sets.items())}
    seen_domains = {rec["domain"] for rec in records}
    domains = {}
    for d in sorted(world.regs):
        regs = [{"registrar": x["registrar"], "registered": x["registered"].isoformat(),
                 "expired": x["expired"].isoformat() if x["expired"] else None} for x in world.regs[d]]
        domains[d] = {"registrar": regs[-1]["registrar"], "registered": regs[-1]["registered"], "registrations": regs}

    counts = {
        "resolutions": len(records),
        "resolutions_passive": sum(r["source"] == "passive" for r in records),
        "resolutions_forward": sum(r["source"] == "forward" for r in records),
        "domains": len(domains),
        "domains_with_records": len(seen_domains),
        "infra": len(infra),
    }
    manifest = {
        "format_version": ld.FORMAT_VERSION,
        "seed": args.seed,
        "world_start": WORLD_START.isoformat(),
        "world_end": WORLD_END.isoformat(),
        "params": {"benign": args.benign, "crimeware": args.crimeware, "n_actor_configs": len(actor_files)},
        "counts": counts,
    }

    # Development copy: observations and metadata only. No answer key, no actor profiles.
    public = Path(args.public_out)
    ld.write_jsonl(public / "resolutions.jsonl", records)
    ld.write_json(public / "infra.json", infra)
    ld.write_json(public / "domains.json", domains)
    ld.write_json(public / "manifest.json", manifest)
    print(f"wrote {public} (no ground truth): {counts}")

    # Evaluation copy: the same files plus ground_truth.json and the actor profiles used.
    if args.out:
        out = Path(args.out)
        ld.write_jsonl(out / "resolutions.jsonl", records)
        ld.write_json(out / "infra.json", infra)
        ld.write_json(out / "domains.json", domains)
        ld.write_json(out / "manifest.json", manifest)
        ld.write_json(out / "ground_truth.json", {
            "actors": actors,
            "domain_labels": {d: world.domain_labels[d] for d in sorted(world.domain_labels)},
            "infra_labels": {v: world.truth[v] for v in sorted(infra)},
        })
        (out / "actors").mkdir(parents=True, exist_ok=True)
        for p in actor_files:
            (out / "actors" / p.name).write_bytes(p.read_bytes())
        print(f"wrote {out} (with ground truth and actor profiles)")


if __name__ == "__main__":
    main()
