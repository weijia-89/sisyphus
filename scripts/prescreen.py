"""
prescreen.py — lightweight pre-triage scoring for jobspy results.

Adds 5 columns to a filtered jobs DataFrame:
  stack_hits  int    Count of Wei's stack keywords in JD description.
                     GH-track rows have no description, always 0.
  yrs_req     int|   Max year requirement from experience-anchored regex.
              None   None = not stated (not 0).
  domain      str    native | adj | far | ?
                     Title-first; description fallback uses multi-word phrases
                     only (avoids "insurance benefits" false positive).
  funding     str    First funding stage/status detected, e.g. "Series B",
                     "bootstrapped", "$50M in funding". '?' if none found.
  priority    str    HIGH | MOD | LOW | ?
                     Rough triage flag (NOT a score): which rows merit a full
                     ILS session. The disclaimer is load-bearing — downstream
                     consumers (e.g. ingest-search-results SKILL) regularly
                     mistake this column for an ILS estimate. It is not.
                     '?' = no JD description; review the URL manually.

Three-layer scoring stack — boundaries are intentional, do not collapse them:

  1. prescreen.priority (this file)
       Stage:  in-CSV during scrape.
       Scale:  HIGH | MOD | LOW | ?  (categorical flag, no points).
       Cost:   ~0ms per row, regex-only.
       Use:    quick visual triage in the CSV; do not feed into ILS gate.

  2. triage_jobspy_csv.estimate_ils
       Stage:  post-scrape via `python3 scripts/triage_jobspy_csv.py --latest`.
       Scale:  ils_estimate column, integer 0–100.
       Cost:   per-company hardcoded overrides + D1–D5 fallback formula.
       Use:    apply/review/skip gate at threshold ~45.
       Spec:   docs/reference_ils_scoring_model.md.

  3. JFS (job-fit score)
       Stage:  manual research session, post ILS ≥45.
       Scale:  C1–C7 dimensions, integer 0–100.
       Cost:   30–60 minutes of human research per role.
       Use:    happiness predictor; controls how much resume tailoring effort
               to invest.
       Spec:   applytime/references/job_fit_score.md.

If you find yourself wanting to "promote" priority into a numeric score, stop —
that's what triage_jobspy_csv.estimate_ils is for. If you find yourself wanting
estimate_ils to be more accurate, stop — that's what JFS is for, and JFS is
deliberately manual. The layers are different costs serving different decisions.

Design decisions:
  - Domain classification is title-first to avoid false positives from
    boilerplate text ("insurance benefits", "25 years in business").
  - Description fallback uses only multi-word, domain-specific phrases.
  - Year regex is anchored to experience/minimum/required context —
    not bare "N+ years" which matches company age.
  - 'golang' used instead of 'go' to avoid matching "go" in common words.
  - c7 (comp floor) is NOT a new column — min_amount/max_amount already
    carry that signal in the CSV.

To add keywords to Wei's stack: edit _WEI_STACK_KEYWORDS below.
"""

import re
import math
import pandas as pd


# ── Wei's canonical tech stack ────────────────────────────────────────────────
# Update as stack evolves. Lowercase, substring-match safe.
# 'golang' intentionally used instead of bare 'go' (too many false matches).
_WEI_STACK_KEYWORDS = frozenset([
    'playwright', 'python', 'pytest', 'typescript', 'javascript',
    'github actions', 'ci/cd', 'cicd', 'rest api', 'graphql',
    'selenium', 'docker', 'sql', 'golang',
    'llm eval', 'llm evaluation', 'ai evaluation', 'model evaluation',
    'test automation', 'shift-left', 'shift left',
    'api testing', 'automated testing', 'e2e testing',
])


# ── Domain classification: title keywords ─────────────────────────────────────
# Title is the primary signal. Far > native > adj priority order prevents
# "LLM evaluation for mortgage platform" from misclassifying as native.
_DOMAIN_FAR_TITLE = frozenset([
    'commercial real estate', 'mortgage origination', 'mortgage servicing',
    'loan origination', 'loan servicing', 'insurtech', 'insurance technology',
    'genomics', 'genomic', 'clinical diagnostics', 'precision medicine',
    'defense', 'government', 'construction', 'manufacturing',
    # Industrial control / OT — keyword collision with software stack
    'scada', 'industrial automation', 'ignition platform', 'plc',
    'operational technology', 'process control',
])
_DOMAIN_NATIVE_TITLE = frozenset([
    'llm', 'language model', 'ai eval', 'model eval', 'model quality',
    'observability', 'developer productivity', 'developer tools', 'devtools',
    'martech', 'marketing automation', 'email platform',
    'generative ai', 'gen ai',
])
_DOMAIN_ADJ_TITLE = frozenset([
    'fintech', 'healthtech', 'health tech', 'edtech', 'ed tech',
    'platform engineering', 'identity', 'compliance tech',
])


# ── Domain classification: description fallback ───────────────────────────────
# Multi-word phrases only — avoids false positives from benefits/boilerplate.
# Only first 500 chars of description scanned (introductory section).
# Single words like 'insurance' or 'real estate' are intentionally excluded.
_DOMAIN_FAR_DESC = frozenset([
    'commercial real estate', 'mortgage origination', 'loan servicing',
    'insurtech', 'insurance technology', 'genomic sequencing',
    'clinical genomics', 'precision medicine', 'defense contractor',
])
_DOMAIN_NATIVE_DESC = frozenset([
    'llm evaluation', 'language model evaluation', 'ai evaluation platform',
    'model evaluation platform', 'email deliverability platform',
    'email marketing platform', 'marketing automation platform',
    'developer productivity platform', 'developer tools platform',
    'generative ai platform', 'foundation model',
])
_DOMAIN_ADJ_DESC = frozenset([
    'financial technology', 'electronic health record',
    'electronic medical record', 'health information platform',
    'learning management system', 'edtech platform',
])


# ── Compiled regexes ──────────────────────────────────────────────────────────
# Year requirement: anchored to experience/minimum context.
# Matches: "5+ years of experience", "minimum 8 years", "at least 7 years of QA experience"
# Does NOT match: "25 years in business", "founded 10 years ago".
_YRS_EXP_RE = re.compile(
    r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:relevant\s+)?'
    r'(?:professional\s+)?(?:experience|exp\b)',
    re.IGNORECASE,
)
_MIN_YRS_RE = re.compile(
    r'(?:minimum|at\s+least|requires?)\s+(\d+)\+?\s*(?:years?|yrs?)',
    re.IGNORECASE,
)

# Funding stage/status — multi-word and specific to avoid false matches.
_FUNDING_RE = re.compile(
    # No outer \b wrapper — \b before \$ never fires (\$ is \W, no word boundary).
    # Each pattern is specific enough to avoid false positives without word boundaries.
    r'(?:'
    r'Series\s+[A-E]'
    r'|(?<!\w)Seed(?:\s+round)?(?!\w)'
    r'|bootstrapped?'
    r'|self[-\s]funded'
    r'|pre-seed'
    r'|pre-IPO'
    r'|publicly\s+traded'
    r'|(?<!\w)NYSE(?!\w)|(?<!\w)NASDAQ(?!\w)'
    r'|went\s+public'
    r'|\$\s*\d+(?:\.\d+)?[MB]\s+(?:raised|in\s+funding)'
    r')',
    re.IGNORECASE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_empty(val) -> bool:
    """True for None, NaN (float), or blank string."""
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    if isinstance(val, str) and not val.strip():
        return True
    return False


def _extract_min_years(text) -> 'int | None':
    """
    Return the maximum year requirement found in experience-anchored context.
    Returns None (not 0) when no requirement is stated — caller distinguishes
    'explicitly not required' from 'unknown'.
    """
    if _is_empty(text):
        return None
    t = str(text)[:5000]
    matches = [int(m) for m in _YRS_EXP_RE.findall(t)]
    matches += [int(m) for m in _MIN_YRS_RE.findall(t)]
    return max(matches) if matches else None


def _score_stack(text) -> int:
    """Count Wei's stack keywords in description. 0 for empty/NaN (e.g. GH-track rows)."""
    if _is_empty(text):
        return 0
    t = str(text)[:5000].lower()
    return sum(1 for kw in _WEI_STACK_KEYWORDS if kw in t)


def _classify_domain(title: str, desc) -> str:
    """
    Classify job domain: native | adj | far | ?

    Priority order: far > native > adj (prevents ambiguous multi-domain titles
    from landing in native when the actual domain is far).

    Title scan first. Description fallback uses only multi-word phrases from
    the first 500 chars (company intro paragraph) to avoid false positives
    from benefits text or boilerplate ("insurance benefits", "real estate prices").
    """
    t = (title or '').lower()

    # Title scan — any keyword substring match
    if any(kw in t for kw in _DOMAIN_FAR_TITLE):
        return 'far'
    if any(kw in t for kw in _DOMAIN_NATIVE_TITLE):
        return 'native'
    if any(kw in t for kw in _DOMAIN_ADJ_TITLE):
        return 'adj'

    # Description fallback — first 500 chars, multi-word phrases only
    d = str(desc)[:500].lower() if not _is_empty(desc) else ''
    if any(kw in d for kw in _DOMAIN_FAR_DESC):
        return 'far'
    if any(kw in d for kw in _DOMAIN_NATIVE_DESC):
        return 'native'
    if any(kw in d for kw in _DOMAIN_ADJ_DESC):
        return 'adj'

    return '?'


def _extract_funding(text) -> str:
    """Return first funding stage/status mention, or '?' if none found."""
    if _is_empty(text):
        return '?'
    m = _FUNDING_RE.search(str(text)[:3000])
    return m.group(0).strip() if m else '?'


def _yrs_ok(yrs_req, max_yrs: int) -> bool:
    """True when yrs_req is None, NaN (pandas null after DataFrame round-trip), or <= max_yrs."""
    if yrs_req is None:
        return True
    try:
        return math.isnan(float(yrs_req)) or float(yrs_req) <= max_yrs
    except (TypeError, ValueError):
        return True  # unparseable → treat as unstated


def _compute_priority(stack_hits: int, yrs_req,
                      domain: str, has_desc: bool) -> str:
    """
    Triage priority: HIGH | MOD | LOW | ?

    NOT the ILS model. Use to identify which rows merit a full ILS session
    with Claude. Rules:

      ?     No description (GH-track). Review the URL manually.
      LOW   Hard ILS blocker: yrs_req > 8 OR domain == far.
      HIGH  stack_hits >= 3 AND yrs_req <= 7 (or unstated/NaN). Domain may be '?'.
            Strong stack signal alone justifies HIGH — domain gap is a separate
            conversation, not a reason to pre-filter.
      MOD   stack_hits >= 1 AND yrs_req <= 8 (or unstated/NaN) AND domain != far.
      LOW   Everything else (no stack signal, or blocked by domain/years).

    NaN handling: pandas converts Python None to NaN in numeric Series.
    _yrs_ok() treats NaN the same as None (year requirement unstated).
    """
    if not has_desc:
        return '?'

    # Hard blockers — NaN yrs_req passes (unstated ≠ required)
    if not _yrs_ok(yrs_req, 8):
        return 'LOW'
    if domain == 'far':
        return 'LOW'

    # Strong signal
    if stack_hits >= 3 and _yrs_ok(yrs_req, 7):
        return 'HIGH'

    # Moderate signal
    if stack_hits >= 1 and _yrs_ok(yrs_req, 8):
        return 'MOD'

    return 'LOW'


# ── Public API ────────────────────────────────────────────────────────────────

def add_prescreen_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add pre-screen triage columns to a filtered jobs DataFrame in-place.
    Returns the same DataFrame (mutated) for chaining.

    Columns added: stack_hits, yrs_req, domain, funding, priority.
    Sort order changed to: priority (HIGH→MOD→LOW→?) → track → date_posted desc.
    """
    df = df.copy()

    df['stack_hits'] = df['description'].apply(_score_stack)
    df['yrs_req']    = df['description'].apply(_extract_min_years)
    df['domain']     = df.apply(
        lambda r: _classify_domain(
            str(r.get('title', '')),
            r.get('description', ''),
        ),
        axis=1,
    )
    df['funding'] = df['description'].apply(_extract_funding)
    df['priority'] = df.apply(
        lambda r: _compute_priority(
            r['stack_hits'],
            r['yrs_req'],
            r['domain'],
            bool(str(r.get('description', '')).strip()),
        ),
        axis=1,
    )

    # Sort: priority first, then track (preserves existing track grouping within tier),
    # then date descending. Replaces the previous track-only sort.
    _PRIORITY_ORDER = {'HIGH': 0, 'MOD': 1, 'LOW': 2, '?': 3}
    df['_p_sort'] = df['priority'].map(_PRIORITY_ORDER).fillna(3).astype(int)
    df = df.sort_values(
        ['_p_sort', 'track', 'date_posted'],
        ascending=[True, True, False],
        na_position='last',
    )
    df = df.drop(columns=['_p_sort'])

    return df
