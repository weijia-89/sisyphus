#!/usr/bin/env bash
# Canonical verify: persona YAMLs, example symlink, catalog paths, fit_calibration parity.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -c "import sys; sys.path.insert(0,'.'); from lib.search_profile import verify_search_profiles; verify_search_profiles()"
test -f config/profile_catalog.yaml
test -f docs/SEARCH_PROFILES.md
