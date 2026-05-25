#!/usr/bin/env python3
"""corpofit.py: seven-dimension job-fit calculator with categorical gate
enforcement, JSON calibration support, and append-only local log.

The calculator enforces tier classification in code: you cannot compute
a fit score without first classifying the company on a 1-10 ethics tier.
corpofit treats the tier as user-supplied input; the rubric for assigning
it is yours, not the calculator's. There is no skip flag, no default value
for the tier argument.

Architecture:

    Gate Layer (categorical):
      Gate 1: tier in {9, 10}  -> DO_NOT_APPLY (hard block)
      Gate 2: comp < tier_floor -> DO_NOT_APPLY (comp-floor pre-gate)

    Weight Layer (continuous, 0-100):
      C5 (industry classification) = TIER_BANDING[tier]    (0-35 pts)
      Internals = C1 + C2 + C3 + C4 + C6 + C7   (0-65 pts)
      Score_final = C5 + internals  (0-100, bounded by construction)

Bands:
    Score >= 65   GREEN          full tailoring
    Score 50-64   YELLOW-GREEN   apply, no heavy tailoring
    Score 40-49   YELLOW-FLAG    apply, screen as diligence gate
    Score 30-39   ORANGE         cold-apply only
    Score < 30    RED-STOP       do not apply

Calibration: tunables load from `config/calibration.json` (user override)
or `config/calibration.example.json` (shipped default). Each log record
includes a `_revision` field (a short hash over the canonical
calibration JSON) so future-you can audit which tuning was active for
a given classification. The `_install_id` field, if present in the
loaded calibration JSON, is folded into the revision hash, which gives
the resulting record a per-install identifier; this is opt-in via
`corpofit --init` (default installs ship without an `_install_id`).

Privacy: the local log is append-only JSONL at `localonly/score_log.jsonl`.
Never leaves the machine. The `localonly/` directory is gitignored.
Pass `--no-log` to disable. Pass `--company` to label the record.

Stdlib only. No network, no telemetry, no PII collection.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import secrets
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional


_SCRIPT = Path(__file__).resolve()
_REPO_ROOT = _SCRIPT.parent.parent
_CONFIG_DIR = _REPO_ROOT / "config"
_USER_CONFIG = _CONFIG_DIR / "calibration.json"
_EXAMPLE_CONFIG = _CONFIG_DIR / "calibration.example.json"
_PROFILES_DIR = _CONFIG_DIR / "profiles"
_LOG_DIR = _REPO_ROOT / "localonly"
_LOG_PATH = _LOG_DIR / "score_log.jsonl"


_FALLBACK_TIER_BANDING: dict[int, float] = {
    1: 35.0, 2: 33.0, 3: 30.0, 4: 27.0, 5: 24.0, 6: 16.0, 7: 8.0, 8: 0.0,
}
_FALLBACK_COMP_FLOOR: dict[int, int] = {
    1: 95_000, 2: 110_000, 3: 125_000, 4: 135_000,
    5: 145_000, 6: 160_000, 7: 170_000, 8: 185_000,
}
_FALLBACK_DIM_MAX: dict[str, float] = {
    "c1": 12.7, "c2": 14.1, "c3": 14.1,
    "c4": 12.7, "c6":  8.5, "c7":  2.8,
}

HARD_BLOCK_REASONS: dict[int, str] = {
    9:  "Tier 9: categorical hard-block. The 1-10 ethics tier is the caller's "
        "own classification; tiers 9 and 10 are reserved by convention for "
        "hard-block categories and are not score-eligible.",
    10: "Tier 10: categorical hard-block, same as tier 9 plus active criminal "
        "or prosecutorial pattern. Not score-eligible.",
}


@dataclass
class Calibration:
    """Parsed calibration with a computed revision hash for the audit trail.

    `revision` is the first 8 chars of SHA256 over the canonical JSON
    encoding of the three core dicts. When `install_id` is set (opt-in
    via `corpofit --init`), it is folded into the canonical input so
    that two clones with identical tunables but different install IDs
    produce different revision strings.
    """
    name: str
    description: str
    tier_banding: dict[int, float]
    comp_floor_usd: dict[int, int]
    dim_max: dict[str, float]
    source_path: Optional[str] = None
    install_id: Optional[str] = None
    revision: str = ""

    def __post_init__(self) -> None:
        if not self.revision:
            payload: dict[str, object] = {
                "tier_banding": {str(k): v for k, v in sorted(self.tier_banding.items())},
                "comp_floor_usd": {str(k): v for k, v in sorted(self.comp_floor_usd.items())},
                "dim_max": {k: v for k, v in sorted(self.dim_max.items())},
            }
            if self.install_id is not None:
                payload["_install_id"] = self.install_id
            canonical = json.dumps(payload, separators=(",", ":"), sort_keys=False)
            self.revision = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]


def _load_fallback() -> Calibration:
    return Calibration(
        name="fallback-hardcoded",
        description="In-script defaults; config/calibration.example.json missing.",
        tier_banding=dict(_FALLBACK_TIER_BANDING),
        comp_floor_usd=dict(_FALLBACK_COMP_FLOOR),
        dim_max=dict(_FALLBACK_DIM_MAX),
        source_path=None,
    )


_INSTALL_ID_RE = re.compile(r"^[0-9a-f]{8}$")


def _validate_install_id(value: object, source: Optional[str]) -> Optional[str]:
    """Validate an optional `_install_id` value from a calibration JSON.

    `None` / missing is allowed (default ungrandfathered installs). When
    present, it must be a lowercase 8-char hex string. Any other shape
    is a hard error; we never silently coerce, because the field is
    meant to be stable across runs.
    """
    if value is None:
        return None
    if not isinstance(value, str) or not _INSTALL_ID_RE.match(value):
        raise ValueError(
            f"Invalid `_install_id` in calibration ({source or 'unknown'}): "
            f"got {value!r}. Expected an 8-char lowercase hex string "
            "(e.g. \"f3a2c891\"). Run `corpofit --init` to generate one."
        )
    return value


def _parse_calibration_dict(data: dict, source: Optional[str] = None) -> Calibration:
    """Validate and parse a calibration dict (typically from JSON)."""
    try:
        tier_banding = {int(k): float(v) for k, v in data["tier_banding"].items()}
        comp_floor = {int(k): int(v) for k, v in data["comp_floor_usd"].items()}
        dim_max = {str(k): float(v) for k, v in data["dim_max"].items()}
    except (KeyError, ValueError, TypeError) as e:
        raise ValueError(
            f"Invalid calibration shape ({source or 'unknown'}): {e}. "
            "Expected keys: tier_banding (int->float), comp_floor_usd "
            "(int->int), dim_max (str->float)."
        ) from e

    install_id = _validate_install_id(data.get("_install_id"), source)

    required_tiers = set(range(1, 9))
    if set(tier_banding.keys()) != required_tiers:
        raise ValueError(
            f"tier_banding keys must be exactly {sorted(required_tiers)}; "
            f"got {sorted(tier_banding.keys())}."
        )
    if set(comp_floor.keys()) != required_tiers:
        raise ValueError(
            f"comp_floor_usd keys must be exactly {sorted(required_tiers)}; "
            f"got {sorted(comp_floor.keys())}."
        )
    required_dims = {"c1", "c2", "c3", "c4", "c6", "c7"}
    if set(dim_max.keys()) != required_dims:
        raise ValueError(
            f"dim_max keys must be exactly {sorted(required_dims)}; "
            f"got {sorted(dim_max.keys())}."
        )

    for tier in range(1, 8):
        if comp_floor[tier] >= comp_floor[tier + 1]:
            raise ValueError(
                f"comp_floor_usd must be monotonically increasing by tier; "
                f"got floor[{tier}]={comp_floor[tier]} >= "
                f"floor[{tier+1}]={comp_floor[tier+1]}."
            )

    # tier_banding must be monotonically NON-INCREASING by tier (higher
    # tier = lower banding score, mirroring the comp_floor monotonic
    # check). Catches inverted or randomized calibrations that would flip
    # the scoring direction. Allows ties (e.g. tier 7 and 8 both at the
    # ceiling for the band is permissible).
    for tier in range(1, 8):
        if tier_banding[tier] < tier_banding[tier + 1]:
            raise ValueError(
                f"tier_banding must be monotonically non-increasing by tier "
                f"(higher tier = lower or equal score); got "
                f"banding[{tier}]={tier_banding[tier]} < "
                f"banding[{tier+1}]={tier_banding[tier+1]}."
            )

    return Calibration(
        name=data.get("name", "unnamed"),
        description=data.get("description", ""),
        tier_banding=tier_banding,
        comp_floor_usd=comp_floor,
        install_id=install_id,
        dim_max=dim_max,
        source_path=source,
    )


def load_calibration(explicit_path: Optional[Path] = None) -> Calibration:
    """Load calibration with fallback chain.

    Priority order:
      1. Explicit --config path if provided.
      2. config/calibration.json (user override, gitignored).
      3. config/calibration.example.json (shipped default).
      4. In-script fallback constants.
    """
    candidates: list[Path] = []
    if explicit_path is not None:
        candidates.append(explicit_path)
    candidates.extend([_USER_CONFIG, _EXAMPLE_CONFIG])

    for path in candidates:
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return _parse_calibration_dict(data, source=str(path))
        except json.JSONDecodeError as e:
            raise ValueError(f"Calibration file {path} has invalid JSON: {e}") from e

    return _load_fallback()


_CALIBRATION = load_calibration()
TIER_BANDING: dict[int, float] = _CALIBRATION.tier_banding
COMP_FLOOR_STARTER: dict[int, int] = _CALIBRATION.comp_floor_usd
DIM_MAX: dict[str, float] = _CALIBRATION.dim_max


@dataclass
class FitResult:
    decision: str
    tier: int
    gate_blocked_at: Optional[str]
    block_reason: Optional[str]
    c5_score: Optional[float]
    internal_scores: Optional[dict[str, float]]
    internal_total: Optional[float]
    score_final: Optional[float]
    band: Optional[str]
    band_action: Optional[str]
    comp: Optional[int]
    comp_floor_used: Optional[int]
    revision: Optional[str]
    calibration_name: Optional[str]
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def band_for_score(score: float) -> tuple[str, str]:
    """Return (band_name, recommended_action) for a score in [0, 100]."""
    if score >= 65:
        return "GREEN", "Full tailoring. Apply confidently."
    if score >= 50:
        return "YELLOW-GREEN", "Apply with screen narrative. No heavy tailoring."
    if score >= 40:
        return "YELLOW-FLAG", "Apply. Treat screen as diligence gate; ask hard questions."
    if score >= 30:
        return "ORANGE", "Cold apply only. Flag risks; negotiate comp premium if offer arrives."
    return "RED-STOP", "Do not apply. Internal score is too low to justify."


def compute_fit(
    tier: int,
    c1: float, c2: float, c3: float, c4: float, c6: float, c7: float,
    comp: Optional[int] = None,
    calibration: Optional[Calibration] = None,
) -> FitResult:
    """Compute a fit score with mandatory gate-layer checks.

    Args:
        tier:    Required. Integer 1-10 per the caller's own ethics rubric.
                 No default. Caller MUST classify before calling.
        c1..c7:  Internal-dim scores (0 to calibration.dim_max[dim]).
        comp:    Optional comp figure. Triggers Gate 2 when provided.
        calibration: Optional Calibration instance. Falls back to the
                     module-loaded calibration if None.

    Returns:
        FitResult with decision, scoring, diagnostic notes.

    Raises:
        ValueError: if tier is not 1-10, or any internal score is out of range.
    """
    if calibration is None:
        calibration = _CALIBRATION
    tier_banding = calibration.tier_banding
    comp_floor = calibration.comp_floor_usd
    dim_max = calibration.dim_max
    notes: list[str] = []

    if not isinstance(tier, int) or tier < 1 or tier > 10:
        raise ValueError(
            f"tier must be integer 1-10 (got {tier!r}). "
            "Classify the company on your own 1-10 ethics rubric "
            "before invoking this calculator."
        )
    internals = {"c1": c1, "c2": c2, "c3": c3, "c4": c4, "c6": c6, "c7": c7}
    for name, value in internals.items():
        max_pts = dim_max[name]
        if value < 0 or value > max_pts:
            raise ValueError(
                f"{name} must be in [0, {max_pts}] (got {value}). "
                f"See docs/role-fit-dimensions.md for the rubric."
            )

    if tier in (9, 10):
        reason = HARD_BLOCK_REASONS[tier]
        notes.append(f"Gate 1 triggered: tier {tier} is a categorical hard-block.")
        notes.append("No compensation premium overrides this. No score computed.")
        notes.append("Hard-block tiers are not score-eligible by design.")
        return FitResult(
            decision="DO_NOT_APPLY",
            tier=tier,
            gate_blocked_at="gate_1",
            block_reason=reason,
            c5_score=None,
            internal_scores=None,
            internal_total=None,
            score_final=None,
            band=None,
            band_action=None,
            comp=comp,
            comp_floor_used=None,
            revision=calibration.revision,
            calibration_name=calibration.name,
            notes=notes,
        )

    tier_floor = comp_floor.get(tier)
    if comp is not None and tier_floor is not None and comp < tier_floor:
        notes.append(
            f"Gate 2 triggered: comp ${comp:,} < tier-{tier} floor ${tier_floor:,}."
        )
        notes.append(
            "Higher tier numbers require higher comp floors. "
            "If this is a starter-value mismatch, recalibrate comp_floor."
        )
        return FitResult(
            decision="DO_NOT_APPLY",
            tier=tier,
            gate_blocked_at="gate_2",
            block_reason=f"comp ${comp:,} below tier-{tier} floor ${tier_floor:,}",
            c5_score=None,
            internal_scores=None,
            internal_total=None,
            score_final=None,
            band=None,
            band_action=None,
            comp=comp,
            comp_floor_used=tier_floor,
            revision=calibration.revision,
            calibration_name=calibration.name,
            notes=notes,
        )

    c5_score = tier_banding[tier]
    internal_total = sum(internals.values())
    score_final = c5_score + internal_total
    band, action = band_for_score(score_final)

    if comp is None:
        notes.append(
            "comp not provided; Gate 2 skipped. Provide --comp at pre-offer "
            "stage or at offer stage for full gate-layer check."
        )

    return FitResult(
        decision="APPLY",
        tier=tier,
        gate_blocked_at=None,
        block_reason=None,
        c5_score=c5_score,
        internal_scores=internals,
        internal_total=round(internal_total, 2),
        score_final=round(score_final, 2),
        band=band,
        band_action=action,
        comp=comp,
        comp_floor_used=tier_floor,
        revision=calibration.revision,
        calibration_name=calibration.name,
        notes=notes,
    )


def log_score_record(
    result: FitResult,
    company: str,
    log_path: Optional[Path] = None,
) -> Path:
    """Append a classification record to the local-only JSONL log.

    Privacy: this file stays local. Never network-egress. Contains the
    company name and your classification. The repo `.gitignore` excludes
    `localonly/`.
    """
    if not company or not company.strip():
        raise ValueError("company is required for logging; pass --company or --no-log")

    path = log_path or _LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "schema_version": "1.1",
        "company": company.strip(),
        "tier": result.tier,
        "decision": result.decision,
        "gate_blocked_at": result.gate_blocked_at,
        "c5_score": result.c5_score,
        "internal_total": result.internal_total,
        "score_final": result.score_final,
        "band": result.band,
        "comp": result.comp,
        "comp_floor_used": result.comp_floor_used,
        "_revision": result.revision,
        "calibration_name": result.calibration_name,
        "outcome": None,
        "notes_count": len(result.notes),
    }

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")
    return path


def _print_human(result: FitResult, log_target: Optional[Path] = None) -> None:
    print("=" * 72)
    print(f"corpofit result: tier {result.tier}, decision: {result.decision}")
    print("=" * 72)
    if result.decision == "DO_NOT_APPLY":
        print(f"  blocked at: {result.gate_blocked_at}")
        print(f"  reason: {result.block_reason}")
    else:
        print(f"  C5 (industry classification, /35): {result.c5_score:>6.2f}")
        print(f"  Internals (/65):                   {result.internal_total:>6.2f}")
        print("    " + "  ".join(
            f"{k.upper()}={v:.1f}" for k, v in (result.internal_scores or {}).items()
        ))
        print(f"  ----------------------------------")
        print(f"  Score_final (/100):                {result.score_final:>6.2f}")
        print(f"  Band:                              {result.band}")
        print(f"  Action:                            {result.band_action}")
        if result.comp is not None and result.comp_floor_used is not None:
            print(f"  Comp check: ${result.comp:,} >= ${result.comp_floor_used:,} "
                  f"(tier-{result.tier} floor)")
    print(f"  Calibration: {result.calibration_name} (revision {result.revision})")
    if log_target:
        print(f"  Logged to: {log_target}")
    if result.notes:
        print()
        print("Notes:")
        for n in result.notes:
            print(f"  - {n}")
    print()


def _interactive(calibration: Calibration) -> tuple[FitResult, str]:
    print()
    print("Interactive corpofit calculator. Tier classification is required.")
    print()
    print("Step 0: Company name (for the local log).")
    company = input("  Company: ").strip()
    if not company:
        company = "(unnamed)"

    print()
    print("Step 1: Industry-classification tier (1-10).")
    print("Apply your own ethics rubric; corpofit takes the tier as your input.")
    print()
    while True:
        try:
            tier = int(input("  Tier (1-10): ").strip())
            if 1 <= tier <= 10:
                break
            print("  Must be 1-10.")
        except ValueError:
            print("  Must be an integer.")

    if tier in (9, 10):
        print()
        print(f"  Tier {tier} is a categorical hard-block. No further input needed.")
        return compute_fit(tier, 0, 0, 0, 0, 0, 0, calibration=calibration), company

    print()
    print("Step 2: Internal dimensions. Score each per docs/role-fit-dimensions.md.")
    print("Rubric anchors (apply to every dimension):")
    print("  0       broken or actively hostile")
    print("  ~30%    explicit negatives outweigh positives")
    print("  ~50%    neutral / no clear signal (default when uncertain)")
    print("  ~70%    clear positives outweigh negatives")
    print("  ~90%    strong evidence from multiple independent sources")
    print("  max     rare; requires author-controlled signal")
    print()
    _DIM_LABEL = {
        "c1": "Psych safety",
        "c2": "WLB reliability",
        "c3": "Direct manager",
        "c4": "Job security",
        "c6": "Career growth",
        "c7": "Comp sustainability",
    }
    inputs: dict[str, float] = {}
    for dim in ("c1", "c2", "c3", "c4", "c6", "c7"):
        max_pts = calibration.dim_max[dim]
        label = _DIM_LABEL[dim]
        while True:
            try:
                v = float(input(
                    f"  {dim.upper()} {label} (0-{max_pts}): "
                ).strip())
                if 0 <= v <= max_pts:
                    inputs[dim] = v
                    break
                print(f"  Must be in [0, {max_pts}].")
            except ValueError:
                print("  Must be a number.")

    print()
    raw = input("Step 3 (optional): comp midpoint or offer $ (blank to skip): ").strip()
    comp = int(raw.replace(",", "").replace("$", "")) if raw else None

    return compute_fit(tier, calibration=calibration, comp=comp, **inputs), company


def _generate_install_id() -> str:
    """Generate a fresh 8-char lowercase hex `_install_id` via `secrets.token_hex`.

    Factored out so tests can monkeypatch it. `secrets.token_hex(4)`
    returns 8 hex chars from `os.urandom`, which satisfies our
    `_INSTALL_ID_RE` constraint.
    """
    return secrets.token_hex(4)


def init_user_calibration(
    example_path: Optional[Path] = None,
    user_path: Optional[Path] = None,
    id_generator=None,
) -> Path:
    """Bootstrap the user-override calibration from the shipped example,
    injecting a fresh 8-char hex `_install_id`.

    Opt-in. Default installs ship without an `_install_id` and therefore
    produce a `_revision` that is identical across clones with the same
    tunables (i.e. no per-clone watermark). Running this function once
    creates `config/calibration.json` with a unique `_install_id` so
    that subsequent score records carry a per-install `_revision`.

    Raises:
        FileExistsError: if the user-override file already exists.
            Refuses to overwrite, because that would silently change the
            install_id and break audit-log continuity.
        FileNotFoundError: if the example calibration is missing.
        ValueError: if the example calibration cannot be parsed (the
            file exists but is malformed).
    """
    example_path = example_path or _EXAMPLE_CONFIG
    user_path = user_path or _USER_CONFIG
    if user_path.exists():
        raise FileExistsError(
            f"{user_path} already exists. Refusing to overwrite. "
            "Delete it manually if you want a fresh install_id."
        )
    if not example_path.is_file():
        raise FileNotFoundError(
            f"Shipped example calibration not found at {example_path}. "
            "Cannot bootstrap."
        )
    with example_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # Validate the example before we copy it forward, so we don't write
    # a known-bad user file.
    _parse_calibration_dict(data, source=str(example_path))
    install_id = (id_generator or _generate_install_id)()
    if not _INSTALL_ID_RE.match(install_id):
        # Shouldn't happen with the default generator; protects against
        # a misbehaving custom generator passed in by a caller.
        raise ValueError(
            f"id_generator produced invalid install_id {install_id!r}; "
            "expected 8-char lowercase hex."
        )
    data["_install_id"] = install_id
    user_path.parent.mkdir(parents=True, exist_ok=True)
    with user_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=False)
        f.write("\n")
    return user_path


def _pick_profile_interactive(profiles_dir: Optional[Path] = None) -> Optional[Path]:
    """Interactive profile picker for --interactive mode.

    Lists every JSON profile in config/profiles/ sorted by filename, prompts
    the user to pick one, and returns its Path. Returns None if the user
    presses Enter (shipped default), if the directory is missing or empty,
    or if every profile in the directory fails to parse.

    Profiles that fail to parse are skipped with a warning line; the picker
    continues with the remaining valid ones. The function never raises on
    profile-parse failure (the picker degrades to "shipped default" rather
    than aborting the interactive flow).

    Args:
        profiles_dir: Optional override of the profiles directory. Defaults
            to the module-level _PROFILES_DIR. Intended for testing.
    """
    directory = profiles_dir if profiles_dir is not None else _PROFILES_DIR
    if not directory.is_dir():
        print("  (no profiles available; using shipped default)")
        return None
    candidates = sorted(directory.glob("*.json"))
    if not candidates:
        print("  (no profiles available; using shipped default)")
        return None

    valid: list[tuple[Path, str, str]] = []
    for path in candidates:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            name = str(data.get("name") or path.stem)
            description = str(data.get("description") or "(no description)")
        except (json.JSONDecodeError, OSError) as e:
            print(f"  (skipping {path.name}: {e})", file=sys.stderr)
            continue
        # Truncate the description to its first sentence so the menu stays
        # readable. Profiles ship multi-sentence descriptions; the first
        # sentence carries the differentiating context.
        idx = description.find(". ")
        short = description if idx == -1 else description[:idx + 1]
        valid.append((path, name, short))

    if not valid:
        print("  (no profiles available; using shipped default)")
        return None

    print()
    print("Calibration profile (optional).")
    for idx, (_, name, short) in enumerate(valid, start=1):
        print(f"  {idx}. {name} - {short}")
    print()
    while True:
        raw = input(
            f"  Pick a profile (1-{len(valid)}), or press Enter to use the shipped default: "
        ).strip()
        if raw == "":
            return None
        try:
            choice = int(raw)
        except ValueError:
            print(f"  Must be 1-{len(valid)} or Enter.")
            continue
        if 1 <= choice <= len(valid):
            return valid[choice - 1][0]
        print(f"  Must be 1-{len(valid)} or Enter.")


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Compute a multi-dimensional job-fit score.",
        epilog="Classify the tier on your own 1-10 ethics rubric before "
               "invoking this calculator. There is no skip flag.",
    )
    p.add_argument("--tier", type=int,
                   help="Industry-classification tier 1-10 (your own rubric). "
                        "Required unless --interactive.")
    # Each internal dimension accepts both a mnemonic long form and the
    # original `--cN` short form. The two are aliases sharing one dest;
    # existing scripts that use `--c1` keep working unchanged.
    p.add_argument("--c1", "--psych-safety", dest="c1", type=float,
                   help="C1 Psych safety (0-12.7)")
    p.add_argument("--c2", "--wlb", dest="c2", type=float,
                   help="C2 WLB reliability (0-14.1)")
    p.add_argument("--c3", "--manager", dest="c3", type=float,
                   help="C3 Direct manager (0-14.1)")
    p.add_argument("--c4", "--security", dest="c4", type=float,
                   help="C4 Job security (0-12.7)")
    p.add_argument("--c6", "--growth", dest="c6", type=float,
                   help="C6 Career growth (0-8.5)")
    p.add_argument("--c7", "--comp-sustain", dest="c7", type=float,
                   help="C7 Comp sustainability (0-2.8)")
    p.add_argument("--comp", type=int,
                   help="Comp midpoint (pre-offer) or offer amount, USD.")
    p.add_argument("--company", type=str,
                   help="Company identifier for the local log (required unless --no-log).")
    p.add_argument("--config", type=Path,
                   help="Path to a calibration JSON file.")
    p.add_argument("--no-log", action="store_true",
                   help="Skip the local log append.")
    p.add_argument("--interactive", action="store_true",
                   help="Walk through inputs verbally.")
    p.add_argument("--json", action="store_true",
                   help="Emit result as JSON instead of human-readable text.")
    p.add_argument("--init", action="store_true",
                   help="Bootstrap config/calibration.json from the shipped "
                        "example with a fresh _install_id. Opt-in; default "
                        "installs ship without one. Re-running --init refuses "
                        "to overwrite an existing user-override file.")
    args = p.parse_args(argv)

    if args.init:
        try:
            written = init_user_calibration()
        except FileExistsError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        except (OSError, ValueError) as e:
            print(f"ERROR initializing calibration: {e}", file=sys.stderr)
            return 2
        print(f"Wrote {written}")
        print(
            "An `_install_id` was added. Future score records will carry a "
            "matching `_revision`. To revert, delete the file."
        )
        return 0

    # Profile picker: only fires under --interactive AND no explicit
    # --config. An explicit --config always wins; non-interactive mode
    # never prompts. SIGINT / EOF at the picker prompt produce the same
    # [aborted] + exit-130 contract as a Ctrl-C inside _interactive.
    if args.interactive and args.config is None:
        try:
            chosen = _pick_profile_interactive()
        except (KeyboardInterrupt, EOFError):
            print("\n[aborted]", file=sys.stderr)
            return 130
        if chosen is not None:
            args.config = chosen

    try:
        calibration = load_calibration(args.config)
    except ValueError as e:
        print(f"ERROR loading calibration: {e}", file=sys.stderr)
        return 2

    global TIER_BANDING, COMP_FLOOR_STARTER, DIM_MAX, _CALIBRATION
    _CALIBRATION = calibration
    TIER_BANDING = calibration.tier_banding
    COMP_FLOOR_STARTER = calibration.comp_floor_usd
    DIM_MAX = calibration.dim_max

    if args.interactive:
        try:
            result, company = _interactive(calibration)
        except (KeyboardInterrupt, EOFError):
            print("\n[aborted]", file=sys.stderr)
            return 130
    else:
        if args.tier is None:
            p.error(
                "--tier is required. Classify the company on your own "
                "1-10 ethics rubric before invoking. "
                "Use --interactive for the questionnaire."
            )
        internals = {}
        for dim in ("c1", "c2", "c3", "c4", "c6", "c7"):
            v = getattr(args, dim)
            if v is None:
                if args.tier in (9, 10):
                    v = 0.0
                else:
                    p.error(
                        f"--{dim} is required (unless --tier in {{9, 10}}, "
                        f"which hard-blocks). See docs/role-fit-dimensions.md "
                        f"for the rubric."
                    )
            internals[dim] = v
        try:
            result = compute_fit(
                args.tier, calibration=calibration, comp=args.comp, **internals
            )
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        company = args.company or ""

    log_target: Optional[Path] = None
    if not args.no_log:
        if not company.strip():
            print("ERROR: --company is required for logging. Pass --company \"...\" "
                  "or pass --no-log to skip persistence.", file=sys.stderr)
            return 2
        try:
            log_target = log_score_record(result, company)
        except OSError as e:
            print(f"WARN: log append failed ({e}); result not persisted.", file=sys.stderr)

    if args.json:
        print(result.to_json())
    else:
        _print_human(result, log_target=log_target)

    if result.decision == "DO_NOT_APPLY":
        return 3 if result.gate_blocked_at == "gate_2" else 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
