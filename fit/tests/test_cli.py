"""CLI integration tests: invoke scripts via subprocess and check exit codes
plus stdout shape. Catches argparse drift that unit tests would miss."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_CORPOFIT = _REPO / "scripts" / "corpofit.py"
_ELICIT = _REPO / "scripts" / "elicit.py"
_ARCHIVE = _REPO / "scripts" / "repo_archive.py"


def _run(script: Path, args: list[str], cwd: Path = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, timeout=15,
        cwd=cwd or _REPO,
    )


def _run_with_input(
    script: Path, args: list[str], stdin_text: str, cwd: Path = None,
) -> subprocess.CompletedProcess:
    """Variant of _run that pipes stdin_text into the subprocess.

    Used by the --interactive flow tests. Kept separate from _run so the
    existing argv-only tests stay untouched.
    """
    return subprocess.run(
        [sys.executable, str(script), *args],
        input=stdin_text,
        capture_output=True, text=True, timeout=15,
        cwd=cwd or _REPO,
    )


class CorpofitCLITests(unittest.TestCase):
    def test_help_exits_zero_and_mentions_tier(self):
        result = _run(_CORPOFIT, ["--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("--tier", result.stdout)
        self.assertIn("--c1", result.stdout)

    def test_valid_scoring_exits_zero_with_no_log(self):
        result = _run(_CORPOFIT, [
            "--tier", "5",
            "--c1", "10", "--c2", "12", "--c3", "11",
            "--c4", "10", "--c6", "7", "--c7", "2",
            "--comp", "150000",
            "--no-log",
        ])
        self.assertEqual(result.returncode, 0,
                         f"stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertIn("APPLY", result.stdout)
        self.assertIn("Band:", result.stdout)

    def test_tier_9_exits_with_code_4(self):
        result = _run(_CORPOFIT, [
            "--tier", "9",
            "--c1", "0", "--c2", "0", "--c3", "0",
            "--c4", "0", "--c6", "0", "--c7", "0",
            "--no-log",
        ])
        self.assertEqual(result.returncode, 4,
                         f"stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertIn("DO_NOT_APPLY", result.stdout)
        self.assertIn("gate_1", result.stdout)

    def test_gate_2_below_floor_exits_with_code_3(self):
        result = _run(_CORPOFIT, [
            "--tier", "7",
            "--c1", "10", "--c2", "10", "--c3", "10",
            "--c4", "10", "--c6", "5", "--c7", "2",
            "--comp", "100000",
            "--no-log",
        ])
        self.assertEqual(result.returncode, 3,
                         f"stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertIn("gate_2", result.stdout)

    def test_missing_tier_returns_nonzero_with_helpful_message(self):
        result = _run(_CORPOFIT, ["--c1", "10", "--no-log"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--tier", result.stderr)

    def test_json_output_is_valid_json(self):
        result = _run(_CORPOFIT, [
            "--tier", "5",
            "--c1", "10", "--c2", "12", "--c3", "11",
            "--c4", "10", "--c6", "7", "--c7", "2",
            "--no-log", "--json",
        ])
        self.assertEqual(result.returncode, 0)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["decision"], "APPLY")
        self.assertEqual(parsed["tier"], 5)
        # Tighten: score_final must be a positive float and equal
        # c5_score + internal_total within rounding (the documented
        # contract from compute_fit). Empty-assertion replaces
        # assertIsNotNone with a structural + numerical check.
        self.assertIsInstance(parsed["score_final"], (int, float))
        self.assertGreater(parsed["score_final"], 0)
        self.assertAlmostEqual(
            parsed["score_final"],
            parsed["c5_score"] + parsed["internal_total"],
            places=1,
            msg="score_final must equal c5_score + internal_total",
        )
        # Sanity: should be in the GREEN band (>=65) for max-ish inputs.
        self.assertEqual(parsed["band"], "GREEN",
                         f"got band={parsed['band']} for inputs that should be GREEN")

    def test_company_required_when_logging(self):
        with tempfile.TemporaryDirectory() as tmp:
            # No --company, no --no-log: must error out before writing.
            result = _run(_CORPOFIT, [
                "--tier", "5",
                "--c1", "10", "--c2", "12", "--c3", "11",
                "--c4", "10", "--c6", "7", "--c7", "2",
            ])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--company", result.stderr)


class ProfilePickerTests(unittest.TestCase):
    """Cover the --interactive profile picker added 2026-05-20.

    Profiles in config/profiles/ are listed alphabetically; profile #1 is
    couple-no-deps-medium-col-2026 and the shipped default (no picker
    selection) is single-us-metro-2026, so the calibration_name in the
    result tells us which profile actually loaded.
    """

    # Stdin for the interactive flow AFTER the picker prompt. tier=4 with
    # mid-range internal dim values; blank comp at the end skips Gate 2.
    _INTERACTIVE_BODY = (
        "TestCorp\n"  # Step 0 company
        "4\n"         # Step 1 tier
        "10\n"        # C1 psych safety
        "12\n"        # C2 wlb
        "11\n"        # C3 manager
        "10\n"        # C4 security
        "7\n"         # C6 growth
        "2\n"         # C7 comp sustainability
        "\n"          # Step 3 comp (blank = skip)
    )

    def test_picker_selection_loads_chosen_profile(self):
        # "1\n" picks profile 1 (couple-no-deps-medium-col-2026) which is
        # NOT the shipped default. The calibration_name in --json output
        # confirms the picker overrode the default.
        result = _run_with_input(
            _CORPOFIT,
            ["--interactive", "--json", "--no-log"],
            stdin_text="1\n" + self._INTERACTIVE_BODY,
        )
        self.assertEqual(
            result.returncode, 0,
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        # Picker menu rendered with the chosen profile listed.
        self.assertIn("couple-no-deps-medium-col-2026", result.stdout)
        # Find the JSON object that compute_fit emits at the end of stdout.
        # The interactive prompts print to stdout too, so we locate the
        # first '{' and parse from there.
        brace_idx = result.stdout.find("{")
        self.assertGreater(brace_idx, -1,
                           f"no JSON found in stdout: {result.stdout!r}")
        parsed = json.loads(result.stdout[brace_idx:])
        self.assertEqual(
            parsed["calibration_name"],
            "couple-no-deps-medium-col-2026",
            "picker selection #1 should have loaded "
            "couple-no-deps-medium-col-2026, not the shipped default",
        )

    def test_explicit_config_skips_picker(self):
        # --config + --interactive: picker MUST NOT prompt. stdin contains
        # only the interactive-body answers (no "1\n" picker selection).
        # If the picker were prompting, stdin would be consumed in the
        # wrong order and the interactive flow would fail.
        config_path = (
            _REPO / "config" / "profiles" / "single-low-col-2026.json"
        )
        result = _run_with_input(
            _CORPOFIT,
            ["--interactive", "--json", "--no-log",
             "--config", str(config_path)],
            stdin_text=self._INTERACTIVE_BODY,
        )
        self.assertEqual(
            result.returncode, 0,
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        # Picker prompt MUST be absent from stdout when --config wins.
        self.assertNotIn(
            "Calibration profile (optional).", result.stdout,
            "explicit --config must skip the picker; "
            f"got picker output in stdout: {result.stdout!r}",
        )
        # Confirm the --config-supplied profile loaded, not the shipped
        # default and not couple-no-deps from the picker.
        brace_idx = result.stdout.find("{")
        self.assertGreater(brace_idx, -1)
        parsed = json.loads(result.stdout[brace_idx:])
        self.assertEqual(parsed["calibration_name"], "single-low-col-2026")


class ElicitCLITests(unittest.TestCase):
    def test_help_exits_zero_and_lists_subcommands(self):
        result = _run(_ELICIT, ["--help"])
        self.assertEqual(result.returncode, 0)
        for sub in ("values", "cover-letter", "resume", "next-application"):
            self.assertIn(sub, result.stdout)

    def test_non_interactive_each_subcommand_writes_session(self):
        for sub in ("values", "cover-letter", "resume", "next-application"):
            with tempfile.TemporaryDirectory() as tmp:
                result = _run(_ELICIT, [
                    sub, "--non-interactive", "--sessions-dir", tmp,
                ])
                self.assertEqual(
                    result.returncode, 0,
                    f"{sub}: rc={result.returncode}, stderr={result.stderr!r}"
                )
                files = list(Path(tmp).glob("*.json"))
                self.assertEqual(
                    len(files), 1,
                    f"{sub}: expected 1 session file, got {len(files)}",
                )

    def test_unknown_subcommand_returns_nonzero(self):
        result = _run(_ELICIT, ["nonsense", "--non-interactive"])
        self.assertNotEqual(result.returncode, 0)


class ArchiveCLITests(unittest.TestCase):
    def test_help_exits_zero(self):
        result = _run(_ARCHIVE, ["--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("encode", result.stdout)
        self.assertIn("decode", result.stdout)
        self.assertIn("verify", result.stdout)

    def test_verify_with_ground_truth_archive(self):
        """Maintainer-only: verify round-trip when classification_archive.bin exists locally."""
        archive = _REPO / "data" / "classification_archive.bin"
        if not archive.exists():
            self.skipTest(
                "classification_archive.bin not present (lane-1: maintainer-only; "
                "encode locally from fit/.internal/archive_sources/)"
            )
        result = _run(_ARCHIVE, ["verify"])
        self.assertEqual(result.returncode, 0,
                         f"verify failed: {result.stdout!r} {result.stderr!r}")
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
