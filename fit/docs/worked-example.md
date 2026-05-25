# Worked example: classifying "Acme Corp"

This page walks through the full corpofit flow for a fictional company. The goal is to show the mechanics. The numbers are illustrative; do not transfer them to a real company without doing your own evidence-gathering.

## Setup

- **Target**: Acme Corp, a hypothetical company in "Sector X" (no real industry).
- **Role**: Senior individual contributor, hybrid 2-day-per-week office attendance.
- **Stage**: pre-application. We have the JD and basic Glassdoor reads; no screen scheduled yet.

## Step 1: Industry classification

Apply your own 1-10 ethics rubric. corpofit takes the tier as user-supplied input; the calculator doesn't ship a public rubric, so the judgment stays yours. The example below sketches one user's rubric walk for orientation; your own rubric will use whatever signals you decide are load-bearing.

- **Sector identification**: Acme operates in Sector X. We are looking at the core cash-flow source, not the marketing department's framing.
- **Tier baseline**: Sector X classifies at tier 4 under this user's rubric. Mixed net outcomes; conventional business model.
- **Company adjustments**: Acme has one transparency point (publishes annual stakeholder reports) and one negative (a 2024 layoff round was poorly communicated). Net adjustment under this rubric: 0 tiers.
- **Hard-block check**: Tier 9/10 criteria (categorical hard-block) are not present under this user's rubric.
- **Final tier**: 4.

C5 banding at tier 4 is 27.0 points.

## Step 2: Score the internal dimensions

Read `fit/docs/role-fit-dimensions.md` for the rubric. Each dimension gets a 0-to-max score based on the evidence available.

For Acme:

| Dim | Max | Score | Evidence |
|---|---|---|---|
| C1 | 12.7 | 10.0 | Glassdoor reviews mention "speak-up culture"; Blind threads are mixed but skew positive; one referral confirmed psych safety with caveats. |
| C2 | 14.1 | 11.5 | JD says "balance is real"; Glassdoor confirms; one Blind thread complained about a specific team. Net positive. |
| C3 | 14.1 | 9.0 | The named hiring manager has 3 years at Acme and a public communication trail. One direct report left after 8 months last year. Mid-positive. |
| C4 | 12.7 | 11.0 | Acme has 18 months of cash, recent contract wins, no recent layoffs. |
| C6 | 8.5 | 7.0 | Role description includes ownership of a service from design to launch. Good growth signal. |
| C7 | 2.8 | 2.0 | JD midpoint is $165k. That clears our fixed-cost margin comfortably. |

Internal total: 50.5 of 64.9 possible.

## Step 3: Combined score

Score_final = C5 (27.0) + internals (50.5) = 77.5.

Band: GREEN (>= 65).

Action: full tailoring. Apply confidently.

## Step 4: Gate 2 check

The JD midpoint is $165k. The tier-4 compensation floor in our calibration is $135k. $165k > $135k. Gate 2 passes.

## Step 5: Log the decision

```bash
./corpofit \
  --tier 4 \
  --c1 10 --c2 11.5 --c3 9 --c4 11 --c6 7 --c7 2 \
  --comp 165000 \
  --company "Acme Corp"
```

<!-- sdk-review F2: score log records use _revision, not "calibration hash" -->

The record lands in `fit/localonly/score_log.jsonl` with the `_revision` field so you can audit later.

## Step 6: Prep the application artifacts

Now that the decision is "apply", use the elicitation flow:

```bash
python3 fit/scripts/elicit.py cover-letter
```

The cover-letter flow prompts for company, role, hiring manager, source, why-this-company, why-now, specific-fit, and one risk-or-gap. Answers save under `fit/localonly/sessions/cover-letter-acme-corp-2026-05-17.json`. You can pull from this file when drafting in your editor.

For resume tailoring:

```bash
python3 fit/scripts/elicit.py resume
```

Walks through the JD's top three requirements, which experiences to foreground, which to demote, metric anchors, and a voice check.

## What this example does NOT show

- Tier 9 or 10 hard-block flow: the calculator short-circuits before scoring. See the `compute_fit` test cases for that behavior.
- Gate 2 trigger: if Acme's comp were $115k, Gate 2 would block at tier 4. The calculator returns DO_NOT_APPLY with `gate_blocked_at == "gate_2"`.
- Calibration override: if you copy a different profile to `fit/config/calibration.json`, the tier banding and comp floors shift accordingly. Same inputs, different decisions.

Each of these is covered by the unit tests in `fit/tests/`.
