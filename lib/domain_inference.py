"""Shared domain inference + per-row gate detection.

Used by BOTH:
  - applications/scripts/refresh_lib/jobspy_ingest.py (Phase 4 refresh skill)
  - scripts/triage_jobspy_csv.py (canonical user-facing triage / ingest-search-results skill)

The two pipelines must agree on tier inference and gate flags so they don't drift.
Earlier these regexes lived inline inside jobspy_ingest.py; this module is the
single source of truth post-merge (2026-05-16).

Public API:
    DOMAIN_TIER_HINT: dict[str, int]
        Maps domain key (e.g. "saas", "insurance") to a tier estimate.
    DOMAIN_INFERENCE_RULES: list[tuple[str, re.Pattern]]
        Ordered list of (domain_key, regex) pairs. Higher-priority (hard-block)
        tiers come first so they win over softer matches.
    infer_domain_from_text(*texts: str) -> Optional[str]
        Scan title + description + company for domain keywords, return first match.
    estimate_tier_from_domain(domain: str) -> Optional[int]
        Look up tier estimate. Returns None if domain is empty/unknown.
    RE_LEVEL_MISMATCH, RE_CONTRACT_ROLE, RE_NON_US, RE_MANUFACTURING:
        Compiled regexes for per-row gate detection.
    detect_gates(title: str, description: str, location: str = "", stack_hits: int = 0) -> dict
        One-shot row-gate detector returning a dict with bool flags + a notes list.

Adding a new domain rule:
  1. Pick the tier from DOMAIN_TIER_HINT (or add a new key + tier).
  2. Insert a (domain_key, compiled_regex) tuple into DOMAIN_INFERENCE_RULES
     in PRIORITY ORDER (hard-block tiers first, neutral last).
  3. Add a failing fixture to scripts/test_triage_<date>_regressions.py and
     re-run scripts/run_all_tests.sh per the standard rule-addition loop
     documented in ingest-search-results/SKILL.md Step 2c.
"""

from __future__ import annotations

import re
from typing import Optional


# Rough domain → C5 tier mapping. Conservative; not authoritative.
# This is heuristic only — actual C5 tier requires per-company research per c5 framework.
DOMAIN_TIER_HINT: dict[str, int] = {
    # Likely tier 1-3 (movement-adjacent / non-profit / co-op)
    "education": 3,
    "civic": 3,
    "climate": 3,
    "nonprofit": 2,
    # Likely tier 4-5 (generally-good-for-society)
    "healthtech": 5,
    "healthcare": 5,
    "fintech": 5,
    "developer-tools": 5,
    "devops": 5,
    "security": 5,
    "qa-tooling": 5,
    "ai-tooling": 5,
    "ai-eval": 5,
    "observability": 5,
    "data-platform": 5,
    # Likely tier 6-7 (neutral for-profit)
    "saas": 7,
    "b2b": 7,
    "ecommerce": 7,
    "marketing": 7,
    "media": 7,
    "logistics": 7,
    # Likely tier 8 (mildly evil + lobbying)
    "adtech": 8,
    "ad-tech": 8,
    "insurance": 8,
    "real-estate": 8,
    # Likely tier 9-10 (hard-block)
    "gambling": 9,
    "sportsbook": 9,
    "surveillance": 9,
    "weapons": 10,
    "defense": 10,  # depends on subtype; conservative
}


# Domain inference rules: regex patterns scanned against title + description + company
# to assign a DOMAIN_TIER_HINT key when CSV `domain` column is `?` / empty.
# Order matters: more-specific patterns first (gambling before saas; surveillance before media).
DOMAIN_INFERENCE_RULES: list[tuple[str, "re.Pattern[str]"]] = [
    # Hard-block tiers (T9-T10) — scan FIRST so they win over softer matches
    ("gambling", re.compile(r"\b(gambling|sportsbook|sports\s+betting|casino|wager|fanduel|draftkings|betmgm)\b", re.IGNORECASE)),
    ("surveillance", re.compile(r"\b(surveillance|session\s+replay|behavioral\s+tracking|user\s+monitoring|fullstory|hotjar|clarity\s+session)\b", re.IGNORECASE)),
    ("weapons", re.compile(r"\b(weapons?\s+systems?|munitions|missile|firearms?\s+manufacturer)\b", re.IGNORECASE)),
    ("defense", re.compile(r"\b(defense\s+contractor|dod\s+contract|lockheed|raytheon|anduril|palantir\s+defense|northrop)\b", re.IGNORECASE)),
    # T8 — mildly evil + lobbying
    ("adtech", re.compile(r"\b(ad[- ]?tech|programmatic\s+advertising|demand[- ]side\s+platform|dsp|ssp|ad\s+exchange|ad\s+server|behavioral\s+ad)\b", re.IGNORECASE)),
    ("insurance", re.compile(r"\b(insurance\s+(?:carrier|company|broker|underwrit)|p&c\s+insurance|claims\s+management|guidewire|duck\s+creek|origami\s+risk)\b", re.IGNORECASE)),
    ("real-estate", re.compile(r"\b(real\s+estate\s+(?:tech|platform|brokerage)|mortgage\s+(?:tech|platform)|proptech|zillow|redfin|opendoor)\b", re.IGNORECASE)),
    # T5 — generally good
    # NB: healthtech requires the JD to be ABOUT health-tech, not just mention "patient" once.
    # Tightened 2026-05-16 after ServiceTitan (home-services SaaS) was misclassified.
    ("healthtech", re.compile(
        r"\b(healthcare?\s+(?:saas|platform|tech)\s+(?:company|vendor)|"
        r"(?:we\s+are|we\s+build|our\s+(?:company|product))\s+(?:a|the)\s+(?:healthcare|healthtech|ehr|emr)|"
        r"electronic\s+health\s+record|ehr\s+(?:platform|vendor)|emr\s+(?:platform|vendor)|telehealth\s+(?:platform|company)|"
        r"patient\s+(?:portal|engagement\s+platform|management\s+platform)|"
        r"clinical\s+(?:trial\s+platform|workflow\s+platform|decision\s+support))\b",
        re.IGNORECASE,
    )),
    ("healthcare", re.compile(r"\b(healthcare\s+(?:company|provider|organization)|patient\s+care\s+(?:platform|company)|hospital\s+system|medical\s+device\s+(?:company|manufacturer)|life\s+sciences\s+company|biotech\s+company|pharmaceutical\s+(?:company|manufacturer))\b", re.IGNORECASE)),
    ("fintech", re.compile(r"\b(fintech|financial\s+technology|banking\s+platform|payment\s+(?:processing|gateway)|lending\s+platform|wealth\s+management\s+platform|robo[- ]advisor|crypto(?:currency)?|defi)\b", re.IGNORECASE)),
    # developer-tools: require explicit vendor framing, not just CI/CD tool mentions.
    # "GitHub Actions" / "GitHub Copilot" in a JD = stack reference, NOT that the company IS GitHub.
    ("developer-tools", re.compile(
        r"\b(developer\s+(?:tools|platform|productivity)\s+(?:company|vendor|startup|saas)|"
        r"(?:we|our\s+company)\s+(?:build|are|operate)\s+(?:a|the)\s+developer\s+(?:tool|platform|product)|"
        r"ide\s+(?:vendor|product|company)|"
        r"code\s+(?:hosting|review|search)\s+platform|"
        r"codesandbox|cursor\s+ai|replit\s+inc)\b",
        re.IGNORECASE,
    )),
    # devops/security/observability/data-platform vendor rules require explicit "we are a ..." framing,
    # NOT just CI/CD tool mentions. Wei's stack JDs constantly mention jenkins/datadog/snowflake as
    # tools to USE — the company itself isn't a vendor in that category.
    ("devops", re.compile(
        r"\b(devops\s+(?:platform|vendor|company|saas|tooling\s+vendor)|"
        r"sre\s+platform|reliability\s+engineering\s+platform|"
        r"ci[/-]cd\s+platform\s+(?:company|vendor|provider))\b",
        re.IGNORECASE,
    )),
    ("security", re.compile(
        r"\b(cybersecurity\s+(?:company|firm|vendor|saas|platform)|"
        r"(?:we\s+are\s+a|is\s+a)\s+security\s+(?:company|platform|vendor)|"
        r"appsec\s+platform|threat\s+detection\s+platform|"
        r"vulnerability\s+management\s+platform|siem\s+vendor|edr\s+vendor)\b",
        re.IGNORECASE,
    )),
    ("qa-tooling", re.compile(
        r"\b(qa\s+(?:platform|tooling)\s+(?:company|vendor|saas)|"
        r"test\s+(?:management|automation)\s+platform\s+(?:vendor|company)|"
        r"(?:we\s+are|we\s+build)\s+(?:a|the)\s+(?:qa|test\s+automation)\s+platform)\b",
        re.IGNORECASE,
    )),
    ("ai-tooling", re.compile(
        r"\b(ai\s+(?:infrastructure|engineering)\s+platform|"
        r"mlops\s+platform|"
        r"llm\s+(?:platform|infrastructure)\s+(?:company|vendor)|"
        r"model\s+(?:serving|deployment)\s+platform\s+(?:vendor|company)|"
        r"(?:we\s+are|we\s+build)\s+(?:a|the)\s+(?:ai|ml|llm)\s+(?:platform|infrastructure))\b",
        re.IGNORECASE,
    )),
    ("ai-eval", re.compile(
        r"\b(ai\s+(?:evaluation|safety\s+eval|red[- ]?teaming)\s+(?:platform|company|vendor)|"
        r"llm\s+eval(?:uation)?\s+(?:platform|company)|"
        r"model\s+evaluation\s+(?:platform|saas|company)|"
        r"braintrust\s+data|patronus\s+ai)\b",
        re.IGNORECASE,
    )),
    ("observability", re.compile(
        r"\b(observability\s+(?:platform|company|vendor|saas)|"
        r"(?:we\s+are|we\s+build)\s+(?:a|the)\s+(?:observability|apm|tracing)\s+platform|"
        r"distributed\s+tracing\s+(?:platform|vendor))\b",
        re.IGNORECASE,
    )),
    ("data-platform", re.compile(
        r"\b(data\s+(?:platform|warehouse|lakehouse)\s+(?:company|vendor|saas)|"
        r"(?:we\s+are|we\s+build)\s+(?:a|the)\s+data\s+(?:platform|warehouse|lakehouse)|"
        r"data\s+infrastructure\s+(?:company|vendor))\b",
        re.IGNORECASE,
    )),
    # T1-T3 — movement-adjacent / nonprofit / climate
    ("nonprofit", re.compile(r"\b(non[- ]?profit|501c3|charity|foundation\s+(?:grant|funded)|mission[- ]driven\s+nonprofit|public\s+benefit\s+corp)\b", re.IGNORECASE)),
    ("climate", re.compile(r"\b(climate\s+(?:tech|change\s+mitigation)|renewable\s+energy|solar\s+(?:platform|installation)|wind\s+power|carbon\s+(?:credit|offset|capture)|grid[- ]?services|vpp|virtual\s+power\s+plant)\b", re.IGNORECASE)),
    ("education", re.compile(r"\b(edtech|education\s+technology|k[- ]?12\s+software|higher\s+education\s+platform|learning\s+management\s+system|lms|tutoring\s+platform|curriculum)\b", re.IGNORECASE)),
    ("civic", re.compile(r"\b(civic\s+tech|gov[- ]?tech|government\s+technology|public[- ]sector\s+software|elections\s+technology|voter\s+platform)\b", re.IGNORECASE)),
    # T6-T7 — neutral for-profit (broad bucket; last because least specific)
    ("ecommerce", re.compile(r"\b(e[- ]?commerce|online\s+retail|shopify\s+merchant|marketplace\s+(?:platform|builder))\b", re.IGNORECASE)),
    ("logistics", re.compile(r"\b(logistics|supply\s+chain|warehouse\s+management|wms|fleet\s+management|freight|shipping\s+software)\b", re.IGNORECASE)),
    ("marketing", re.compile(r"\b(marketing\s+(?:platform|automation|tech|cloud)|email\s+marketing|crm\s+(?:platform|vendor)|martech|customer\s+engagement\s+platform)\b", re.IGNORECASE)),
    ("media", re.compile(r"\b(media\s+(?:company|conglomerate)|broadcaster|streaming\s+service|entertainment\s+(?:company|conglomerate)|news\s+organization|publisher)\b", re.IGNORECASE)),
    ("saas", re.compile(r"\b(saas|software[- ]as[- ]a[- ]service|b2b\s+platform|enterprise\s+software)\b", re.IGNORECASE)),
    ("b2b", re.compile(r"\b(b2b\s+(?:tech|software|platform)|business[- ]to[- ]business)\b", re.IGNORECASE)),
]


# Role-mismatch / level-mismatch / contract / geography detection regexes.
# Shared by both pipelines for consistent gate flagging.
RE_LEVEL_MISMATCH = re.compile(
    r"\b(junior|jr\.?|entry[-\s]?level|associate|intern(?:ship)?|coop)\b",
    re.IGNORECASE,
)
RE_CONTRACT_ROLE = re.compile(
    # Handles both raw "6+ Months Contract" and JobSpy-escaped "6\+ Months Contract"
    r"\b(\d+\\?\+?\s*month[s]?\s*contract|contract\s+to\s+hire|c2h|1099|temp(?:orary)?\s+contract|short[\s-]term\s+contract|month[s]?\s+contract|freelance\s+project)\b",
    re.IGNORECASE,
)
RE_NON_US = re.compile(
    r"\b(canada|portugal|germany|uk|united\s+kingdom|ireland|netherlands|india|"
    r"singapore|australia|brazil|mexico|argentina|spain|france|italy|israel|"
    r"poland|romania|ukraine|philippines)\b",
    re.IGNORECASE,
)
RE_MANUFACTURING = re.compile(
    r"\b(manufacturing|hardware\s+test|production\s+test\s+engineer|silicon\s+validation)\b",
    re.IGNORECASE,
)


def infer_domain_from_text(*texts: str) -> Optional[str]:
    """Scan title + description + company name for domain keywords.

    Returns first matching DOMAIN_TIER_HINT key, or None if no match.
    Order is priority-aware: hard-block tiers (gambling, surveillance) scanned first
    so they win over softer matches (media, saas).
    """
    combined = " ".join(t or "" for t in texts)
    if not combined.strip():
        return None
    for key, pattern in DOMAIN_INFERENCE_RULES:
        if pattern.search(combined):
            return key
    return None


def estimate_tier_from_domain(domain: str) -> Optional[int]:
    """Map domain hint to tier estimate. Returns None if unknown."""
    d = (domain or "").lower().strip()
    if d in ("?", "", "unknown"):
        return None
    # Direct lookup
    if d in DOMAIN_TIER_HINT:
        return DOMAIN_TIER_HINT[d]
    # Substring match (catches e.g. "media-streaming" → "media")
    for key, tier in DOMAIN_TIER_HINT.items():
        if key in d:
            return tier
    return None


def detect_gates(
    title: str,
    description: str,
    location: str = "",
    stack_hits: int = 0,
) -> dict:
    """One-shot row-gate detector. Returns dict with bool flags + a notes list.

    Returned dict keys:
        level_mismatch: bool — title contains junior/entry/intern markers
        contract_role: bool — description matches contract / C2H / freelance patterns
        zero_stack_hits: bool — stack_hits == 0
        manufacturing_stack: bool — low stack hits AND manufacturing/hardware-test framing
        non_us_location: bool — location or description mentions non-US country (and not "remote")
        notes: list[str] — human-readable per-gate reasons for the triage report

    Both pipelines (refresh-skill jobspy_ingest, user-facing triage_jobspy_csv)
    call this so gate semantics stay aligned.
    """
    notes: list[str] = []
    flags = {
        "level_mismatch": False,
        "contract_role": False,
        "zero_stack_hits": False,
        "manufacturing_stack": False,
        "non_us_location": False,
    }

    title_safe = title or ""
    desc_safe = (description or "")[:800]
    loc_safe = location or ""
    scan_text = f"{title_safe} {desc_safe}"

    if RE_LEVEL_MISMATCH.search(title_safe):
        flags["level_mismatch"] = True
        notes.append("LEVEL-MISMATCH: junior/entry-level role (Wei is 5yr+)")

    if RE_CONTRACT_ROLE.search(desc_safe):
        flags["contract_role"] = True
        notes.append("CONTRACT-FLAG: contract / C2H / freelance / non-FTE role")

    if stack_hits == 0:
        flags["zero_stack_hits"] = True
        notes.append("STACK-MISMATCH: zero JD-to-Wei stack hits")
    elif stack_hits <= 2 and RE_MANUFACTURING.search(scan_text):
        flags["manufacturing_stack"] = True
        notes.append("STACK-MISMATCH: manufacturing/hardware test ≠ Wei's stack")

    if RE_NON_US.search(loc_safe + " " + desc_safe[:300]) and "remote" not in loc_safe.lower():
        flags["non_us_location"] = True
        notes.append(f"NON-US: located {loc_safe or '[in description]'}")

    flags["notes"] = notes
    return flags
