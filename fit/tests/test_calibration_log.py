"""Tests for calibration loading and score-log persistence in corpofit."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_SCRIPT = _REPO / "scripts" / "corpofit.py"

spec = importlib.util.spec_from_file_location("corpofit", _SCRIPT)
corpofit = importlib.util.module_from_spec(spec)
sys.modules["corpofit"] = corpofit
spec.loader.exec_module(corpofit)


class CalibrationLoadingTests(unittest.TestCase):
    def test_default_load_returns_shipped_starter(self):
        cal = corpofit.load_calibration()
        self.assertIn(cal.name, {"starter-2026", "fallback-hardcoded"})
        if cal.source_path:
            self.assertIn("calibration.example.json", cal.source_path)
        self.assertEqual(len(cal.revision), 8)

    def test_explicit_config_path_takes_priority(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({
                "name": "test-custom",
                "description": "for unit test",
                "tier_banding": {str(k): 35.0 - (k - 1) * 4 for k in range(1, 9)},
                "comp_floor_usd": {str(k): 50_000 + k * 5_000 for k in range(1, 9)},
                "dim_max": {"c1": 10.0, "c2": 10.0, "c3": 10.0,
                            "c4": 10.0, "c6": 10.0, "c7": 10.0},
            }, f)
            tmp_path = Path(f.name)
        try:
            cal = corpofit.load_calibration(tmp_path)
            self.assertEqual(cal.name, "test-custom")
            self.assertEqual(cal.comp_floor_usd[5], 75_000)
        finally:
            tmp_path.unlink()

    def test_revision_stable_across_loads_of_same_file(self):
        cal1 = corpofit.load_calibration()
        cal2 = corpofit.load_calibration()
        self.assertEqual(cal1.revision, cal2.revision)

    def test_revision_changes_with_different_calibration(self):
        cal_default = corpofit.load_calibration()
        cal_alt = corpofit.Calibration(
            name="alt", description="",
            tier_banding={k: 30.0 for k in range(1, 9)},
            comp_floor_usd={k: 100_000 + k * 1_000 for k in range(1, 9)},
            dim_max={"c1": 10.0, "c2": 10.0, "c3": 10.0,
                     "c4": 10.0, "c6": 10.0, "c7": 10.0},
        )
        self.assertNotEqual(cal_default.revision, cal_alt.revision)

    def test_rejects_non_monotonic_comp_floor(self):
        bad = {
            "name": "bad",
            "description": "non-monotonic floor",
            "tier_banding": {str(k): 35.0 - (k - 1) * 4 for k in range(1, 9)},
            "comp_floor_usd": {
                "1": 100_000, "2": 200_000, "3": 100_000,
                "4": 100_000, "5": 100_000, "6": 100_000,
                "7": 100_000, "8": 100_000,
            },
            "dim_max": {"c1": 10.0, "c2": 10.0, "c3": 10.0,
                        "c4": 10.0, "c6": 10.0, "c7": 10.0},
        }
        with self.assertRaises(ValueError) as ctx:
            corpofit._parse_calibration_dict(bad)
        self.assertIn("monotonically", str(ctx.exception))

    def test_rejects_non_monotonic_tier_banding(self):
        # Inverted banding (low tier scores LESS than high tier) must be
        # rejected. Mirrors the comp_floor monotonic check. Adversarial
        # finding 2026-05-17: without this check, a calibration attack
        # could flip scoring direction.
        bad = {
            "name": "bad",
            "description": "inverted banding",
            "tier_banding": {str(k): float(k * 10) for k in range(1, 9)},
            "comp_floor_usd": {str(k): 50_000 + k * 5_000 for k in range(1, 9)},
            "dim_max": {"c1": 10.0, "c2": 10.0, "c3": 10.0,
                        "c4": 10.0, "c6": 10.0, "c7": 10.0},
        }
        with self.assertRaises(ValueError) as ctx:
            corpofit._parse_calibration_dict(bad)
        self.assertIn("tier_banding must be monotonically", str(ctx.exception))

    def test_accepts_monotonic_non_increasing_banding_with_ties(self):
        # Equality between adjacent tiers IS allowed (banding can plateau).
        ok = {
            "name": "ok",
            "description": "banding with ties",
            "tier_banding": {
                "1": 30.0, "2": 30.0, "3": 20.0, "4": 20.0,
                "5": 10.0, "6": 10.0, "7": 5.0, "8": 0.0,
            },
            "comp_floor_usd": {str(k): 50_000 + k * 5_000 for k in range(1, 9)},
            "dim_max": {"c1": 10.0, "c2": 10.0, "c3": 10.0,
                        "c4": 10.0, "c6": 10.0, "c7": 10.0},
        }
        cal = corpofit._parse_calibration_dict(ok)
        self.assertEqual(cal.tier_banding[1], 30.0)
        self.assertEqual(cal.tier_banding[8], 0.0)

    def test_rejects_missing_tier_in_banding(self):
        bad = {
            "name": "bad",
            "description": "missing tier 8",
            "tier_banding": {str(k): 30.0 for k in range(1, 8)},
            "comp_floor_usd": {str(k): 100_000 + k * 5_000 for k in range(1, 9)},
            "dim_max": {"c1": 10.0, "c2": 10.0, "c3": 10.0,
                        "c4": 10.0, "c6": 10.0, "c7": 10.0},
        }
        with self.assertRaises(ValueError):
            corpofit._parse_calibration_dict(bad)

    def test_rejects_missing_dim_in_dim_max(self):
        bad = {
            "name": "bad",
            "description": "missing c7",
            "tier_banding": {str(k): 30.0 for k in range(1, 9)},
            "comp_floor_usd": {str(k): 100_000 + k * 5_000 for k in range(1, 9)},
            "dim_max": {"c1": 10.0, "c2": 10.0, "c3": 10.0,
                        "c4": 10.0, "c6": 10.0},
        }
        with self.assertRaises(ValueError):
            corpofit._parse_calibration_dict(bad)


class LogPersistenceTests(unittest.TestCase):
    def test_log_writes_one_record_per_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "score_log.jsonl"
            result = corpofit.compute_fit(
                tier=5, c1=10, c2=12, c3=10, c4=10, c6=6, c7=2, comp=150_000
            )
            written = corpofit.log_score_record(result, "Acme Corp", log_path=log)
            self.assertEqual(written, log)
            self.assertTrue(log.exists())
            lines = log.read_text().splitlines()
            self.assertEqual(len(lines), 1)
            rec = json.loads(lines[0])
            self.assertEqual(rec["company"], "Acme Corp")
            self.assertEqual(rec["tier"], 5)
            self.assertEqual(rec["decision"], "APPLY")
            self.assertIn("_revision", rec)
            self.assertEqual(len(rec["_revision"]), 8)
            self.assertEqual(rec["schema_version"], "1.1")
            self.assertIsNone(rec["outcome"])

    def test_log_appends_three_records_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "score_log.jsonl"
            result = corpofit.compute_fit(
                tier=5, c1=10, c2=12, c3=10, c4=10, c6=6, c7=2
            )
            corpofit.log_score_record(result, "First Co", log_path=log)
            corpofit.log_score_record(result, "Second Co", log_path=log)
            corpofit.log_score_record(result, "Third Co", log_path=log)
            lines = log.read_text().splitlines()
            self.assertEqual(len(lines), 3)
            companies = [json.loads(L)["company"] for L in lines]
            self.assertEqual(companies, ["First Co", "Second Co", "Third Co"])

    def test_log_rejects_empty_company(self):
        result = corpofit.compute_fit(
            tier=5, c1=10, c2=12, c3=10, c4=10, c6=6, c7=2
        )
        with self.assertRaises(ValueError):
            corpofit.log_score_record(result, "", log_path=Path("/tmp/_nowhere"))
        with self.assertRaises(ValueError):
            corpofit.log_score_record(result, "   ", log_path=Path("/tmp/_nowhere"))

    def test_log_persists_gate_blocked_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "score_log.jsonl"
            result = corpofit.compute_fit(tier=9, c1=0, c2=0, c3=0, c4=0, c6=0, c7=0)
            corpofit.log_score_record(result, "Tier-9 Co", log_path=log)
            rec = json.loads(log.read_text().splitlines()[0])
            self.assertEqual(rec["decision"], "DO_NOT_APPLY")
            self.assertEqual(rec["gate_blocked_at"], "gate_1")
            self.assertIsNone(rec["score_final"])

    def test_log_auto_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "nested" / "deeper"
            log = nested / "score_log.jsonl"
            self.assertFalse(nested.exists(),
                             "preconditions: nested path must not exist yet")
            result = corpofit.compute_fit(
                tier=5, c1=10, c2=12, c3=10, c4=10, c6=6, c7=2
            )
            corpofit.log_score_record(result, "DeepCo", log_path=log)
            # Test name promises parent-dir creation; assert that
            # explicitly rather than implying it from log file existence.
            self.assertTrue(nested.is_dir(),
                            f"parent directory {nested} should have been auto-created")
            self.assertTrue(log.is_file(),
                            f"log file {log} should have been written")
            # And the record must be valid JSONL with the company name.
            line = log.read_text().strip()
            rec = json.loads(line)
            self.assertEqual(rec["company"], "DeepCo")


class InstallIdTests(unittest.TestCase):
    """W4 watermark: optional `_install_id` field round-trip."""

    def _make_cal_dict(self, install_id=None):
        d = {
            "name": "iid-test",
            "description": "for install_id round-trip",
            "tier_banding": {str(k): 35.0 - (k - 1) * 4 for k in range(1, 9)},
            "comp_floor_usd": {str(k): 50_000 + k * 5_000 for k in range(1, 9)},
            "dim_max": {"c1": 10.0, "c2": 10.0, "c3": 10.0,
                        "c4": 10.0, "c6": 10.0, "c7": 10.0},
        }
        if install_id is not None:
            d["_install_id"] = install_id
        return d

    def _write_and_load(self, d):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(d, f)
            tmp = Path(f.name)
        try:
            return corpofit.load_calibration(tmp)
        finally:
            tmp.unlink()

    def test_missing_install_id_is_none(self):
        cal = self._write_and_load(self._make_cal_dict())
        self.assertIsNone(cal.install_id)

    def test_present_install_id_round_trips(self):
        cal = self._write_and_load(self._make_cal_dict(install_id="f3a2c891"))
        self.assertEqual(cal.install_id, "f3a2c891")

    def test_install_id_changes_revision(self):
        cal_no = self._write_and_load(self._make_cal_dict())
        cal_a = self._write_and_load(self._make_cal_dict(install_id="f3a2c891"))
        cal_b = self._write_and_load(self._make_cal_dict(install_id="abcdef01"))
        # Distinct install_ids must yield distinct revisions, and both
        # must differ from the no-install_id baseline.
        self.assertNotEqual(cal_a.revision, cal_b.revision)
        self.assertNotEqual(cal_a.revision, cal_no.revision)
        self.assertNotEqual(cal_b.revision, cal_no.revision)

    def test_install_id_must_be_8_hex_chars(self):
        for bad in ("F3A2C891", "f3a2c89", "f3a2c8911", "zzzzzzzz", 12345678, ""):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self._write_and_load(self._make_cal_dict(install_id=bad))

    def test_install_id_revision_is_deterministic(self):
        cal_1 = self._write_and_load(self._make_cal_dict(install_id="f3a2c891"))
        cal_2 = self._write_and_load(self._make_cal_dict(install_id="f3a2c891"))
        self.assertEqual(cal_1.revision, cal_2.revision)

    def test_init_user_calibration_writes_install_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            user = tmp_p / "calibration.json"
            example = tmp_p / "calibration.example.json"
            example.write_text(json.dumps(self._make_cal_dict()))
            written = corpofit.init_user_calibration(
                example_path=example, user_path=user
            )
            self.assertEqual(written, user)
            self.assertTrue(user.is_file())
            data = json.loads(user.read_text())
            self.assertIn("_install_id", data)
            self.assertRegex(data["_install_id"], r"^[0-9a-f]{8}$")

    def test_init_user_calibration_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            user = tmp_p / "calibration.json"
            example = tmp_p / "calibration.example.json"
            example.write_text(json.dumps(self._make_cal_dict()))
            user.write_text("{}")  # pre-existing
            with self.assertRaises(FileExistsError):
                corpofit.init_user_calibration(
                    example_path=example, user_path=user
                )

    def test_init_user_calibration_fails_when_example_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            user = tmp_p / "calibration.json"
            example = tmp_p / "calibration.example.json"  # never written
            with self.assertRaises(FileNotFoundError):
                corpofit.init_user_calibration(
                    example_path=example, user_path=user
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
