"""Tests for the elicitation harness."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_SCRIPT = _REPO / "scripts" / "elicit.py"

spec = importlib.util.spec_from_file_location("elicit", _SCRIPT)
elicit = importlib.util.module_from_spec(spec)
sys.modules["elicit"] = elicit
spec.loader.exec_module(elicit)


class SlugifyTests(unittest.TestCase):
    def test_lowercases_and_dashes_spaces(self):
        self.assertEqual(elicit.slugify("Acme Corp"), "acme-corp")

    def test_collapses_punctuation(self):
        self.assertEqual(elicit.slugify("Foo, Inc!!!"), "foo-inc")

    def test_strips_leading_and_trailing_separators(self):
        self.assertEqual(elicit.slugify("  spaces  "), "spaces")

    def test_empty_input_returns_unnamed(self):
        self.assertEqual(elicit.slugify(""), "unnamed")
        self.assertEqual(elicit.slugify("   "), "unnamed")

    def test_only_punctuation_returns_unnamed(self):
        self.assertEqual(elicit.slugify("!!!"), "unnamed")


class PromptSetTests(unittest.TestCase):
    def test_all_subcommands_have_prompt_sets(self):
        self.assertEqual(
            set(elicit.PROMPT_SETS.keys()),
            {"values", "cover-letter", "resume", "next-application"},
        )

    def test_each_prompt_has_three_fields(self):
        for subcmd, prompts in elicit.PROMPT_SETS.items():
            for entry in prompts:
                self.assertEqual(
                    len(entry), 3,
                    f"{subcmd}: prompt entry must be (key, question, hint)",
                )

    def test_each_prompt_set_is_non_empty(self):
        for subcmd, prompts in elicit.PROMPT_SETS.items():
            self.assertGreater(
                len(prompts), 0,
                f"{subcmd}: prompt set must have at least one prompt",
            )

    def test_prompt_keys_are_unique_within_each_set(self):
        for subcmd, prompts in elicit.PROMPT_SETS.items():
            keys = [k for k, _q, _h in prompts]
            self.assertEqual(
                len(keys), len(set(keys)),
                f"{subcmd}: prompt keys must be unique within a set",
            )

    def test_values_set_includes_must_have_and_comp_floor(self):
        keys = [k for k, _q, _h in elicit.VALUES_PROMPTS]
        self.assertIn("must_have", keys)
        self.assertIn("comp_floor", keys)

    def test_cover_letter_set_includes_why_this_company(self):
        keys = [k for k, _q, _h in elicit.COVER_LETTER_PROMPTS]
        self.assertIn("why_this_company", keys)
        self.assertIn("why_now", keys)

    def test_next_application_set_includes_all_seven_dimensions(self):
        keys = [k for k, _q, _h in elicit.NEXT_APPLICATION_PROMPTS]
        for dim_key in (
            "c1_psych_safety", "c2_wlb", "c3_manager",
            "c4_security", "c6_growth", "c7_comp",
        ):
            self.assertIn(dim_key, keys)


class SessionFilenameTests(unittest.TestCase):
    def test_filename_includes_subcommand_and_date(self):
        name = elicit.session_filename("values", {})
        self.assertTrue(name.startswith("values-"))
        self.assertTrue(name.endswith(".json"))

    def test_filename_includes_company_when_present(self):
        name = elicit.session_filename(
            "cover-letter", {"company": "Acme Corp"}
        )
        self.assertIn("acme-corp", name)
        self.assertTrue(name.startswith("cover-letter-"))


class SaveSessionTests(unittest.TestCase):
    def test_save_creates_json_with_schema_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            answers = {"k1": "answer one", "k2": "answer two"}
            path = elicit.save_session("values", answers, sessions_dir=Path(tmp))
            self.assertTrue(path.exists())
            payload = json.loads(path.read_text())
            self.assertEqual(payload["schema_version"], "1.0")
            self.assertEqual(payload["subcommand"], "values")
            self.assertEqual(payload["answers"], answers)
            self.assertEqual(payload["answered_count"], 2)
            self.assertEqual(payload["total_prompts"], 2)

    def test_empty_answers_count_as_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            answers = {"k1": "", "k2": "filled", "k3": ""}
            path = elicit.save_session("resume", answers, sessions_dir=Path(tmp))
            payload = json.loads(path.read_text())
            self.assertEqual(payload["answered_count"], 1)
            self.assertEqual(payload["total_prompts"], 3)

    def test_creates_sessions_directory_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "nested" / "missing"
            path = elicit.save_session(
                "values", {"k": "v"}, sessions_dir=nested
            )
            self.assertTrue(path.exists())
            self.assertEqual(path.parent, nested)


class NonInteractiveModeTests(unittest.TestCase):
    def test_non_interactive_saves_empty_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = elicit.main([
                "values", "--non-interactive",
                "--sessions-dir", tmp,
            ])
            self.assertEqual(rc, 0)
            files = list(Path(tmp).glob("*.json"))
            self.assertEqual(len(files), 1)
            payload = json.loads(files[0].read_text())
            self.assertEqual(payload["answered_count"], 0)
            self.assertGreater(payload["total_prompts"], 0)

    def test_non_interactive_for_all_four_subcommands(self):
        for subcmd in ("values", "cover-letter", "resume", "next-application"):
            with tempfile.TemporaryDirectory() as tmp:
                rc = elicit.main([
                    subcmd, "--non-interactive",
                    "--sessions-dir", tmp,
                ])
                self.assertEqual(rc, 0, f"{subcmd} non-interactive must exit 0")
                files = list(Path(tmp).glob("*.json"))
                self.assertEqual(
                    len(files), 1,
                    f"{subcmd} must produce one session file",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
