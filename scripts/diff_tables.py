# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "daff==1.4.2",
# ]
# ///
"""Diff two versions of a table, cell by cell, as an HTML page.

    uv run diff_tables.py PREVIOUS.tsv NEW.tsv --key sample_name --out DIFF.html

TSV files are read with every cell as text, exactly as written: rows split
on line feeds, cells on tabs, quote characters kept, and a blank line read as
a row of empty cells. (daff's own reader treats quotes CSV-style, so TSV is
split here.) A .csv file is read by daff's own CSV reader; a byte-order mark
is dropped from either. Rows are matched by the key column, not by position;
if it is missing from either file, or its values repeat or are empty in
either, daff matches rows by content instead, and the summary says so.

Prints a one-line summary. If nothing changed, says so and writes no page.
Never overwrites an existing page.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import daff


def read_table(path: Path) -> list[list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".csv":
        table = daff.Csv(",").makeTable(text)
        rows = [
            [table.getCell(x, y) or "" for x in range(table.get_width())]
            for y in range(table.get_height())
        ]
        return rows
    # Split TSV here, not with the cleanup scripts' reader, so a bug in that
    # reader still shows in the diff; everything else is left to daff
    lines = text.split("\n")  # same-pattern-ok: independent of shared reader
    if lines and lines[-1] == "":
        lines = lines[:-1]
    lines = [line[:-1] if line.endswith("\r") else line for line in lines]
    rows = [line.split("\t") for line in lines]
    # Pad short rows (a blank line) to the header's width, as daff needs
    width = len(rows[0]) if rows else 0
    padded = [r + [""] * (width - len(r)) for r in rows]
    return padded


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
    # Why the key cannot identify every row, if it cannot
    reason = ""
    for name, t in (("previous", old), ("new", new)):
        if not t or a.key not in t[0]:
            reason = reason or f"{a.key} is not in the {name} file's header"
            continue
        col = t[0].index(a.key)
        keys = [row[col] if len(row) > col else "" for row in t[1:]]
        if "" in keys or len(keys) != len(set(keys)):
            reason = reason or f"{a.key} repeats or is empty"
    unique = not reason

    # Match rows by the key only when it identifies every row; otherwise daff decides
    flags = daff.CompareFlags()
    if unique:
        flags.addPrimaryKey(a.key)
    matched_by = a.key if unique else "content"
    alignment = daff.Coopy.compareTables(
        daff.PythonTableView(old), daff.PythonTableView(new), flags
    ).align()
    result = daff.PythonTableView([])
    daff.TableDiff(alignment, flags).hilite(result)
    rows = result.data

    # Count daff's markers: on each row, and on each column in the schema row
    row_marks = Counter(r[0] for r in rows if r)
    changed, added, removed = row_marks["->"], row_marks["+++"], row_marks["---"]
    schema = next((r for r in rows if r and r[0] == "!"), [])
    col_marks = Counter(schema[1:])
    cols_added, cols_removed = col_marks["+++"], col_marks["---"]
    # "(old name)" marks a rename and ":" a move; "..." only marks hidden columns
    cols_renamed = sum(1 for c in schema[1:] if c.startswith("("))
    cols_moved = col_marks[":"]

    if not (
        changed
        or added
        or removed
        or cols_added
        or cols_removed
        or cols_renamed
        or cols_moved
    ):
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
        f"<p>Previous: {a.previous.name}<br>New: {a.new.name}<br>Rows matched by: {matched_by}</p>"
        f'<div class="highlighter">{html}</div></body></html>\n'
    )
    a.out.write_text(page, encoding="utf-8")
    by_content = "" if unique else f"; rows matched by content: {reason}"
    print(
        f"{changed} rows changed, {added} added, {removed} removed; "
        f"{cols_added} columns added, {cols_removed} removed, "
        f"{cols_renamed} renamed, {cols_moved} moved{by_content} -> {a.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
