"""Tests for the skill's bundled scripts.

Run with run_tests.sh in the skill folder, from any directory; extra
arguments go to pytest.

Every test builds its own small input files; no real study data is used.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


@pytest.fixture
def write(tmp_path):
    """write("name.tsv", text) or write("name.tsv", rows) -> path. Rows are lists
    of cells, joined with tabs (or commas for .csv) and ended with LF."""

    def _write(name, content, encoding="utf-8", raw=None):
        path = tmp_path / name
        if raw is not None:
            path.write_bytes(raw)
        elif isinstance(content, str):
            path.write_text(content, encoding=encoding, newline="")
        else:
            sep = "," if name.endswith(".csv") else "\t"
            path.write_text(
                "".join(sep.join(r) + "\n" for r in content),
                encoding=encoding,
                newline="",
            )
        return path

    return _write
