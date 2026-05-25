#!/usr/bin/env python3
"""
Triage JobSpy CSV rows using the same filters as scripts/run_search.py (sisyphus).

Usage:
  python3 scripts/triage_jobspy_csv.py --latest --profile "$JOB_SEARCH_PROFILE"
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = Path(__file__).resolve().parent
import sys

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import argparse
import json
import logging
import os
import re

import pandas as pd


_JOBSPY_DIR = os.environ.get(
    'JOB_SEARCH_RESULTS_DIR',
    str(_REPO_ROOT / 'data' / 'jobspy_results'),
)
_ILS_OVERRIDES_PATH = str(_REPO_ROOT / 'config' / 'ils_overrides.json')
_REFERRAL_STATUS_PATH = str(_REPO_ROOT / 'config' / 'referral_status.txt')

# Referral-aware ILS floors (Patch 2026-05-15 #4).
#
# Rationale: in the AI-boom application volume era (2025+), cold-apply senior
# tech roles routinely see 1,500-5,000 applicants. ATS auto-filters + 3-10
# sec recruiter scans mean cold-apply odds collapsed faster than referral
# odds — referrals now bypass ~90% of the funnel (LinkedIn 2025 hiring data:
# ~45% of senior tech hires are referrals, up from 30% in 2022). The single
# ILS-floor model under-skipped wheelhouse-miss cold roles and over-skipped
# bridgeable referral-available roles. Tiered floors fix both directions.
#
# Default floor in `--ils-floor` (CLI default 45) is the COLD floor. The
# warm/strong tiers are RELATIVE to the cold floor — passing `--ils-floor 50`
# raises all three floors together.
_REFERRAL_WARM_DELTA = -10   # warm tier accepts ILS down to (cold - 10)
_REFERRAL_STRONG_DELTA = -20  # strong tier accepts ILS down to (cold - 20)


def _load_referral_status(path: str) -> dict[str, str]:
    """Load per-company referral status from a plain-text file.

    Format: one entry per line, ``company_substring,status`` where
    ``status`` is ``cold`` (default — no entry needed), ``warm`` (Wei has at
    least one LinkedIn connection at the company), or ``strong`` (Wei knows
    someone on the hiring team / has a likely HM intro path). Lines starting
    with ``#`` are comments; empty lines ignored. Company match is
    case-insensitive substring against the JobSpy ``company`` column.

    Missing file: empty dict (everyone is cold). Malformed lines logged and
    skipped rather than failing the run.
    """
    out: dict[str, str] = {}
    if not os.path.exists(path):
        return out
    try:
        with open(path, encoding='utf-8') as f:
            for lineno, line in enumerate(f, 1):
                s = line.strip()
                if not s or s.startswith('#'):
                    continue
                # Strip inline comments — common user mistake to write
                # `company,warm   # note` and have the parser treat the entire
                # tail (including the '#' and prose) as the status field.
                # Per the file format, comments are line-level only, but the
                # inline form is intuitive enough to support defensively.
                if '#' in s:
                    s = s.split('#', 1)[0].rstrip()
                    if not s:
                        continue
                if ',' not in s:
                    logging.warning('referral_status.txt:%d malformed (no comma): %r', lineno, s)
                    continue
                company, status = (p.strip() for p in s.split(',', 1))
                status_lc = status.lower()
                if status_lc not in {'cold', 'warm', 'strong'}:
                    logging.warning(
                        'referral_status.txt:%d invalid status %r (use cold/warm/strong)',
                        lineno, status,
                    )
                    continue
                if not company:
                    continue
                out[company.lower()] = status_lc
    except OSError as exc:
        logging.warning('referral_status.txt read failed: %s', exc)
    return out


_REFERRAL_STATUS: dict[str, str] = _load_referral_status(_REFERRAL_STATUS_PATH)
def _configure_from_profile(profile_path: str | None) -> None:
    """Apply profile paths and geo/ILS settings when --profile or env is set."""
    global _JOBSPY_DIR, _ILS_OVERRIDES_PATH, _REFERRAL_STATUS_PATH
    global _REFERRAL_STATUS, _ILS_OVERRIDES, _ATL_BLOB, _REMOTE_PREF

    path = profile_path or os.environ.get("JOB_SEARCH_PROFILE")
    if not path:
        return

    from lib.search_profile import (
        ils_floor,
        load_profile,
        referral_path,
        remote_policy,
        results_dir,
        allowed_hybrid_places,
    )

    profile = load_profile(path)
    os.environ["JOB_SEARCH_PROFILE"] = profile["_meta"]["path"]
    _JOBSPY_DIR = os.environ.get("JOB_SEARCH_RESULTS_DIR") or results_dir(profile)
    _REFERRAL_STATUS_PATH = referral_path(profile)
    _REFERRAL_STATUS = _load_referral_status(_REFERRAL_STATUS_PATH)
    _ILS_OVERRIDES = _load_ils_overrides(_ILS_OVERRIDES_PATH)
    _REMOTE_PREF = remote_policy(profile)["preference"]
    places = allowed_hybrid_places(profile)
    if places and _REMOTE_PREF == "hybrid_home_metro":
        parts = [re.escape(p.strip()).replace(r"\ ", r"\s+") for p in places]
        _ATL_BLOB = re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.IGNORECASE)


_REMOTE_PREF = "hybrid_home_metro"


def referral_status_for(company: object) -> str:
    """Return cold / warm / strong for a JobSpy company string. Default cold."""
    cs = str(company or '').lower()
    if not cs:
        return 'cold'
    # Substring match (not equality) — JobSpy company strings vary
    # ("Reveleer" vs "Reveleer, Inc." vs "Reveleer (via Indeed)").
    for key, status in _REFERRAL_STATUS.items():
        if key in cs:
            return status
    return 'cold'


def ils_floor_for(status: str, cold_floor: int) -> int:
    """Return the ILS floor for a referral status given the cold-tier baseline."""
    if status == 'strong':
        return max(0, cold_floor + _REFERRAL_STRONG_DELTA)
    if status == 'warm':
        return max(0, cold_floor + _REFERRAL_WARM_DELTA)
    return cold_floor


def _load_ils_overrides(path: str) -> dict[str, dict]:
    """Load per-company ILS point overrides. Empty dict on missing/bad file."""
    try:
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except FileNotFoundError:
        logging.warning('ils_overrides.json not found at %s; using formula-only', path)
        return {}
    except json.JSONDecodeError as exc:
        logging.warning('ils_overrides.json is malformed (%s); using formula-only', exc)
        return {}
    # Drop the leading _comment metadata; keep only score/note records.
    return {k: v for k, v in raw.items() if not k.startswith('_') and isinstance(v, dict)}


_ILS_OVERRIDES: dict[str, dict] = _load_ils_overrides(_ILS_OVERRIDES_PATH)

import run_search as rsl  # noqa: E402

try:
    from lib.domain_inference import (
        detect_gates as _di_detect_gates,
        estimate_tier_from_domain as _di_estimate_tier,
        infer_domain_from_text as _di_infer_domain,
    )
    _DOMAIN_INFERENCE_AVAILABLE = True
except ImportError as _exc:
    logging.warning('lib.domain_inference unavailable: %s; phase4 columns will be empty', _exc)
    _DOMAIN_INFERENCE_AVAILABLE = False

_RE_JOBSPY = re.compile(r"^jobspy_results_(\d{8})\.csv$")

# Employers that stay off SKIP_COMPANIES but never auto-classify as "apply".
_REVIEW_SUBSTRINGS = (
    "crowdstrike",
    "ifit solutions",
)

# Stricter than TITLE_REQUIRED: excludes pure PM/PO tracks that still hit the whitelist.
_QA_PRIMARY_HINTS = (
    "sdet",
    "software engineer in test",
    " set ",
    "quality",
    " qa",
    "qa ",
    " qe",
    "qe ",
    "test automation",
    "automation engineer",
    "evaluation",
    "llm eval",
    "model eval",
    "ai quality",
    "test engineer",
    "testing engineer",
)


def _qa_primary_title(title: str) -> bool:
    t = title.lower()
    return any(h in t for h in _QA_PRIMARY_HINTS)


def _is_review_company(company: object) -> bool:
    n = str(company or "").lower()
    for s in _REVIEW_SUBSTRINGS:
        if s in n:
            return True
    return n.strip() == "ifit"


# ── Staffing-wrapper detection (Patch 2026-05-15 #5) ─────────────────────────
#
# Problem: JobSpy preserves the LinkedIn `company` field, but for staffing-aug
# postings, that field is the staffing firm (DOMA Technologies, KForce, Apex
# Systems, Insight Global, etc.) — NOT the actual employer. The canonical JD
# URL also lives on the actual employer's ATS (paylocity, greenhouse, ashby,
# workday, ICIMS) rather than on LinkedIn. For example: JobSpy returned the
# 2026-05-15 Lead QA role under "DOMA Technologies" with the LinkedIn apply
# URL, but the actual employer is LIVANTA LLC / branded "Commence", and the
# canonical JD is at recruiting.paylocity.com/recruiting/jobs/Details/4145884/
# LIVANTA-LLC/Lead-Quality-Assurance-Engineer.
#
# What this module does:
# 1) Detect when JobSpy `company` matches a known staffing-wrapper substring.
# 2) Extract a best-effort "real employer" hint from the JD body via the
#    `At <Employer>, we…` opening pattern that 95%+ of staffing-aug JDs use.
# 3) Emit two output columns: `apply_url_check_needed` (bool) and
#    `wrapper_employer_hint` (str — may be empty if no hint extractable).
#
# This is a HINT, not a hard skip. The role still flows through normal
# triage; the columns just nudge Wei to find the canonical careers-page URL
# before applying. A future patch could resolve the URL automatically via
# playwright but that's out of scope here.

# Known staffing wrappers (lowercase substring match). Add new entries
# sparingly — false-positives degrade signal quality on direct hires.
_STAFFING_WRAPPERS: tuple[str, ...] = (
    "doma technologies",
    "kforce",
    "apex systems",
    "insight global",
    "robert half",
    "tek systems",
    "tekSystems".lower(),
    "n-ix",                 # staff-aug across LATAM/EU
    "epam",                 # large consultancy with US contracts
    "wissen",
    "infosys",
    "tcs",                  # tata
    "accenture",
    "deloitte",
    "cognizant",
    "capgemini",
)

# Pattern: matches "At Commence, we're…" / "At LIVANTA, our…" / "Join Acme as a…"
# style openings. Anchored to opening 1500 chars to avoid catching company
# names mentioned downstream as customers / partners. Non-greedy capture
# bounded by punctuation. Restrict capture group to letters/digits/space/
# common punctuation to avoid runaway matches.
_BODY_EMPLOYER_HINT = re.compile(
    r"\bAt\s+([A-Z][A-Za-z0-9&'.\-\s]{2,40}?),\s+(?:we|our)\b",
)
_BODY_EMPLOYER_HINT_JOIN = re.compile(
    r"\bJoin\s+([A-Z][A-Za-z0-9&'.\-\s]{2,40}?)\s+as\s+a\b",
)


def is_staffing_wrapper(company: object) -> bool:
    """True if the JobSpy `company` matches a known staffing wrapper."""
    cs = str(company or "").lower()
    if not cs:
        return False
    return any(w in cs for w in _STAFFING_WRAPPERS)


def extract_employer_hint(desc: object) -> str:
    """Best-effort extraction of the real-employer name from a JD body.

    Returns the captured name (preserved casing) or empty string on no match.
    Limited to the first 1500 chars of the body to avoid catching downstream
    mentions of partners / customers. Caller is responsible for confirming
    via the actual careers page; this is a hint only.
    """
    if desc is None or (isinstance(desc, float) and pd.isna(desc)):
        return ""
    s = str(desc)[:1500]
    # Try "At <Employer>, we/our" first (most common JD opener).
    m = _BODY_EMPLOYER_HINT.search(s)
    if m:
        name = m.group(1).strip().rstrip(",")
        # Skip generic non-employer captures.
        if name.lower() not in {"first", "least", "minimum", "this point", "this time"}:
            return name
    # Fall back to "Join <Employer> as a …"
    m = _BODY_EMPLOYER_HINT_JOIN.search(s)
    if m:
        return m.group(1).strip().rstrip(",")
    return ""


def detect_wrapper(company: object, desc: object) -> tuple[bool, str]:
    """Return (is_wrapper, employer_hint).

    - is_wrapper=True when JobSpy `company` matches a known staffing-wrapper
      substring. The hint is best-effort from JD body; may be empty.
    - is_wrapper=False otherwise. We still extract a hint when the JD opens
      with a clear "At <Employer>, we…" pattern AND the captured employer
      name does NOT match the JobSpy company (proxy signal for a wrapper we
      haven't catalogued yet). In that case is_wrapper stays False but the
      hint is surfaced; rule tag downstream is `wrapper_hint_unknown_pattern`.
    """
    if is_staffing_wrapper(company):
        return True, extract_employer_hint(desc)
    # Heuristic for unknown wrappers: JobSpy company and the JD's "At X, we"
    # opener disagree by enough that the role likely isn't directly with the
    # JobSpy company.
    hint = extract_employer_hint(desc)
    if hint:
        company_norm = re.sub(r'[^a-z0-9]', '', str(company or '').lower())
        hint_norm = re.sub(r'[^a-z0-9]', '', hint.lower())
        # Disagreement = neither name is a prefix of the other (covers
        # subsidiaries like "Acme Health" → "Acme" but flags true mismatches).
        if (
            company_norm and hint_norm
            and not company_norm.startswith(hint_norm)
            and not hint_norm.startswith(company_norm)
        ):
            return False, hint
    return False, ""


# Atlanta metro keywords for hybrid/onsite exception (aligns with run_search_locally spirit).
_ATL_BLOB = re.compile(
    r"\b(?:atlanta|alpharetta|roswell|marietta|sandy\s+springs|dunwoody|"
    r"decatur|buckhead|john'?s\s+creek|gwinnett|east\s+point|"
    r"college\s+park|midtown\s+atlanta|perimeter)\b",
    re.IGNORECASE,
)

# Employee US-remote signals (JD body).
_FULL_REMOTE_US = re.compile(
    r"(?:100%\s*remote|fully\s*remote|completely\s*remote|all[-\s]?remote\b"
    r"|💻\s*remote|#\s*li[-\s]?remote\b|remote\s+work\s*:|"
    r"this\s+is\s+a\s+remote\s+position\b|"
    r"remote\s+position\s+based\s+in\s+the\s+united\s+states|"
    r"flexibility\s+of\s+working\s+from\s+home|"
    r"work\s+from\s+home\s+while)",
    re.IGNORECASE,
)

# Primary office / not-remote-as-default.
_OFFICE_PRIMARY = re.compile(
    r"(?:based\s+at\s+the\s+\w+|full[-\s]?time\s+position\s+based\s+at|"
    r"day\s*1\s+onsite|onsite/hybrid|hybrid\)\s*[–-]\s*fulltime|"
    r"mode\s+of\s+work:\s*\d+\s*days?/\s*week\s+onsite|"
    r"remote\s+work\s+is\s+at\s+the\s+discretion\s+of\s+the\s+manager)",
    re.IGNORECASE,
)


def arrangement_skip(desc: object, loc: object, company: object) -> tuple[bool, str]:
    """
    True + reason if listing fails remote / hybrid-in-home-metro / not-primary-office rules.
    """
    if _REMOTE_PREF == 'fully_remote' and _OFFICE_PRIMARY.search(
        '' if desc is None or (isinstance(desc, float) and pd.isna(desc)) else str(desc)[:25000].lower()
    ):
        return True, 'arrangement_fully_remote_profile'
    d_raw = "" if desc is None or (isinstance(desc, float) and pd.isna(desc)) else str(desc)
    d = d_raw[:25_000].lower()
    l = "" if loc is None or (isinstance(loc, float) and pd.isna(loc)) else str(loc).lower()
    blob = d + "\n" + l
    cs = str(company or "").lower()

    if "based in mexico" in d or "currently based in mexico" in d:
        return True, "arrangement_non_us_remote"

    # YETI: HQ-primary role even if manager discretion mentions remote.
    if "yeti" in cs or re.search(r"based at the bozeman", d, re.I):
        return True, "arrangement_yeti_bozeman_primary"

    # Scheduled hybrid / onsite days (incl. Wissen-class).
    if re.search(
        r"(?:mode\s+of\s+work:\s*\d+\s*days?/\s*week\s+onsite|"
        r"\d+\s*days?/\s*week\s+onsite|day\s*1\s+onsite|onsite/hybrid)",
        d,
        re.I,
    ):
        return True, "arrangement_hybrid_or_scheduled_onsite"

    if "abbvie" in cs and "within the plant" in d:
        return True, "arrangement_plant_onsite"

    if "tram" in cs and not _FULL_REMOTE_US.search(d):
        return True, "arrangement_tram_no_employee_remote_jd"

    if "quva" in cs and not re.search(
        r"(?:100%\s*remote|fully\s*remote|this\s+is\s+a\s+remote\s+position|"
        r"remote\s+position\s+based\s+in\s+the\s+united\s+states|work\s+from\s+home)",
        d,
        re.I,
    ):
        return True, "arrangement_quva_no_employee_remote_statement"

    # Taulia (SAP group): Wei has direct-verified the role is fully US-remote
    # via Taulia's own careers page (`Location: US, Remote: Yes` in the
    # structured fields), but the LinkedIn JD body that JobSpy pulls only
    # carries the "Remote-friendly environment" benefits-section copy. The
    # pre-2026-05-15 carve-out flagged Taulia as `_remote_friendly_not_
    # guaranteed` which produced a false-positive skip on the otherwise
    # qualifying Principal QE role. Per Wei's allowlist override, bypass
    # arrangement_skip entirely for SAP Taulia. If a new evidence pattern
    # contradicts this (e.g. JD explicitly says hybrid Pleasanton), add a
    # negative carve-out here.
    _WEI_VERIFIED_REMOTE_US_EMPLOYERS = {"taulia", "sap taulia"}
    if any(emp in cs for emp in _WEI_VERIFIED_REMOTE_US_EMPLOYERS):
        return False, ""

    # Explicit US employee remote language → pass arrangement.
    if _FULL_REMOTE_US.search(d) or re.search(
        r"remote\s+in\s+[a-z]{2,4}\s+contract", d, re.I
    ):
        return False, ""

    if re.search(r"remote-friendly", d):
        return True, "arrangement_remote_friendly_only"

    if _OFFICE_PRIMARY.search(d):
        return True, "arrangement_primary_office_or_discretionary_remote"

    if re.search(r"\bhybrid\b", d):
        if _ATL_BLOB.search(blob):
            return True, "arrangement_hybrid_not_fully_remote_atl"
        return True, "arrangement_hybrid_non_atlanta"

    return False, ""


def _normalize_jd_for_scoring(desc: object) -> str:
    """Undo common LinkedIn/CSV escape noise so regexes match human-readable JDs."""
    if desc is None or (isinstance(desc, float) and pd.isna(desc)):
        return ""
    s = str(desc)[:24_000].lower()
    s = s.replace("\\-", "-").replace("\\.", ".").replace("\\+", "+")
    s = s.replace("\\%", "%")
    s = re.sub(r"\\(?=[%\-+.,:;])", "", s)
    return s


def compute_travel_penalty(d: str) -> tuple[int, str]:
    """
    Map stated travel % to ILS deduction band (aligned with docs/reference_ils_scoring_model.md).
    Returns (penalty 0..28, short evidence substring or "").
    """
    if not d:
        return 0, ""

    hi = 0
    tag = ""

    for m in re.finditer(
        r"(?:travel|require\s+you\s+to\s+travel)[^.]{0,55}?(\d{1,2})\s*[-–]\s*(\d{1,2})\s*%",
        d,
        re.I,
    ):
        hi = max(hi, int(m.group(1)), int(m.group(2)))
        tag = re.sub(r"\s+", " ", m.group(0))[:56]

    if hi == 0:
        m = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s*%\s*travel", d, re.I)
        if m:
            hi = max(int(m.group(1)), int(m.group(2)))
            tag = re.sub(r"\s+", " ", m.group(0))[:56]

    if hi == 0:
        m = re.search(r"up\s+to\s+(\d{1,2})\s*%\s*travel", d, re.I)
        if m:
            hi = int(m.group(1))
            tag = m.group(0)[:56]

    if hi == 0:
        m = re.search(r"\btravel\s+(?:of\s+|up\s+to\s+)?(\d{1,2})\s*%", d, re.I)
        if m:
            hi = int(m.group(1))
            tag = m.group(0)[:56]

    if hi <= 0:
        return 0, ""

    if hi >= 50:
        return 28, tag
    if hi >= 40:
        return 22, tag
    if hi >= 30:
        return 20, tag
    if hi >= 20:
        return 12, tag
    if hi >= 11:
        return 7, tag
    return 0, tag


def jd_derived_ils_fallback(row: pd.Series, d: str) -> tuple[int, str]:
    """
    Lightweight D1–D5-ish score when no hand-tuned company branch exists.
    Replaces flat 42 so Optimal/Peek/etc. spread realistically vs staffing gigs.
    """
    cs = str(row.get("company") or "").lower()
    title = str(row.get("title") or "").lower()

    tools = (
        "playwright",
        "cypress",
        "selenium",
        "typescript",
        "javascript",
        "python",
        "java",
        "golang",
        "kubernetes",
        "k8s",
        "aws",
        "azure",
        "gcp",
        "ci/cd",
        "pytest",
        "junit",
        "jenkins",
        "github actions",
        "graphql",
        "rest api",
        "appium",
        "postman",
        "docker",
        "terraform",
        "fhir",
        "hl7",
        "dicom",
        "cms",
        "snowflake",
        "kafka",
    )
    hits = sum(1 for t in tools if t in d)
    d1 = min(25, 5 + hits * 2)

    d2 = 14
    if re.search(r"(?:12|15)\s*\+?\s*years|12\+|15\+|15\s+years", d + " " + title):
        d2 = 9
    elif re.search(r"(?:10|11)\s*\+?\s*years|10\+|11\+", d + " " + title):
        d2 = 11
    elif re.search(r"(?:8|9)\s*\+?\s*years|8\+|9\+", d + " " + title):
        d2 = 13
    elif re.search(r"(?:5|6|7)\s*\+?\s*years|5\+|6\+|7\+", d + " " + title):
        d2 = 16

    if re.search(r"\b(?:phd|master'?s)\s+(?:degree\s+)?required\b", d):
        d2 -= 3

    d3 = 12
    if any(
        k in cs
        for k in (
            "staffing",
            "nearshore",
            "outstaffer",
            "jobot",
            "beacon",
            "tandym",
            "qat global",
            "autonomai",
            "bairesdev",
            "dataannotation",
            "distillery",
        )
    ):
        d3 -= 5
    if any(
        k in d[:2500]
        for k in (
            "staffing agency",
            "staffing firm",
            "nearshore",
            "body shop",
            "it consulting firm",
            "recruiting firm",
        )
    ):
        d3 -= 3
    if "nuclear" in d or "ap1000" in d:
        d3 = min(d3, 7)
    if any(k in d[:1200] for k in ("train ai models", "label data", "evaluate chatbots")):
        d3 -= 4

    d4 = 7
    d5 = 7

    tp, travel_tag = compute_travel_penalty(d)
    raw = d1 + d2 + d3 + d4 + d5 - tp

    if "contract" in d[:900] and "w2" not in d[:900]:
        raw -= 4

    score = int(max(18, min(72, raw)))
    bits = [f"d1≈{d1}", f"d2≈{d2}", f"d3≈{d3}", f"travel−{tp}"]
    if travel_tag:
        bits.append(f"({travel_tag})")
    return score, "jd_derived_fallback(" + "; ".join(bits) + ")"


def estimate_ils(row: pd.Series) -> tuple[int, str]:
    """
    Conservative ILS point estimate (0–100 scale per docs/reference_ils_scoring_model.md).
    Not a substitute for a full scored session — used only for the <45 skip gate.

    Lookup order:
      1. applications/ils_overrides.json — flat per-company {score, note} entries.
      2. Hardcoded "complex" branches below — companies with conditional logic
         (travel penalty, JD-comp lookup, JD-body OR clauses) that don't reduce
         to {score, note}.
      3. jd_derived_ils_fallback — generic D1–D5 formula on the JD body.
    """
    cs = str(row.get("company") or "").lower()
    d = _normalize_jd_for_scoring(row.get("description"))

    # 1. Simple per-company overrides from ils_overrides.json.
    for key, ov in _ILS_OVERRIDES.items():
        if key in cs:
            return int(ov["score"]), str(ov["note"])

    # 2. Complex per-company branches that don't reduce to {score, note}.

    # Westinghouse: D1+D2+D3+D4+D5 base minus dynamic travel penalty from JD.
    if "westinghouse" in cs:
        base = 12 + 12 + 5 + 7 + 6
        tp, _ = compute_travel_penalty(d)
        note = f"nuclear supplier QA; travel_penalty={tp}"
        return max(12, base - tp), note

    # Conduent: differentiate based on JD-stated comp band.
    if "conduent" in cs:
        if "85,000" in d or "95000" in d or "85,000" in d.replace("-", ""):
            return 41, "Listed ~85–95k band in JD; manual+automation mix; cold apply"
        return 44, "BPO-style services; cold apply"

    # Doma family: matches company OR a JD-body keyword (intentional widening).
    if "doma" in cs or "commence" in d[:400]:
        return 50, "Fed healthcare/CMS + FHIR; QA lead 8–12yr; remote stated"

    # 3. Generic JD-derived fallback (D1–D5 formula).
    return jd_derived_ils_fallback(row, d)


def post_gate_row(
    row: pd.Series,
    *,
    ils_floor: int,
    post_gates: bool,
) -> tuple[str, str, str, str]:
    """
    After pipeline verdict: return (final_verdict, final_rule, ils_str, ils_driver).
    """
    base_v = str(row.get("pipeline_verdict") or "")
    base_rule = str(row.get("pipeline_rule") or "")
    if base_v == "skip" or not post_gates:
        ils, inote = estimate_ils(row)
        return base_v, base_rule, f"{ils}", inote

    desc = row.get("description")
    loc = row.get("location")
    company = row.get("company")

    skip_arr, arr_r = arrangement_skip(desc, loc, company)
    ils, ils_note = estimate_ils(row)
    cs = str(company or "").lower()

    # ── Wei-verified-allowlist override (2026-05-15) ──
    # Some companies have JD-page evidence (from careers site) that contradicts
    # the LinkedIn body — Wei has manually verified them as US-remote /
    # legitimate-employer. Promote to `apply` (bypasses arrangement AND ILS
    # floor). Add to this tuple sparingly; the override skips both gates.
    _WEI_VERIFIED_ALLOWLIST = ("taulia", "sap taulia")
    if any(emp in cs for emp in _WEI_VERIFIED_ALLOWLIST):
        return "apply", "wei_verified_remote_allowlist", f"{ils}", ils_note

    if skip_arr:
        return "skip", arr_r, f"{ils}", ils_note

    # ── Referral-aware ILS floor (2026-05-15) ──
    # Look up the row's company in referral_status.txt; use a relaxed floor
    # for `warm` / `strong` entries. Default (cold) uses the CLI --ils-floor.
    # The applied floor is embedded in the rule tag so triage CSV consumers
    # can audit which tier fired.
    status = referral_status_for(company)
    effective_floor = ils_floor_for(status, ils_floor)
    if ils < effective_floor:
        if status == 'cold':
            rule = f"ils_below_{effective_floor}"
        else:
            rule = f"ils_below_{effective_floor}_{status}_tier"
        return "skip", rule, f"{ils}", ils_note

    if _is_review_company(str(company or "")):
        return "review", "review_tier_passed_gates", f"{ils}", ils_note

    # Surface the referral status on apply rows so Wei sees it in the triage
    # CSV without having to cross-reference the referral_status.txt file.
    if status == 'cold':
        return "apply", "pipeline_ok_post_gates", f"{ils}", ils_note
    return "apply", f"pipeline_ok_post_gates_{status}_tier", f"{ils}", ils_note


def latest_jobspy_csv(directory: str) -> str:
    paths = []
    for name in os.listdir(directory):
        m = _RE_JOBSPY.match(name)
        if m:
            paths.append(os.path.join(directory, name))
    if not paths:
        raise SystemExit(f"No jobspy_results_YYYYMMDD.csv under {directory}")
    return max(paths, key=lambda p: _RE_JOBSPY.match(os.path.basename(p)).group(1))


def _scalar(val: object) -> object:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return val


def triage_row(row: pd.Series, *, require_qa_primary: bool) -> tuple[str, str]:
    """
    Return (verdict, rule) where rule is a short machine-readable reason for skip/review.
    """
    company = _scalar(row.get("company"))
    title = _scalar(row.get("title"))
    desc = row.get("description")
    loc = _scalar(row.get("location"))
    mn = row.get("min_amount")
    mx = row.get("max_amount")

    company_s = "" if company is None else str(company)
    title_s = "" if title is None else str(title)
    loc_s = "" if loc is None else str(loc)

    if rsl.is_skip_company(company_s):
        return "skip", "skip_company"
    # ── Wrapper-hint cross-check (Patch 2026-05-15 #6) ──
    # JobSpy preserves the LinkedIn `company` field. For staffing-aug rows
    # (DOMA, KForce, Apex, Insight Global, etc.), the wrapper passes the
    # `is_skip_company` check but the *real* employer extracted from the JD
    # body via `detect_wrapper` may be on the skip list. Cross-check that
    # hint against the same skip set so a Commence-via-DOMA row auto-skips
    # the same way a direct Commence Health row would. Without this check,
    # the Aug-2025 LIVANTA→Commence rebrand + DOMA staffing routing would
    # let the same role re-enter the apply pool indefinitely.
    #
    # NOTE: `is_skip_company` uses one-direction prefix matching
    # (input.startswith(skip_key)). The wrapper-hint extraction returns short
    # opening tokens like "Commence" which CANNOT be a prefix of the longer
    # skip key "commencehealth". We need BIDIRECTIONAL prefix matching here:
    # treat as a skip if either direction is a prefix-match. This is the
    # canonical semantic for "wrapper hint plausibly references skip-listed
    # employer". Restrict to hints ≥4 chars to avoid degenerate matches.
    is_wrapper, wrapper_hint = detect_wrapper(company_s, desc)
    if is_wrapper and wrapper_hint:
        hint_norm = rsl.normalize_company_key(wrapper_hint)
        if hint_norm and len(hint_norm) >= 4:
            # Lazy-init skip set via existing accessor.
            if rsl._NORMALIZED_SKIP is None:
                rsl._NORMALIZED_SKIP = rsl._build_normalized_skip_keys()
            for skip_key in rsl._NORMALIZED_SKIP:
                if hint_norm.startswith(skip_key) or skip_key.startswith(hint_norm):
                    return "skip", "skip_company_via_wrapper_hint"
    if rsl.is_skip_title_company_signal(title_s):
        return "skip", "skip_title_company_signal"
    if rsl.has_title_blocker(title_s):
        return "skip", "title_blocker"
    if not rsl.has_required_signal(title_s):
        return "skip", "missing_title_required_signal"
    if rsl.has_pe(desc):
        return "skip", "pe_signal_in_jd"
    if not rsl.comp_ok(mn, mx):
        return "skip", "comp_below_threshold"
    if rsl.has_desc_blocker(desc):
        return "skip", "desc_blocker"
    if not rsl.is_us_remote(loc_s):
        return "skip", "non_us_remote_location"
    if not rsl.passes_wei_geo_and_work_mode(desc, loc_s):
        return "skip", "geo_or_work_mode"

    if _is_review_company(company_s):
        return "review", "review_tier_employer"

    if require_qa_primary and not _qa_primary_title(title_s):
        return "skip", "not_qa_primary_title"

    return "apply", "pipeline_ok"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "csv_path",
        nargs="?",
        help="Path to jobspy_results_YYYYMMDD.csv (default: --latest)",
    )
    ap.add_argument(
        "--latest",
        action="store_true",
        help=f"Use newest jobspy_results_*.csv under {_JOBSPY_DIR}",
    )
    ap.add_argument(
        "--out",
        metavar="FILE",
        help="Write full triage CSV with verdict + rule columns",
    )
    ap.add_argument(
        "--include-pm-po",
        action="store_true",
        help="Allow Product Owner / TPM-only titles into apply (default: QA-primary titles only)",
    )
    ap.add_argument(
        "--ils-floor",
        type=int,
        default=45,
        metavar="N",
        help="Skip post-gate if conservative ILS estimate is below N (default: 45)",
    )
    ap.add_argument(
        "--no-post-gates",
        action="store_true",
        help="Disable ILS + arrangement post-gates (pipeline only)",
    )
    ap.add_argument(
        "--profile",
        help="Search profile YAML (default: JOB_SEARCH_PROFILE env)",
    )
    args = ap.parse_args()

    _configure_from_profile(args.profile)
    if args.profile or os.environ.get('JOB_SEARCH_PROFILE'):
        from lib.search_profile import load_profile, ils_floor

        _p = load_profile(args.profile or os.environ['JOB_SEARCH_PROFILE'])
        args.ils_floor = ils_floor(_p, 'cold')

    if args.latest and args.csv_path:
        ap.error("Pass either --latest or a csv path, not both")
    if args.latest:
        path = latest_jobspy_csv(_JOBSPY_DIR)
    elif args.csv_path:
        path = os.path.expanduser(args.csv_path)
    else:
        path = latest_jobspy_csv(_JOBSPY_DIR)

    if not os.path.isfile(path):
        raise SystemExit(f"Not a file: {path}")

    df = pd.read_csv(path)
    require_qa = not args.include_pm_po
    pv, pr = [], []
    for _, row in df.iterrows():
        v, ru = triage_row(row, require_qa_primary=require_qa)
        pv.append(v)
        pr.append(ru)
    df = df.copy()
    df["pipeline_verdict"] = pv
    df["pipeline_rule"] = pr

    post_gates = not args.no_post_gates
    fv, fr, ils_es, ils_ns = [], [], [], []
    for _, row in df.iterrows():
        row2 = row.copy()
        row2["pipeline_verdict"] = row["pipeline_verdict"]
        row2["pipeline_rule"] = row["pipeline_rule"]
        a, b, c, d = post_gate_row(
            row2,
            ils_floor=args.ils_floor,
            post_gates=post_gates,
        )
        fv.append(a)
        fr.append(b)
        ils_es.append(c)
        ils_ns.append(d)
    df["triage_verdict"] = fv
    df["triage_rule"] = fr
    df["ils_estimate"] = ils_es
    df["ils_driver"] = ils_ns

    # ── Wrapper / canonical-employer hint columns (Patch 2026-05-15 #5) ──
    # Computed on all rows (not just apply) so the audit trail covers skip
    # rows too — useful for revisiting skipped roles when a wrapper-class
    # signal might have changed.
    wrap_flags: list[bool] = []
    wrap_hints: list[str] = []
    for _, row in df.iterrows():
        is_w, hint = detect_wrapper(row.get("company"), row.get("description"))
        wrap_flags.append(is_w)
        wrap_hints.append(hint)
    df["apply_url_check_needed"] = wrap_flags
    df["wrapper_employer_hint"] = wrap_hints

    # ── Phase 4 enrichment (2026-05-16 merge) ──
    # Per-row domain inference + gate flags, sourced from
    # refresh_lib.domain_inference so both pipelines stay aligned. These
    # columns are advisory: they DO NOT change triage_verdict (which is
    # already finalised above). Wei reads them as additional context when
    # spot-checking the apply pool. Surfaces three failure modes that the
    # legacy pipeline misses today:
    #   1. CSV `domain` column empty/`?` → infer from title+desc+company
    #   2. JD looks senior-titled but body says junior/intern/freelance
    #   3. Tier estimate from inferred domain disagrees with comp band
    if _DOMAIN_INFERENCE_AVAILABLE:
        inferred_domains: list[str] = []
        estimated_tiers: list[str] = []
        gate_flags: list[str] = []
        for _, row in df.iterrows():
            title_s = str(row.get("title") or "")
            desc_s = str(row.get("description") or "")
            company_s2 = str(row.get("company") or "")
            loc_s = str(row.get("location") or "")
            csv_domain = str(row.get("domain") or "").strip()

            # Domain: trust CSV column if non-empty/non-?, else infer.
            if csv_domain and csv_domain not in {"?", "unknown"}:
                inferred = csv_domain
            else:
                inferred_opt = _di_infer_domain(title_s, desc_s, company_s2)
                inferred = inferred_opt or ""

            # Tier estimate from the domain.
            tier_opt = _di_estimate_tier(inferred) if inferred else None
            tier_str = f"T{tier_opt}" if tier_opt is not None else ""

            # Gate flags (level / contract / stack / non-US).
            try:
                stack_n = int(row.get("stack_hits") or 0)
            except (ValueError, TypeError):
                stack_n = 0
            gates = _di_detect_gates(
                title=title_s,
                description=desc_s,
                location=loc_s,
                stack_hits=stack_n,
            )
            flag_parts: list[str] = []
            if gates.get("level_mismatch"):
                flag_parts.append("LEVEL")
            if gates.get("contract_role"):
                flag_parts.append("CONTRACT")
            if gates.get("zero_stack_hits"):
                flag_parts.append("ZERO-STACK")
            if gates.get("manufacturing_stack"):
                flag_parts.append("MFG-STACK")
            if gates.get("non_us_location"):
                flag_parts.append("NON-US")
            flag_str = "|".join(flag_parts)

            inferred_domains.append(inferred)
            estimated_tiers.append(tier_str)
            gate_flags.append(flag_str)
        df["inferred_domain"] = inferred_domains
        df["estimated_tier"] = estimated_tiers
        df["phase4_gate_flags"] = gate_flags
    else:
        df["inferred_domain"] = ""
        df["estimated_tier"] = ""
        df["phase4_gate_flags"] = ""

    n_skip = sum(1 for v in fv if v == "skip")
    n_review = sum(1 for v in fv if v == "review")
    n_apply = sum(1 for v in fv if v == "apply")

    print(f"Source: {path}")
    print(
        f"Rows: {len(df)}  skip={n_skip}  review={n_review}  apply={n_apply}"
        + ("  [post-gates ON]" if post_gates else "  [post-gates OFF]")
    )

    if args.out:
        out_path = os.path.expanduser(args.out)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        df.to_csv(out_path, index=False)
        print(f"Wrote: {out_path}")

    apply_df = df[df["triage_verdict"] == "apply"].copy()
    if apply_df.empty:
        print("\nNo rows with final verdict=apply.")
        return

    cols = [
        "track",
        "title",
        "company",
        "location",
        "min_amount",
        "max_amount",
        "priority",
        "ils_estimate",
        "estimated_tier",
        "phase4_gate_flags",
        "job_url",
        "triage_rule",
    ]
    use = [c for c in cols if c in apply_df.columns]
    print("\n--- APPLY (good pipeline fit) ---\n")
    # Tab-separated for easy paste; no markdown table requirement in script stdout
    print("\t".join(use))
    for _, row in apply_df.iterrows():
        print("\t".join(str(row.get(c, "")) for c in use))


if __name__ == "__main__":
    main()
