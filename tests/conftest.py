"""Tests for the skill's bundled scripts.

Run from the skill folder (metadata-cleanup/):

    uv run --no-project --with pytest==8.3.5 --with daff==1.4.2 --with frictionless==5.19.1 --with pandas==3.0.5 pytest tests/

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
            path.write_text("".join(sep.join(r) + "\n" for r in content),
                            encoding=encoding, newline="")
        return path
    return _write
