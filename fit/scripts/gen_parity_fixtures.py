#!/usr/bin/env python3
"""Generate parity fixtures for the Pages JS port of corpofit.compute_fit.

Each fixture pairs an input dict with the expected output produced by
the Python reference. The Pages parity harness loads docs/tests/parity.json
and asserts identical output from window.corpofit.scoreFit.

Run from anywhere; absolute paths are used.

Output:
    docs/tests/parity.json
"""
from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path

# Load corpofit by path (it's not a package).
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_SCRIPT = _REPO / "scripts" / "corpofit.py"

spec = importlib.util.spec_from_file_location("corpofit", _SCRIPT)
corpofit = importlib.util.module_from_spec(spec)
sys.modules["corpofit"] = corpofit
spec.loader.exec_module(corpofit)


def main() -> int:
    # Use the shipped starter calibration. The Pages app saves with
    # schema_version 1.1 but the canonical revision input doesn't
    # include schema_version, so this stays parity-equivalent.
    cal = corpofit.load_calibration(_REPO / "config" / "calibration.example.json")

    # Build an explicit list of cases. Each case is a tuple of
    # (name, kwargs-for-compute_fit). The Python output is captured
    # and exported alongside the input so the JS test can diff exactly.
    cases = [
        # --- Happy path, GREEN ---
        ("apply_green_tier1_full", dict(tier=1, c1=12.7, c2=14.1, c3=14.1, c4=12.7, c6=8.5, c7=2.8, comp=200_000)),
        ("apply_green_tier4_typical", dict(tier=4, c1=9.5, c2=11.2, c3=10.8, c4=9.0, c6=6.4, c7=2.1, comp=165_000)),

        # --- YELLOW-GREEN band (50-64) ---
        ("apply_yellow_green_tier3", dict(tier=3, c1=8.0, c2=8.0, c3=8.0, c4=8.0, c6=4.0, c7=1.5, comp=130_000)),

        # --- YELLOW-FLAG band (40-49) ---
        ("apply_yellow_flag_tier5", dict(tier=5, c1=6.0, c2=6.0, c3=6.0, c4=6.0, c6=4.0, c7=1.0, comp=150_000)),

        # --- ORANGE band (30-39) ---
        ("apply_orange_tier6", dict(tier=6, c1=4.0, c2=4.0, c3=4.0, c4=4.0, c6=3.0, c7=1.0, comp=165_000)),

        # --- RED-STOP band (<30) ---
        ("apply_red_stop_tier8", dict(tier=8, c1=2.0, c2=2.0, c3=2.0, c4=2.0, c6=1.0, c7=0.5, comp=200_000)),

        # --- Gate 1 hard-block: tier 9 ---
        ("gate1_tier9", dict(tier=9, c1=0, c2=0, c3=0, c4=0, c6=0, c7=0, comp=300_000)),

        # --- Gate 1 hard-block: tier 10 ---
        ("gate1_tier10", dict(tier=10, c1=0, c2=0, c3=0, c4=0, c6=0, c7=0, comp=500_000)),

        # --- Gate 2: comp below tier-4 floor ---
        ("gate2_tier4_lowcomp", dict(tier=4, c1=10, c2=12, c3=10, c4=10, c6=6, c7=2, comp=100_000)),

        # --- Gate 2: comp below tier-7 floor ---
        ("gate2_tier7_lowcomp", dict(tier=7, c1=10, c2=12, c3=10, c4=10, c6=6, c7=2, comp=150_000)),

        # --- No comp provided (Gate 2 skipped, note added) ---
        ("apply_no_comp_tier2", dict(tier=2, c1=10, c2=10, c3=10, c4=10, c6=6, c7=2)),

        # --- Boundary: tier 1, all zeros (still APPLY but RED-STOP) ---
        ("apply_all_zero_tier1", dict(tier=1, c1=0, c2=0, c3=0, c4=0, c6=0, c7=0, comp=100_000)),

        # --- Boundary: tier 8, max internals (band depends on tier banding=0) ---
        ("apply_tier8_max_internals", dict(tier=8, c1=12.7, c2=14.1, c3=14.1, c4=12.7, c6=8.5, c7=2.8, comp=200_000)),

        # --- Exact band boundaries ---
        ("band_boundary_score_65_exact", dict(tier=2, c1=11.0, c2=10.0, c3=11.0, c4=0, c6=0, c7=0, comp=120_000)),
        ("band_boundary_score_50_exact", dict(tier=4, c1=10.0, c2=8.0, c3=5.0, c4=0, c6=0, c7=0, comp=140_000)),
        ("band_boundary_score_40_exact", dict(tier=5, c1=6.0, c2=6.0, c3=4.0, c4=0, c6=0, c7=0, comp=150_000)),
        ("band_boundary_score_30_exact", dict(tier=6, c1=5.0, c2=5.0, c3=4.0, c4=0, c6=0, c7=0, comp=165_000)),

        # --- Boundary: comp exactly at the floor (passes Gate 2) ---
        ("gate2_comp_exactly_floor_tier3", dict(tier=3, c1=8, c2=8, c3=8, c4=8, c6=4, c7=1, comp=125_000)),

        # --- Realistic combinations ---
        ("realistic_strong_apply_tier2", dict(tier=2, c1=10.5, c2=12.0, c3=13.0, c4=11.0, c6=7.5, c7=2.5, comp=140_000)),
        ("realistic_marginal_apply_tier5", dict(tier=5, c1=7.5, c2=8.5, c3=8.0, c4=7.0, c6=5.0, c7=1.5, comp=160_000)),
        ("realistic_floor_close_call_tier4", dict(tier=4, c1=9.0, c2=11.0, c3=10.0, c4=9.0, c6=6.0, c7=2.0, comp=136_000)),
    ]

    fixtures = []
    for name, kwargs in cases:
        try:
            result = corpofit.compute_fit(calibration=cal, **kwargs)
            output = asdict(result)
        except Exception as e:
            output = {"_exception": type(e).__name__, "_message": str(e)}
        fixtures.append({"name": name, "input": kwargs, "expected": output})

    # Bundle the calibration alongside the fixtures so the JS test loads
    # the SAME calibration the Python used. We strip Python-only fields
    # that don't round-trip (source_path) and keep what the JS port reads.
    cal_for_js = {
        "schema_version": "1.1",
        "name": cal.name,
        "description": cal.description,
        "tier_banding": {str(k): v for k, v in sorted(cal.tier_banding.items())},
        "comp_floor_usd": {str(k): v for k, v in sorted(cal.comp_floor_usd.items())},
        "dim_max": {k: v for k, v in sorted(cal.dim_max.items())},
        # The python's `revision` is the canonical-hash without install_id.
        "revision": cal.revision,
        "install_id": cal.install_id,
    }

    out_dir = _REPO / "docs" / "tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "parity.json"
    out_path.write_text(json.dumps({
        "calibration": cal_for_js,
        "fixtures": fixtures,
        "_meta": {
            "python_version": sys.version.split()[0],
            "corpofit_revision": cal.revision,
            "fixture_count": len(fixtures),
        }
    }, indent=2) + "\n")

    print(f"Wrote {out_path} with {len(fixtures)} fixtures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
