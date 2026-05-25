"""Tests for corpofit.py: gate enforcement, band boundaries, arithmetic."""
import importlib.util
import sys
import unittest
from pathlib import Path


_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_SCRIPT = _REPO / "scripts" / "corpofit.py"

spec = importlib.util.spec_from_file_location("corpofit", _SCRIPT)
corpofit = importlib.util.module_from_spec(spec)
sys.modules["corpofit"] = corpofit
spec.loader.exec_module(corpofit)


def _full_internals(strength: str = "mid") -> dict[str, float]:
    if strength == "max":
        return {k: v for k, v in corpofit.DIM_MAX.items()}
    if strength == "min":
        return {k: 0.0 for k in corpofit.DIM_MAX}
    return {k: round(v * 0.80, 2) for k, v in corpofit.DIM_MAX.items()}


class GateLayerTests(unittest.TestCase):
    """Gate layer is the load-bearing enforcement; verify the mechanism."""

    def test_tier_9_blocks_at_gate_1_with_no_score_computed(self):
        result = corpofit.compute_fit(tier=9, **_full_internals("max"), comp=500_000)
        self.assertEqual(result.decision, "DO_NOT_APPLY")
        self.assertEqual(result.gate_blocked_at, "gate_1")
        self.assertIsNone(result.score_final)
        self.assertIsNone(result.c5_score)
        self.assertIsNone(result.internal_total)

    def test_tier_10_blocks_at_gate_1(self):
        result = corpofit.compute_fit(tier=10, **_full_internals("max"))
        self.assertEqual(result.decision, "DO_NOT_APPLY")
        self.assertEqual(result.gate_blocked_at, "gate_1")
        self.assertIsNone(result.score_final)

    def test_tier_7_with_comp_below_floor_blocks_at_gate_2(self):
        result = corpofit.compute_fit(
            tier=7, **_full_internals("max"), comp=150_000
        )
        self.assertEqual(result.decision, "DO_NOT_APPLY")
        self.assertEqual(result.gate_blocked_at, "gate_2")
        self.assertIsNone(result.score_final)
        self.assertEqual(result.comp, 150_000)
        self.assertEqual(result.comp_floor_used, 170_000)

    def test_tier_7_with_comp_at_or_above_floor_passes_gate_2(self):
        result = corpofit.compute_fit(
            tier=7, **_full_internals("mid"), comp=180_000
        )
        self.assertEqual(result.decision, "APPLY")
        self.assertIsNone(result.gate_blocked_at)
        # score_final must be a positive float in the expected band for
        # mid-internals at tier 7. Replaces weak assertIsNotNone.
        self.assertIsInstance(result.score_final, float)
        self.assertGreater(result.score_final, 0)
        self.assertAlmostEqual(
            result.score_final,
            result.c5_score + result.internal_total,
            places=1,
            msg="score_final must equal c5_score + internal_total",
        )
        # comp_floor_used must be exposed for the band display layer.
        self.assertEqual(result.comp_floor_used, 170_000)
        self.assertEqual(result.comp, 180_000)

    def test_no_comp_provided_skips_gate_2(self):
        result = corpofit.compute_fit(tier=5, **_full_internals("mid"))
        self.assertEqual(result.decision, "APPLY")
        self.assertIsNone(result.comp)
        self.assertIn("Gate 2 skipped",
                      " ".join(result.notes),
                      "must annotate that Gate 2 was skipped when comp absent")


class TierBandingTests(unittest.TestCase):
    """C5 banding numbers are exact and asymmetric by design."""

    def test_tier_1_c5_score_is_35(self):
        result = corpofit.compute_fit(tier=1, **_full_internals("min"), comp=100_000)
        self.assertEqual(result.c5_score, 35.0)

    def test_tier_5_c5_score_is_24(self):
        result = corpofit.compute_fit(tier=5, **_full_internals("min"), comp=145_000)
        self.assertEqual(result.c5_score, 24.0)

    def test_tier_8_c5_score_is_zero(self):
        result = corpofit.compute_fit(tier=8, **_full_internals("min"), comp=200_000)
        self.assertEqual(result.c5_score, 0.0)

    def test_asymmetric_gradient_magnitudes(self):
        t5 = corpofit.TIER_BANDING[5]
        t1_minus_t5 = corpofit.TIER_BANDING[1] - t5
        t5_minus_t8 = t5 - corpofit.TIER_BANDING[8]
        self.assertEqual(t1_minus_t5, 11.0)
        self.assertEqual(t5_minus_t8, 24.0)
        self.assertGreater(t5_minus_t8, t1_minus_t5,
                           "downside must be steeper than upside by design")


class WeightLayerTests(unittest.TestCase):
    """Combined score is bounded by construction."""

    def test_score_at_most_100_at_max_inputs(self):
        result = corpofit.compute_fit(tier=1, **_full_internals("max"), comp=100_000)
        self.assertLessEqual(result.score_final, 100.0)

    def test_score_at_least_zero_at_min_inputs(self):
        result = corpofit.compute_fit(tier=8, **_full_internals("min"), comp=200_000)
        self.assertGreaterEqual(result.score_final, 0.0)

    def test_score_sums_internals_and_c5_exactly(self):
        result = corpofit.compute_fit(
            tier=5, c1=10, c2=12, c3=11, c4=10, c6=7, c7=2, comp=150_000
        )
        self.assertEqual(result.c5_score, 24.0)
        self.assertEqual(result.internal_total, 52.0)
        self.assertEqual(result.score_final, 76.0)


class BandTests(unittest.TestCase):
    """Band boundaries are operationally meaningful; test the exact threshold."""

    def test_green_band_at_65_and_above(self):
        self.assertEqual(corpofit.band_for_score(75.0)[0], "GREEN")
        self.assertEqual(corpofit.band_for_score(65.0)[0], "GREEN")

    def test_yellow_green_band_at_50_to_64_99(self):
        self.assertEqual(corpofit.band_for_score(64.99)[0], "YELLOW-GREEN")
        self.assertEqual(corpofit.band_for_score(50.0)[0], "YELLOW-GREEN")

    def test_yellow_flag_band_at_40_to_49_99(self):
        self.assertEqual(corpofit.band_for_score(49.99)[0], "YELLOW-FLAG")
        self.assertEqual(corpofit.band_for_score(40.0)[0], "YELLOW-FLAG")

    def test_orange_band_at_30_to_39_99(self):
        self.assertEqual(corpofit.band_for_score(39.99)[0], "ORANGE")
        self.assertEqual(corpofit.band_for_score(30.0)[0], "ORANGE")

    def test_red_stop_band_below_30(self):
        self.assertEqual(corpofit.band_for_score(29.99)[0], "RED-STOP")
        self.assertEqual(corpofit.band_for_score(0.0)[0], "RED-STOP")


class InputValidationTests(unittest.TestCase):
    """Calculator refuses malformed inputs cleanly."""

    def test_tier_zero_raises_value_error(self):
        with self.assertRaises(ValueError):
            corpofit.compute_fit(tier=0, **_full_internals("min"))

    def test_tier_eleven_raises_value_error(self):
        with self.assertRaises(ValueError):
            corpofit.compute_fit(tier=11, **_full_internals("min"))

    def test_negative_internal_score_raises_value_error(self):
        scores = _full_internals("min")
        scores["c1"] = -1.0
        with self.assertRaises(ValueError):
            corpofit.compute_fit(tier=5, **scores)

    def test_over_max_internal_score_raises_value_error(self):
        scores = _full_internals("min")
        scores["c1"] = corpofit.DIM_MAX["c1"] + 0.1
        with self.assertRaises(ValueError):
            corpofit.compute_fit(tier=5, **scores)

    def test_non_int_tier_raises(self):
        with self.assertRaises(ValueError):
            corpofit.compute_fit(tier="five", **_full_internals("min"))


class CalibrationConstantsTests(unittest.TestCase):
    """Load-bearing constants must satisfy framework invariants."""

    def test_dim_max_sums_to_approximately_65(self):
        total = sum(corpofit.DIM_MAX.values())
        self.assertAlmostEqual(total, 64.9, places=1)

    def test_c5_max_plus_internals_max_equals_100(self):
        max_total = 35.0 + sum(corpofit.DIM_MAX.values())
        self.assertAlmostEqual(max_total, 99.9, places=1)

    def test_comp_floor_strictly_monotonic_by_tier(self):
        floors = corpofit.COMP_FLOOR_STARTER
        for tier in range(1, 8):
            self.assertLess(
                floors[tier], floors[tier + 1],
                f"comp floor not monotonic at tier {tier} -> {tier+1}"
            )

    def test_tier_banding_strictly_monotonic_descending(self):
        banding = corpofit.TIER_BANDING
        for tier in range(1, 8):
            self.assertGreater(
                banding[tier], banding[tier + 1],
                f"tier banding not monotonic descending at tier {tier} -> {tier+1}"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
