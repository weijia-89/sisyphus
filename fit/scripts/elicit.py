#!/usr/bin/env python3
"""elicit.py: structured elicitation harness for cover letters, resumes,
and role-preference values.

Each subcommand walks through a focused set of prompts, saves answers
to a session JSON file under `localonly/sessions/`, and prints a brief
summary. Future cover-letter or resume drafts can read from these
sessions to maintain a consistent voice and value-set across applications.

Subcommands:

  values         Capture role-preference values: what you want and what
                 you refuse to compromise on. One-time setup (or re-run
                 when preferences shift).

  cover-letter   Walk through cover-letter prep for one specific
                 application. Captures the why-this-company, why-now,
                 and specific-fit answers.

  resume         Capture resume-tailoring inputs: which experiences
                 to foreground for this application, which to demote.

  next-application  Quick pre-application checklist: company, role,
                    expected scoring inputs for the corpofit calculator.

Sessions are local-only. The `localonly/` directory is gitignored.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Optional


_SCRIPT = Path(__file__).resolve()
_REPO_ROOT = _SCRIPT.parent.parent
_SESSIONS_DIR = _REPO_ROOT / "localonly" / "sessions"


# Schema versioning lets future-you migrate old sessions if the
# prompt set changes substantively.
SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Prompt sets per subcommand. Each prompt has a key, a question, and an
# optional follow-up hint. The order is the elicitation order.
# ---------------------------------------------------------------------------

VALUES_PROMPTS: list[tuple[str, str, str]] = [
    ("must_have",
     "What three role attributes must be present for you to apply at all?",
     "Examples: remote-first, salary above X, no on-call, manager you can name and verify."),
    ("must_not_have",
     "What three role attributes will cause you to skip an application no matter how good the rest looks?",
     "Examples: open floor plan, mandatory commute, particular tooling, particular industry vertical."),
    ("growth_target",
     "What specific skill or scope are you trying to add in the next role?",
     "Be concrete: 'tech-lead a service from design to launch', 'manage a team of 4', 'switch from IC to PM'."),
    ("title_floor",
     "What is the lowest title you would accept for this growth target?",
     "Examples: 'Senior X' if you are L5; 'Staff X' if you are L6; 'Director' if you have managed before."),
    ("comp_floor",
     "What total-compensation figure (base + variable, annualized) is your walk-away threshold?",
     "Anything below this hits Gate 2 in the corpofit calculator and stops you. Round to nearest $5k."),
    ("comp_target",
     "What total-compensation figure is your 'enthusiastic yes'?",
     "Usually 20-40 percent above the floor. This is what you ask for in compensation negotiation."),
    ("voice_signature",
     "Describe your professional voice in one or two sentences.",
     "What words come to mind for how you write? Examples: 'direct, evidence-first, mildly dry'; 'warm, narrative, careful with claims'."),
    ("non_negotiable_values",
     "Are there industries, business models, or specific companies you will not work for?",
     "Tier-9 hard-blocks from the industry classification rubric usually go here. Be specific."),
]

COVER_LETTER_PROMPTS: list[tuple[str, str, str]] = [
    ("company",
     "What is the company name (exact spelling for the letter)?",
     ""),
    ("role_title",
     "What is the role title (exact spelling)?",
     ""),
    ("hiring_manager",
     "Who is the hiring manager, if known? (Name, optional Linkedin handle.)",
     "Leave blank if you only have a recruiter contact."),
    ("source",
     "How did you find this role? (Referral, search, recruiter outreach, etc.)",
     "If a referral, name the person. Cover letter should acknowledge the path in for warmth."),
    ("why_this_company",
     "Why this company specifically (two or three sentences)?",
     "Avoid generic praise. Reference a product, a publication, a hire, a strategic move."),
    ("why_now",
     "Why are you looking to move now (one sentence)?",
     "Honest. Not 'pursuing new challenges'. Try: 'team hit a stable point, ready to learn a new domain'."),
    ("specific_fit",
     "Which 2-3 bullet points from the JD do you map onto cleanly, and with what evidence?",
     "Pull from your last 18 months. Quantify where possible. One paragraph per bullet."),
    ("risk_or_gap",
     "What is the one risk or gap the reviewer will notice, and how would you address it?",
     "Pre-empting one risk in the letter signals self-awareness and saves the screen for harder questions."),
]

RESUME_PROMPTS: list[tuple[str, str, str]] = [
    ("company",
     "What is the target company name?",
     ""),
    ("role_title",
     "What is the target role title?",
     ""),
    ("jd_top_three",
     "List the top three requirements from the JD in priority order.",
     "Use the exact phrasing from the JD. The resume should echo these phrases verbatim where possible."),
    ("experience_to_foreground",
     "Which 2-3 of your past roles or projects most directly demonstrate the JD top three?",
     "Reorder your resume so these are visually prominent. Bullets under them should be the strongest."),
    ("experience_to_demote",
     "Which past roles or projects should you compress or omit for this application?",
     "Roles 8+ years old often compress to a single line. Side projects that don't map can be cut."),
    ("metric_anchors",
     "List 3-5 quantitative achievements that map onto this role.",
     "Examples: 'reduced p99 from 1.2s to 380ms', 'led 4-engineer team', 'launched feature with 250k DAU'."),
    ("voice_check",
     "Read your draft aloud. Does it sound like your voice signature from the values session?",
     "If it sounds vibe-coded or templated, rewrite for tone."),
]

NEXT_APPLICATION_PROMPTS: list[tuple[str, str, str]] = [
    ("company",
     "Company name?",
     ""),
    ("role_title",
     "Role title?",
     ""),
    ("classified_tier",
     "Industry tier classification (1-10) per your own ethics rubric?",
     "Bring your tier judgment; corpofit takes the tier as user input. The calculator requires this."),
    ("c1_psych_safety",
     "C1 (psychological safety, 0-12.7)?",
     "What evidence do you have from Glassdoor, Blind, your network?"),
    ("c2_wlb",
     "C2 (WLB reliability, 0-14.1)?",
     "Off-hours norms? On-call? Vacation pattern?"),
    ("c3_manager",
     "C3 (direct manager, 0-14.1)?",
     "Tenure? Communication style? Direct reports' retention?"),
    ("c4_security",
     "C4 (job security, 0-12.7)?",
     "Funding? Layoff history? Business-unit health?"),
    ("c6_growth",
     "C6 (career growth, 0-8.5)?",
     "Scope? On-job learning? Transferable signals?"),
    ("c7_comp",
     "C7 (comp sustainability, 0-2.8)?",
     "Does the comp cover fixed costs with margin?"),
    ("comp_estimate",
     "Estimated comp (total annualized USD)?",
     "Use JD midpoint at pre-offer stage; use actual offer at offer stage."),
]


PROMPT_SETS: dict[str, list[tuple[str, str, str]]] = {
    "values": VALUES_PROMPTS,
    "cover-letter": COVER_LETTER_PROMPTS,
    "resume": RESUME_PROMPTS,
    "next-application": NEXT_APPLICATION_PROMPTS,
}


def slugify(text: str) -> str:
    """Make a filename-safe slug from arbitrary user input."""
    if not text:
        return "unnamed"
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    s = s.strip("-")
    return s or "unnamed"


def run_prompts(prompts: list[tuple[str, str, str]]) -> dict[str, str]:
    """Walk through the prompts. Empty input means 'skip this field'."""
    answers: dict[str, str] = {}
    for key, question, hint in prompts:
        print()
        print(f"  [{key}] {question}")
        if hint:
            print(f"    hint: {hint}")
        ans = input("  > ").strip()
        answers[key] = ans
    return answers


def session_filename(subcommand: str, answers: dict[str, str]) -> str:
    today = _dt.date.today().isoformat()
    company = answers.get("company", "")
    if company:
        return f"{subcommand}-{slugify(company)}-{today}.json"
    return f"{subcommand}-{today}.json"


def save_session(
    subcommand: str,
    answers: dict[str, str],
    sessions_dir: Optional[Path] = None,
) -> Path:
    target_dir = sessions_dir or _SESSIONS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / session_filename(subcommand, answers)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "subcommand": subcommand,
        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "answers": answers,
        "answered_count": sum(1 for v in answers.values() if v),
        "total_prompts": len(answers),
    }

    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def print_summary(subcommand: str, answers: dict[str, str], saved_to: Path) -> None:
    answered = sum(1 for v in answers.values() if v)
    skipped = len(answers) - answered
    print()
    print("=" * 60)
    print(f"  {subcommand}: {answered} answered, {skipped} skipped")
    print(f"  Saved to: {saved_to}")
    print("=" * 60)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Structured elicitation harness for job-application artifacts."
    )
    parser.add_argument(
        "subcommand",
        choices=sorted(PROMPT_SETS.keys()),
        help="Which elicitation flow to run.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Skip interactive prompts (useful for tests). Saves an empty session.",
    )
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=None,
        help="Override the sessions directory (default: localonly/sessions/).",
    )
    args = parser.parse_args(argv)

    prompts = PROMPT_SETS[args.subcommand]

    if args.non_interactive:
        answers = {key: "" for key, _q, _h in prompts}
    else:
        print()
        print(f"Elicitation: {args.subcommand}")
        print(f"  {len(prompts)} prompts. Empty input skips a field.")
        try:
            answers = run_prompts(prompts)
        except (KeyboardInterrupt, EOFError):
            print("\n[aborted]", file=sys.stderr)
            return 130

    saved = save_session(args.subcommand, answers, args.sessions_dir)
    print_summary(args.subcommand, answers, saved)
    return 0


if __name__ == "__main__":
    sys.exit(main())
