"""Load and validate job-search profile YAML (no toren dependency)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "PyYAML is required: pip install pyyaml"
    ) from exc

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "config" / "search_profile.schema.json"
_REFERRAL_WARM_DELTA = -10
_REFERRAL_STRONG_DELTA = -20


def _schema() -> dict[str, Any]:
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _validate(data: dict[str, Any]) -> None:
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "jsonschema is required: pip install jsonschema"
        ) from exc
    jsonschema.validate(instance=data, schema=_schema())


def _expand_path(raw: str, profile_dir: Path) -> str:
    expanded = os.path.expanduser(raw)
    path = Path(expanded)
    if not path.is_absolute():
        path = (profile_dir / path).resolve()
    return str(path)


def load_profile(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load YAML profile, validate against schema, resolve relative paths."""
    profile_path = Path(path).expanduser().resolve()
    if not profile_path.is_file():
        raise FileNotFoundError(f"Profile not found: {profile_path}")

    with open(profile_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Profile root must be a mapping: {profile_path}")

    _validate(data)

    profile_dir = profile_path.parent
    data = dict(data)
    referrals = dict(data["referrals"])
    referrals["status_file"] = _expand_path(referrals["status_file"], profile_dir)
    data["referrals"] = referrals

    output = dict(data["output"])
    output["results_dir"] = _expand_path(output["results_dir"], profile_dir)
    data["output"] = output

    data["_meta"] = {
        "path": str(profile_path),
        "profile_dir": str(profile_dir),
    }
    return data


def remote_policy(profile: dict[str, Any]) -> dict[str, Any]:
    """Summarize work-mode rules for scraper/triage integration."""
    pref = profile["remote_preference"]
    return {
        "preference": pref,
        "requires_us_employee_remote": pref in {"fully_remote", "hybrid_home_metro"},
        "allows_hybrid_in_home_metro": pref == "hybrid_home_metro",
        "allows_any_us_remote_listing": pref == "any_us_remote",
    }


def allowed_hybrid_places(profile: dict[str, Any]) -> list[str]:
    """Place-name allowlist for hybrid/onsite when remote_preference allows home metro."""
    return list(profile["home_metro"]["place_names"])


def ils_floor(profile: dict[str, Any], referral_status: str = "cold") -> int:
    """Effective ILS skip floor for cold / warm / strong referral tier."""
    ils = profile["ils"]
    cold = int(ils["cold_floor"])
    warm_delta = int(ils.get("referral_warm_delta", _REFERRAL_WARM_DELTA))
    strong_delta = int(ils.get("referral_strong_delta", _REFERRAL_STRONG_DELTA))
    status = (referral_status or "cold").lower()
    if status == "strong":
        return max(0, cold + strong_delta)
    if status == "warm":
        return max(0, cold + warm_delta)
    return cold


def referral_path(profile: dict[str, Any]) -> str:
    """Absolute path to referral_status.txt."""
    return profile["referrals"]["status_file"]


def comp_min_ceiling(profile: dict[str, Any]) -> int:
    return int(profile["comp"]["min_ceiling_usd"])


def tier_floors(profile: dict[str, Any]) -> dict[int, int]:
    raw = profile["comp"].get("tier_floors") or {}
    return {int(k): int(v) for k, v in raw.items()}


def enabled_tracks(profile: dict[str, Any]) -> list[str]:
    return list(profile["tracks"]["enable"])


def results_dir(profile: dict[str, Any]) -> str:
    return profile["output"]["results_dir"]
