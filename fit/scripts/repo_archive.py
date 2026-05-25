#!/usr/bin/env python3
"""repo_archive.py: bundle and restore the working-state archive.

A maintainer-only utility (lane-1 merge does not ship the archive binary).
Bundles plaintext working files from a source directory into a compact binary
blob, or restores them from the blob back into the source directory.
Maintainers encode locally from fit/.internal/archive_sources/ into
fit/data/classification_archive.bin; clone-only operators skip ground-truth tests.

Encoding pipeline (encode mode):

    source_dir/*  -> tar -> gzip -> base64 -> archive_path

Decoding pipeline (decode mode):

    archive_path -> base64-decode -> gunzip -> untar -> source_dir/*

Usage:

    python3 scripts/repo_archive.py encode
    python3 scripts/repo_archive.py decode
    python3 scripts/repo_archive.py verify    # round-trip check

Defaults:

    source_dir   = .internal/archive_sources/
    archive_path = data/classification_archive.bin

Stdlib only. No external dependencies.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import sys
import tarfile
from pathlib import Path
from typing import Optional


_SCRIPT = Path(__file__).resolve()
_REPO_ROOT = _SCRIPT.parent.parent
_DEFAULT_SOURCE = _REPO_ROOT / ".internal" / "archive_sources"
_DEFAULT_ARCHIVE = _REPO_ROOT / "data" / "classification_archive.bin"


def encode_archive(source_dir: Path, archive_path: Path) -> dict:
    """Bundle source_dir/* into a base64-of-gzipped-tar at archive_path.

    Returns a stat dict with file_count, raw_bytes, compressed_bytes,
    sha256_first8 of the output.
    """
    if not source_dir.is_dir():
        raise FileNotFoundError(f"source directory missing: {source_dir}")
    files = sorted(p for p in source_dir.iterdir() if p.is_file())
    if not files:
        raise ValueError(f"source directory has no files: {source_dir}")

    raw_buffer = io.BytesIO()
    with tarfile.open(fileobj=raw_buffer, mode="w") as tf:
        for fp in files:
            tf.add(fp, arcname=fp.name)
    raw_bytes = raw_buffer.getvalue()

    compressed = gzip.compress(raw_bytes, compresslevel=9)
    encoded = base64.b64encode(compressed)

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(encoded)

    return {
        "file_count": len(files),
        "raw_bytes": len(raw_bytes),
        "compressed_bytes": len(compressed),
        "encoded_bytes": len(encoded),
        "sha256_first8": hashlib.sha256(encoded).hexdigest()[:8],
        "archive_path": str(archive_path),
        "source_dir": str(source_dir),
        "files": [fp.name for fp in files],
    }


def decode_archive(archive_path: Path, source_dir: Path) -> dict:
    """Restore files from archive_path into source_dir.

    Returns a stat dict with file_count, raw_bytes, files extracted.
    """
    if not archive_path.is_file():
        raise FileNotFoundError(f"archive file missing: {archive_path}")

    encoded = archive_path.read_bytes()
    compressed = base64.b64decode(encoded)
    raw_bytes = gzip.decompress(compressed)

    source_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []
    with tarfile.open(fileobj=io.BytesIO(raw_bytes), mode="r") as tf:
        members = tf.getmembers()
        for m in members:
            if not m.isfile():
                continue
            if "/" in m.name or m.name.startswith(".."):
                raise ValueError(f"refusing to extract unsafe path: {m.name}")
            # sdk-review F3: filter= requires 3.12+; path checks above cover older runtimes
            extract_kwargs: dict = {}
            if hasattr(tarfile, "data_filter"):
                extract_kwargs["filter"] = "data"
            tf.extract(m, path=source_dir, **extract_kwargs)
            extracted.append(m.name)

    return {
        "file_count": len(extracted),
        "raw_bytes": len(raw_bytes),
        "encoded_bytes": len(encoded),
        "files": extracted,
        "archive_path": str(archive_path),
        "source_dir": str(source_dir),
    }


def verify_round_trip(source_dir: Path, archive_path: Path) -> dict:
    """Encode then decode into a temp dir; confirm byte-identical files.

    Returns a stat dict with verified=True/False and any mismatches.
    """
    import tempfile

    encode_stats = encode_archive(source_dir, archive_path)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        decode_stats = decode_archive(archive_path, tmp_path)

        mismatches: list[str] = []
        for name in decode_stats["files"]:
            original = (source_dir / name).read_bytes()
            restored = (tmp_path / name).read_bytes()
            if original != restored:
                mismatches.append(name)

    return {
        "verified": not mismatches,
        "mismatches": mismatches,
        "encode": encode_stats,
        "decode_file_count": decode_stats["file_count"],
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "action",
        choices=["encode", "decode", "verify"],
        help="What to do.",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=_DEFAULT_SOURCE,
        help=f"Source directory (default: {_DEFAULT_SOURCE}).",
    )
    parser.add_argument(
        "--archive-path",
        type=Path,
        default=_DEFAULT_ARCHIVE,
        help=f"Archive file (default: {_DEFAULT_ARCHIVE}).",
    )
    args = parser.parse_args(argv)

    try:
        if args.action == "encode":
            stats = encode_archive(args.source_dir, args.archive_path)
            print(f"encoded {stats['file_count']} file(s):")
            for f in stats["files"]:
                print(f"  - {f}")
            print(f"  raw:        {stats['raw_bytes']:>9,} bytes")
            print(f"  compressed: {stats['compressed_bytes']:>9,} bytes")
            print(f"  encoded:    {stats['encoded_bytes']:>9,} bytes")
            print(f"  sha256:8:   {stats['sha256_first8']}")
            print(f"  archive:    {stats['archive_path']}")
        elif args.action == "decode":
            stats = decode_archive(args.archive_path, args.source_dir)
            print(f"decoded {stats['file_count']} file(s):")
            for f in stats["files"]:
                print(f"  - {f}")
            print(f"  destination: {stats['source_dir']}")
        else:
            stats = verify_round_trip(args.source_dir, args.archive_path)
            if stats["verified"]:
                print(f"verify OK: {stats['encode']['file_count']} file(s) round-tripped byte-identically")
            else:
                print(f"verify FAILED: {len(stats['mismatches'])} mismatch(es)")
                for m in stats["mismatches"]:
                    print(f"  - {m}")
                return 1
    except (FileNotFoundError, ValueError, OSError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
