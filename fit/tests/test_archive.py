"""Tests for repo_archive.py: encode, decode, round-trip integrity."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_SCRIPT = _REPO / "scripts" / "repo_archive.py"

spec = importlib.util.spec_from_file_location("repo_archive", _SCRIPT)
repo_archive = importlib.util.module_from_spec(spec)
sys.modules["repo_archive"] = repo_archive
spec.loader.exec_module(repo_archive)


def _seed_source(source_dir: Path, files: dict[str, str]) -> None:
    source_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (source_dir / name).write_text(content, encoding="utf-8")


class EncodeTests(unittest.TestCase):
    def test_encode_writes_archive_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            _seed_source(src, {"a.md": "alpha", "b.md": "beta"})
            archive = Path(tmp) / "out" / "archive.bin"
            stats = repo_archive.encode_archive(src, archive)
            self.assertTrue(archive.exists())
            self.assertEqual(stats["file_count"], 2)
            self.assertGreater(stats["encoded_bytes"], 0)

    def test_encode_includes_all_source_files_in_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            _seed_source(src, {"x.md": "one", "y.md": "two", "z.md": "three"})
            archive = Path(tmp) / "archive.bin"
            stats = repo_archive.encode_archive(src, archive)
            self.assertEqual(set(stats["files"]), {"x.md", "y.md", "z.md"})

    def test_encode_raises_on_missing_source_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                repo_archive.encode_archive(
                    Path(tmp) / "nonexistent", Path(tmp) / "archive.bin"
                )

    def test_encode_raises_on_empty_source_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            with self.assertRaises(ValueError):
                repo_archive.encode_archive(src, Path(tmp) / "archive.bin")

    def test_encode_compresses_meaningfully_for_redundant_content(self):
        """Highly repetitive content should compress dramatically."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            content = "the same line repeated\n" * 1000
            _seed_source(src, {"repeated.md": content})
            archive = Path(tmp) / "archive.bin"
            stats = repo_archive.encode_archive(src, archive)
            self.assertLess(
                stats["compressed_bytes"], stats["raw_bytes"] // 10,
                "highly repetitive content should compress to <10% of raw",
            )


class DecodeTests(unittest.TestCase):
    def test_decode_recovers_byte_identical_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            originals = {
                "a.md": "alpha content with special chars: !@#$\n",
                "b.md": "beta content\nmultiline\nthree lines\n",
            }
            _seed_source(src, originals)
            archive = Path(tmp) / "archive.bin"
            repo_archive.encode_archive(src, archive)

            dest = Path(tmp) / "dest"
            stats = repo_archive.decode_archive(archive, dest)
            self.assertEqual(stats["file_count"], 2)
            for name, original in originals.items():
                restored = (dest / name).read_text(encoding="utf-8")
                self.assertEqual(restored, original)

    def test_decode_raises_on_missing_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                repo_archive.decode_archive(
                    Path(tmp) / "no-such-file.bin", Path(tmp) / "dest"
                )


class RoundTripTests(unittest.TestCase):
    def test_verify_succeeds_on_normal_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            _seed_source(src, {"a.md": "alpha", "b.md": "beta", "c.md": "gamma"})
            archive = Path(tmp) / "archive.bin"
            stats = repo_archive.verify_round_trip(src, archive)
            self.assertTrue(stats["verified"])
            self.assertEqual(stats["mismatches"], [])

    def test_verify_succeeds_on_unicode_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            _seed_source(src, {
                "u.md": "unicode: cafe, naive, jalapeno, emoji shrug\n",
            })
            archive = Path(tmp) / "archive.bin"
            stats = repo_archive.verify_round_trip(src, archive)
            # Tighten: both verified=True AND mismatches=[] are required to
            # confirm byte-identical round-trip. assertTrue alone leaves
            # the door open for partial-mismatch states.
            self.assertEqual(stats["verified"], True)
            self.assertEqual(stats["mismatches"], [],
                             f"unicode round-trip mismatched: {stats['mismatches']!r}")

    def test_ground_truth_archive_decodes_cleanly(self):
        """The committed data/classification_archive.bin must decode
        without errors AND contain the canonical seven reference
        files. Regression test against silent corruption + content drift."""
        ground_archive = _REPO / "data" / "classification_archive.bin"
        if not ground_archive.exists():
            self.skipTest("no ground-truth archive present; run encode first")
        with tempfile.TemporaryDirectory() as tmp:
            stats = repo_archive.decode_archive(ground_archive, Path(tmp))
            self.assertGreater(stats["file_count"], 0)
            self.assertGreater(stats["raw_bytes"], 0)
            # Verify the canonical seven reference files are present.
            # If any are missing the archive has drifted from spec; if any
            # are added, the spec changed and this test should be updated.
            extracted = {p.name for p in Path(tmp).iterdir() if p.is_file()}
            canonical = {
                "c5_ethics_framework.md",
                "epistemic_standards.md",
                "extended_sector_reference.md",
                "insurance_subsectors.md",
                "job_fit_score.md",
                "onboarding.md",
                "surveillance_carceral.md",
            }
            self.assertEqual(
                extracted, canonical,
                f"archive contents drifted from canonical set: "
                f"missing={canonical - extracted}, extra={extracted - canonical}"
            )
            # Each file should have non-trivial content.
            for name in canonical:
                content = (Path(tmp) / name).read_text(encoding="utf-8")
                self.assertGreater(
                    len(content), 1000,
                    f"{name} is suspiciously short ({len(content)} bytes)"
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
