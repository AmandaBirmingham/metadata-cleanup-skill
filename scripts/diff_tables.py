# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "daff==1.4.2",
# ]
# ///
"""Diff two versions of a tab-separated table, cell by cell, as an HTML page.

    uv run diff_tables.py PREVIOUS.tsv NEW.tsv --key sample_name --out DIFF.html

Both files are read with every cell as text, exactly as written: rows split
on line feeds, cells on tabs, quote characters kept. (daff's own command-line
reader treats quotes CSV-style, so the files are read here and handed to
daff's Python interface.) Rows are matched by the key column, not by
position.

Prints a one-line summary. If nothing changed, says so and writes no page.
Never overwrites an existing page.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import daff


def read_table(path: Path) -> list[list[str]]:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    lines = [line[:-1] if line.endswith("\r") else line for line in lines]
    return [line.split("\t") for line in lines]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("previous", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument(
        "--key",
        required=True,
        help="column that identifies each row (e.g. sample_name)",
    )
    ap.add_argument("--out", required=True, type=Path, help="HTML page to write")
    a = ap.parse_args()

    if a.out.exists():
        sys.exit(f"STOPPED: {a.out} already exists; choose a new name.")
    old, new = read_table(a.previous), read_table(a.new)
    for name, t in (("previous", old), ("new", new)):
        if not t or a.key not in t[0]:
            sys.exit(
                f"STOPPED: key column {a.key!r} not found in the {name} file's header."
            )
        keys = [row[t[0].index(a.key)] for row in t[1:] if len(row) > t[0].index(a.key)]
        if len(keys) != len(set(keys)):
            sys.exit(
                f"STOPPED: key column {a.key!r} has repeated values in the {name} file."
            )

    flags = daff.CompareFlags()
    flags.addPrimaryKey(a.key)
    alignment = daff.Coopy.compareTables(
        daff.PythonTableView(old), daff.PythonTableView(new), flags
    ).align()
    result = daff.PythonTableView([])
    daff.TableDiff(alignment, flags).hilite(result)
    rows = result.data

    changed = sum(1 for r in rows if r and r[0] == "->")
    added = sum(1 for r in rows if r and r[0] == "+++")
    removed = sum(1 for r in rows if r and r[0] == "---")
    schema = next((r for r in rows if r and r[0] == "!"), [])
    cols_added = sum(1 for c in schema[1:] if c == "+++")
    cols_removed = sum(1 for c in schema[1:] if c == "---")

    if not (changed or added or removed or cols_added or cols_removed):
        print(
            f"No changes between {a.previous.name} and {a.new.name}; no page written."
        )
        return 0

    html = daff.DiffRender().render(result).html()
    css = daff.DiffRender().sampleCss()
    page = (
        '<!doctype html>\n<html><head><meta charset="utf-8">'
        f"<title>Diff: {a.new.name}</title><style>{css}"
        "body{font-family:sans-serif}</style></head><body>"
        f"<p>Previous: {a.previous.name}<br>New: {a.new.name}<br>Rows matched by: {a.key}</p>"
        f'<div class="highlighter">{html}</div></body></html>\n'
    )
    a.out.write_text(page, encoding="utf-8")
    print(
        f"{changed} rows changed, {added} added, {removed} removed; "
        f"{cols_added} columns added, {cols_removed} removed -> {a.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
