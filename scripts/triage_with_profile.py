#!/usr/bin/env python3
"""
Thin triage wrapper: load search profile and invoke triage with profile-derived flags.

Lane 2 does not port triage_jobspy_csv.py (lane 3). This script:
  1. Loads JOB_SEARCH_PROFILE or --profile YAML
  2. Prints profile-derived settings
  3. Delegates to toren triage when present, else prints the env/CLI recipe

Usage:
  export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
  python3 scripts/triage_with_profile.py --latest

  python3 scripts/triage_with_profile.py --profile config/search_profile.example.yaml /path/to.csv

Lane 3 target (sisyphus-native):
  python3 scripts/triage_jobspy_csv.py --latest --profile "$JOB_SEARCH_PROFILE"
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_repo_root := _REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from lib.search_profile import (  # noqa: E402
    comp_min_ceiling,
    enabled_tracks,
    ils_floor,
    load_profile,
    referral_path,
    remote_policy,
    results_dir,
)

_TOREN_TRIAGE = Path.home() / "Projects" / "toren" / "scripts" / "triage_jobspy_csv.py"
_SISYPHUS_TRIAGE = _REPO_ROOT / "scripts" / "triage_jobspy_csv.py"


def _default_profile_path() -> str | None:
    env = os.environ.get("JOB_SEARCH_PROFILE")
    if env:
        return os.path.expanduser(env)
    local = _REPO_ROOT / "config" / "search_profile.local.yaml"
    if local.is_file():
        return str(local)
    return None


def _build_delegate_cmd(
    profile: dict,
    *,
    csv_path: str | None,
    latest: bool,
    out_path: str | None,
    triage_script: Path,
) -> list[str]:
    cmd = [sys.executable, str(triage_script)]
    if latest:
        cmd.append("--latest")
    elif csv_path:
        cmd.append(csv_path)
    cmd.extend(["--ils-floor", str(ils_floor(profile, "cold"))])
    if out_path:
        cmd.extend(["--out", out_path])
    return cmd


def _print_recipe(profile: dict, cmd: list[str]) -> None:
    policy = remote_policy(profile)
    print("Profile settings (lane 3 will read --profile directly):")
    print(f"  remote_preference: {policy['preference']}")
    print(f"  ils cold floor:    {ils_floor(profile, 'cold')}")
    print(f"  referral file:     {referral_path(profile)}")
    print(f"  comp min ceiling:  {comp_min_ceiling(profile)}")
    print(f"  tracks:            {', '.join(enabled_tracks(profile))}")
    print(f"  results_dir:       {results_dir(profile)}")
    print()
    print("Delegate command:")
    print("  " + " ".join(cmd))
    print()
    print("Or set env for a ported triage script:")
    print(f"  export JOB_SEARCH_PROFILE={profile['_meta']['path']}")
    print(f"  export TRIAGE_REFERRAL_STATUS={referral_path(profile)}")
    print(f"  export TRIAGE_ILS_FLOOR={ils_floor(profile, 'cold')}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "csv_path",
        nargs="?",
        help="Path to jobspy_results_YYYYMMDD.csv (optional with --latest)",
    )
    ap.add_argument("--profile", help="Profile YAML (default: JOB_SEARCH_PROFILE)")
    ap.add_argument("--latest", action="store_true", help="Use newest CSV in profile results_dir")
    ap.add_argument("--out", metavar="FILE", help="Write triage CSV path")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print delegate command only; do not run triage",
    )
    args = ap.parse_args()

    profile_path = args.profile or _default_profile_path()
    if not profile_path:
        ap.error("Pass --profile or set JOB_SEARCH_PROFILE")

    profile = load_profile(profile_path)
    os.environ["JOB_SEARCH_PROFILE"] = profile["_meta"]["path"]
    os.environ["TRIAGE_REFERRAL_STATUS"] = referral_path(profile)
    os.environ["TRIAGE_ILS_FLOOR"] = str(ils_floor(profile, "cold"))

    triage_script = _SISYPHUS_TRIAGE if _SISYPHUS_TRIAGE.is_file() else _TOREN_TRIAGE
    if not triage_script.is_file():
        _print_recipe(profile, ["python3", "scripts/triage_jobspy_csv.py", "..."])
        raise SystemExit(
            "No triage script found. Complete lane 3 or run toren triage manually."
        )

    cmd = _build_delegate_cmd(
        profile,
        csv_path=args.csv_path,
        latest=args.latest,
        out_path=args.out,
        triage_script=triage_script,
    )
    if triage_script.resolve() == _SISYPHUS_TRIAGE.resolve():
        cmd.extend(["--profile", profile["_meta"]["path"]])

    if args.dry_run:
        _print_recipe(profile, cmd)
        return

    print(f"Profile: {profile['_meta']['path']}")
    print(f"Triage:  {triage_script}")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
