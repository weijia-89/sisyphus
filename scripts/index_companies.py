from __future__ import annotations

"""Parse application_index.html for company tokens (auto-skip / dedupe).

Normative behavior: docs/application_index_company_extraction_contract.md (v1.4.0).
v1.4.0 (2026-05-15) ADDED `<div class="skip-item">` extraction (Veritone-class
gap): previously only `<span class="role">` was indexed, so companies that Wei
had explicitly written off via the "Skipped" section never fed auto-skip.
v1.3.0 added §10 consumer-normalization clause; extractor is otherwise
unchanged from v1.2.0. The reference normalization implementation lives in
`run_search_locally.normalize_company_key` and is what consumers MUST apply
when comparing tokens emitted here against JobSpy / ATS company strings.
"""

INDEX_COMPANIES_CONTRACT_VERSION = "1.4.0"
INDEX_COMPANIES_ROLE_PATTERN = r'class="role"[^>]*>(?:<[^>]+>)?([^—–<]+)'
# Skip-item entries look like: <div class="skip-item"><strong>Company (Role)</strong>
# Capture the company name up through the optional " (Role description)" paren;
# the consumer's _skip_key_variants (run_search_locally) handles the paren strip
# so both bare and paren-suffixed forms are matched against JobSpy companies.
INDEX_COMPANIES_SKIP_ITEM_PATTERN = (
    r'class="skip-item"[^>]*>\s*<strong[^>]*>([^<—–]+?)(?:\s*</strong>)'
)

import logging
import re
from pathlib import Path

_ROLE_COMPANY = re.compile(INDEX_COMPANIES_ROLE_PATTERN)
_SKIP_ITEM_COMPANY = re.compile(INDEX_COMPANIES_SKIP_ITEM_PATTERN)


def load_applied_companies(html: str) -> set[str]:
    """Company slugs from BOTH `<span class="role">` and `<div class="skip-item">`.

    Per contract v1.4.0: both sections feed the auto-skip set. Role rows are
    canonical applications/in-pipeline; skip-item entries are Wei's explicit
    written-off list (Glassdoor red flags, comp ceilings, layoff signals).
    Both should suppress the company from future scrapes.
    """
    found: set[str] = set()
    for m in _ROLE_COMPANY.finditer(html):
        company = m.group(1).strip().rstrip(",").lower()
        if len(company) > 2:
            found.add(company)
    for m in _SKIP_ITEM_COMPANY.finditer(html):
        company = m.group(1).strip().rstrip(",").lower()
        if len(company) > 2:
            found.add(company)
    return found


def load_applied_companies_from_path(path: str | Path) -> set[str]:
    try:
        html = Path(path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return set()
    except OSError as exc:
        logging.warning("auto-skip parse: %s", exc)
        return set()
    return load_applied_companies(html)
