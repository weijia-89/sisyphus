# Role-fit dimensions

corpofit scores opportunities across seven dimensions. The dimensions partition the question "is this role a good fit for me" into bounded, scorable components that combine into a single 0-100 score.

## The seven dimensions

| Dim | Name | Max | Description |
|---|---|---|---|
| C1 | Psychological safety | 12.7 | Whether you can speak up, disagree, fail visibly, and recover. Includes evidence from Glassdoor, Blind, network conversations. |
| C2 | WLB reliability | 14.1 | Whether work-life-balance signals are consistent across sources, not just stated in the JD. Includes off-hours norms, on-call burden, vacation actually-taken. |
| C3 | Direct manager | 14.1 | Quality and stability of the hiring manager. Includes tenure at company, public communication style, reports' retention pattern. |
| C4 | Job security | 12.7 | Likelihood the role and the team survive 18 months. Includes funding pattern, layoff history, business-unit health. |
| C5 | Industry classification | 35.0 | Tier-based score related to industry, relevant to your subject matter expertise. |
| C6 | Career growth | 8.5 | Whether the role advances your skill stack and resume. Includes scope, on-job learning, transferable signals. |
| C7 | Comp sustainability | 2.8 | Whether the comp covers your fixed costs with margin. Smallest dimension by design: comp is necessary, not sufficient. |

The numbers in the Max column sum to 99.9. C5 is 35.0 ceiling, internals are 64.9 ceiling. Combined score range is 0-100.

## Why these weights

Three premises behind the asymmetric weighting:

1. **Industry tier dominates** because durable career outcomes depend more on what business you're in than on local team conditions. A great team in a sunset industry burns out into worse-fit work; a mediocre team in a growing industry teaches you the field.
2. **Manager and WLB tie for second** because they are the day-to-day operational reality. They beat job security by a small margin because security is more legible upfront and easier to research.
3. **Comp is smallest** because comp is necessary (above the gate-2 floor) but not sufficient. A high-comp offer in a poor-fit setup does not pencil out over 3 years.

<!-- sdk-review F1: profiles only vary comp_floor_usd (Gate 2), not tier_banding/dim_max -->
The calibration profiles in `fit/config/profiles/` adjust **compensation floors only** (`comp_floor_usd`, Gate 2). All shipped profiles share identical `tier_banding` and internal dimension maxima (`dim_max`); only comp floors differ by household structure. Sole-earners with dependents get higher comp floors; dual-earner couples get lower ones reflecting shared fixed costs. Lane 2 may sync search-profile YAML separately via `config/profile_catalog.yaml`.

## How to score each dimension

Each dimension is scored 0 to its max in increments of 0.1. The rubric below applies:

- **Score 0**: clear evidence the dimension is broken or absent. (Hostile manager; off-hours expected; team about to be cut; etc.)
- **Score at 30 percent of max**: explicit negatives outweigh positives. Apply only if other dimensions compensate strongly.
- **Score at 50 percent of max**: neutral. No clear signal either way.
- **Score at 70 percent of max**: clear positives outweigh negatives. Standard "this looks good."
- **Score at 90 percent of max**: strong evidence from multiple independent sources. Glassdoor + Blind + network + JD all agree.
- **Score at max**: rare. Requires explicit author-controlled signals (e.g., you previously worked with this manager and know them directly).

When you can't find evidence either way, default to 50 percent of max. Document the uncertainty in the comp / manager / etc. note when reviewing your log.

## Banding

The combined score maps to one of five bands:

- **GREEN** (score >= 65): full tailoring. Apply confidently.
- **YELLOW-GREEN** (50-64): apply with screen narrative. Avoid heavy tailoring; the screen is the diligence gate.
- **YELLOW-FLAG** (40-49): apply, but treat the screen as a hard diligence gate. Have your "ask hard questions" list ready.
- **ORANGE** (30-39): cold-apply only. Flag risks; negotiate comp premium if an offer arrives.
- **RED-STOP** (< 30): do not apply. Internal score is too low to justify the application effort.

## Audit trail

<!-- sdk-review F2: log schema uses _revision since v0.2.0 -->

Every score is logged to `fit/localonly/score_log.jsonl` with the `_revision` field (calibration revision hash). If you change your calibration profile mid-search, you can replay old entries to see whether they would still pass under the new tuning.
