#!/bin/sh
# Runs the tests for the bundled scripts from any directory. The environment
# is built from the scripts' own dependency blocks, so each pinned version has
# one home; only a minimum pytest version is set here.
cd "$(dirname "$0")" || exit 1
exec uv run --no-project \
    --with-requirements scripts/cleanup_template.py \
    --with-requirements scripts/diff_tables.py \
    --with-requirements scripts/metadata_profile.py \
    --with "pytest>=8" \
    pytest tests/ "$@"
