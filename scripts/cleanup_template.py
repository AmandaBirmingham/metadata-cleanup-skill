# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas==3.0.5",
# ]
# ///
"""
Cleanup script -- <study name>
Scientist:     <name>
Started:       <YYYY-MM-DD>
Decision log:  <decision_log_YYYYMMDD-HHMMSS.md>

Made from the metadata-cleanup skill's scripts/cleanup_template.py. It carries
out every decision in the decision log that changes data; what was decided and
why is in the log, not here.

Run (draft):
    uv run cleanup_draft.py --inputs DIR --outdir DIR --timestamp YYYYMMDD-HHMMSS \\
        --decision-log decision_log_....md --diff-script <skill>/scripts/diff_tables.py
Run (final, after the scientist says the discussion is done):
    uv run cleanup_<timestamp>.py --inputs DIR --outdir DIR --timestamp <timestamp> \\
        --decision-log decision_log_....md --final

Without uv: install the packages in the dependency block above into the
Python version it names, and run with python.
Each run starts from the original files, never writes to them, and never
overwrites an output.
"""

from __future__ import annotations

import argparse
import csv
import glob
import io
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

# ===========================================================================
# EDIT HERE: the input files and the decisions
# ===========================================================================
INPUTS: dict[str, str] = {}  # table name -> file name in --inputs
ID_COLUMNS: dict[str, str] = {}  # table name -> the column that identifies its rows


def decisions(t):
    """One block per decision in the decision log, in ID order, headed by the
    ID alone. A decision that changes no data is just `pass`."""
    pass


# === END OF DECISIONS ===


# ===========================================================================
# Helper layer: do not edit
# ===========================================================================
READABLE_SUFFIXES = (".tsv", ".txt", ".csv")  # .csv is parsed as CSV, the rest as TSV
# Space characters other than the ordinary space: shown as a space, or invisible
WIDE_SPACES = "\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000"
ZERO_WIDTH = "\u200b\ufeff"
UNUSUAL_SPACE = re.compile(f"[{WIDE_SPACES}{ZERO_WIDTH}]")
SPACES = f"[ {WIDE_SPACES}]+"


class Stop(Exception):
    """A problem that must be fixed before the script can go on."""


CHANGES: list[dict] = []  # one entry per change, in the order made


def column_letter(index0: int) -> str:
    s, i = "", index0 + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


@dataclass
class RawTable:
    """A file's rows of cells exactly as written, plus facts about the file."""

    kind: str  # "csv" or "tsv"
    text: str
    bom: bool
    utf8: bool  # False: not valid UTF-8, so text was decoded as Latin-1
    crlf_lines: int
    records: list[list[str]]  # a blank line is an empty list


def read_file(path: Path) -> RawTable:
    """Every cell as text: TSV split on LF and TAB with quotes kept, CSV parsed
    the standard way. Stops on a file type it cannot read."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in READABLE_SUFFIXES:
        raise Stop(
            f"{path.name}: cannot read {suffix or 'unnamed'} files, only "
            + ", ".join(READABLE_SUFFIXES)
        )
    # Decode as UTF-8, falling back to Latin-1 so the file can still be inspected
    raw = path.read_bytes()
    try:
        text, utf8 = raw.decode("utf-8-sig"), True
    except UnicodeDecodeError:
        text, utf8 = raw.decode("latin-1"), False
    # Split into rows of cells; a blank line has no cells in either format
    if suffix == ".csv":
        kind = "csv"
        records = list(csv.reader(io.StringIO(text, newline="")))
    else:
        kind = "tsv"
        lines = text.split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]
        lines = [line[:-1] if line.endswith("\r") else line for line in lines]
        records = [line.split("\t") if line else [] for line in lines]
    raw_table = RawTable(
        kind=kind,
        text=text,
        bom=raw.startswith(b"\xef\xbb\xbf"),
        utf8=utf8,
        crlf_lines=text.count("\r\n"),
        records=records,
    )
    return raw_table


def unique_column_names(header: list[str]) -> list[str]:
    """Each name made unique where names repeat or are blank ("status [col C]",
    "[col D]"), so no column is lost."""
    seen = Counter(header)
    names = [
        h
        if h.strip() and (seen[h] == 1 or i == header.index(h))
        else (
            f"{h} [col {column_letter(i)}]"
            if h.strip()
            else f"[col {column_letter(i)}]"
        )
        for i, h in enumerate(header)
    ]
    return names


def one_line(v: str) -> str:
    """A value for one TSV cell: tabs and line breaks shown as \\t, \\r, \\n."""
    return v.replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")


def refuse_existing(*paths: Path) -> None:
    """Stop if any of the paths already exists: outputs are never overwritten."""
    for path in paths:
        if path.exists():
            raise Stop(
                f"{path} already exists; never overwrite an output; "
                "choose a new timestamp"
            )


def write_tsv(path: Path, header: list[str], rows: Iterable[tuple]) -> None:
    """Every cell as one line of text, so tabs and line breaks never split it."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("\t".join(header) + "\n")
        fh.writelines("\t".join(one_line(str(x)) for x in row) + "\n" for row in rows)


class Table:
    """One table: .df holds every cell as text. Rows are identified as
    "<table>|row N" (N = spreadsheet row, header = row 1); each column keeps
    its original letter, so renames don't lose track of it. id_column names
    the column whose values identify the table's rows (its IDs)."""

    def __init__(
        self,
        name: str,
        path: str | Path | None = None,
        df: pd.DataFrame | None = None,
        file: str | None = None,
        col_ids: dict[str, str] | None = None,
        *,
        id_column: str,
    ):
        self.name = name
        self.id_column = id_column
        self._invented: set[str] = set()  # names made up for repeated or blank headers
        if df is not None:  # built by stack()
            self.df, self.file, self._col_ids = df, file or name, dict(col_ids or {})
            return
        path = Path(path)
        self.path, self.file = path, path.name
        raw_table = read_file(path)
        if not raw_table.utf8:
            raise Stop(
                f"{self.file} is not valid UTF-8; converting it is a decision to make first"
            )
        records = raw_table.records
        if not records or not records[0]:
            raise Stop(f"{self.file} has no header row; fix the file first")
        # Keep blank lines as rows of empty cells; any other short or long row stops
        width = len(records[0])
        rows = []
        for i, r in enumerate(records[1:], start=2):
            if not r:
                r = [""] * width
            elif len(r) != width:
                raise Stop(
                    f"{self.file}: row {i} has {len(r)} cells but the header has "
                    f"{width}; fix the file first"
                )
            rows.append(r)
        names = unique_column_names(records[0])
        self._invented = {n for n, h in zip(names, records[0]) if n != h}
        df = pd.DataFrame(rows, columns=names, dtype=str)
        df.index = [f"{name}|row {i}" for i in range(2, len(df) + 2)]
        self.df = df
        self._col_ids = {n: column_letter(i) for i, n in enumerate(names)}
        self._need(id_column)

    def col_id(self, column: str) -> str:
        return self._col_ids.get(column, "")

    def _need(self, column: str) -> None:
        if column not in self.df.columns:
            raise Stop(f"{self.name}: no column named {column!r}")

    def unique_id(self, row_id: str) -> str:
        if self.id_column not in self.df.columns:
            return ""
        return self.df.at[row_id, self.id_column]


class RowSet:
    def __init__(self, table: Table, index: list[str]):
        self.table, self.index = table, index


class matches:
    """A condition: the whole value matches this regular expression."""

    def __init__(self, pattern: str):
        self.pattern = re.compile(pattern)

    def __call__(self, v: str) -> bool:
        return self.pattern.fullmatch(v) is not None


def _mask(table: Table, ids, conditions: dict) -> pd.Series:
    mask = pd.Series(True, index=table.df.index)
    if ids is not None:
        table._need(table.id_column)
        known = set(table.df[table.id_column])
        missing = [i for i in ids if i not in known]
        if missing:
            raise Stop(f"{table.name}: no row with ID {', '.join(missing)}")
        mask &= table.df[table.id_column].isin(ids)
    for column, cond in conditions.items():
        table._need(column)
        col = table.df[column]
        if callable(cond):
            m = col.map(lambda v: bool(cond(v)))
        elif isinstance(cond, (list, tuple, set)):
            m = col.isin(list(cond))
        else:
            m = col == cond
        if not m.any():
            raise Stop(f"{table.name}: the condition on {column!r} matches no rows")
        mask &= m
    return mask


def select(table: Table, ids: list[str] | None = None, **conditions) -> RowSet:
    """Rows matching every condition: a value, a list of values, matches(regex),
    a function of the value, or ids=[the table's IDs]. Stops if nothing matches."""
    mask = _mask(table, ids, conditions)
    if not mask.any():
        raise Stop(f"{table.name}: the selection matches no rows")
    return RowSet(table, list(table.df.index[mask]))


def exclude(rows: RowSet, ids: list[str] | None = None, **conditions) -> RowSet:
    """The rows minus those matching every condition. Stops if a condition
    matches none of the rows."""
    sub = Table.__new__(Table)
    sub.__dict__.update(rows.table.__dict__)
    sub.df = rows.table.df.loc[rows.index]
    mask = _mask(sub, ids, conditions)
    return RowSet(rows.table, [i for i, m in zip(rows.index, mask) if not m])


def _record(decision, kind, table, row_id="", column="", old="", new="", letter=None):
    CHANGES.append(
        {
            "decision": decision,
            "kind": kind,
            "file": table.file,
            "row": row_id.rsplit("row ", 1)[-1] if row_id else "",
            "column_letter": table.col_id(column) if letter is None else letter,
            "column": column,
            "table_unique_id": table.unique_id(row_id) if row_id else "",
            "old": old,
            "new": new,
        }
    )


def _refuse_column(table: Table, column: str, decision: str) -> None:
    if column in table.df.columns:
        raise Stop(f"{decision}: {table.name} already has a column named {column!r}")


def _own(table: Table, rows: RowSet) -> None:
    if rows.table is not table:
        raise Stop(
            f"these rows were selected from another table ({rows.table.name}), not {table.name}"
        )
    if not rows.index:
        raise Stop(f"{table.name}: no rows left to change in the selection")


def _change_cells(table: Table, row_ids, column: str, new_values, decision: str) -> int:
    n = 0
    for rid, new in zip(row_ids, new_values):
        old = table.df.at[rid, column]
        if old != new:
            table.df.at[rid, column] = new
            _record(decision, "value changed", table, rid, column, old, new)
            n += 1
    return n


def set_value(
    table: Table, rows: RowSet, column: str, value: str, decision: str
) -> None:
    _own(table, rows)
    table._need(column)
    if not _change_cells(
        table, rows.index, column, [value] * len(rows.index), decision
    ):
        raise Stop(f"{decision}: setting {column!r} to {value!r} changes nothing")


def map_values(
    table: Table,
    column: str,
    mapping: dict[str, str],
    decision: str,
    rows: RowSet | None = None,
) -> None:
    """Replace whole values exactly as listed (no partial or case-insensitive matches)."""
    table._need(column)
    ids = rows.index if rows is not None else list(table.df.index)
    if rows is not None:
        _own(table, rows)
    current = table.df.loc[ids, column]
    hit = current.isin(list(mapping))
    if not hit.any():
        raise Stop(f"{decision}: {list(mapping)} matches no value in {column!r}")
    targets = list(current.index[hit])
    _change_cells(table, targets, column, [mapping[v] for v in current[hit]], decision)


def reformat_dates(
    table: Table,
    rows: RowSet,
    column: str,
    from_format: str,
    to_format: str,
    decision: str,
) -> None:
    """Rewrite dates with explicit formats. Stops if any selected value doesn't
    match from_format."""
    _own(table, rows)
    table._need(column)
    new, bad = [], []
    for rid in rows.index:
        v = table.df.at[rid, column]
        try:
            new.append(datetime.strptime(v, from_format).strftime(to_format))
        except ValueError:
            bad.append(f"{rid.split('|')[-1]} ({v!r})")
    if bad:
        raise Stop(
            f"{decision}: {len(bad)} values in {column!r} don't match {from_format!r}: "
            + ", ".join(bad[:5])
        )
    if not _change_cells(table, rows.index, column, new, decision):
        raise Stop(f"{decision}: reformatting {column!r} changes nothing")


def add_column(
    table: Table,
    column: str,
    values: str | dict[str, str],
    decision: str,
    after: str | None = None,
) -> None:
    """Add a column: one value for every row, or a value for every ID."""
    _refuse_column(table, column, decision)
    if isinstance(values, dict):
        table._need(table.id_column)
        ids = list(table.df[table.id_column])
        unknown = [k for k in values if k not in set(ids)]
        missing = [i for i in ids if i not in values]
        if unknown:
            raise Stop(f"{decision}: no row with ID {', '.join(unknown)}")
        if missing:
            raise Stop(f"{decision}: no value given for {', '.join(missing[:10])}")
        col = [values[i] for i in ids]
    else:
        col = [values] * len(table.df)
    if after is not None:
        table._need(after)
    pos = (
        len(table.df.columns)
        if after is None
        else list(table.df.columns).index(after) + 1
    )
    table.df.insert(pos, column, col)
    table._col_ids[column] = ""
    _record(decision, "column added", table, column=column, letter="")


def rename_column(table: Table, old: str, new: str, decision: str) -> None:
    table._need(old)
    _refuse_column(table, new, decision)
    table.df = table.df.rename(columns={old: new})
    table._col_ids[new] = table._col_ids.pop(old, "")
    table._invented.discard(old)
    # The IDs stay with their column under its new name
    if table.id_column == old:
        table.id_column = new
    _record(decision, "column renamed", table, column=new, old=old, new=new)


def delete_column(table: Table, column: str, decision: str) -> None:
    table._need(column)
    _record(decision, "column deleted", table, column=column)
    table.df = table.df.drop(columns=[column])
    table._col_ids.pop(column, None)
    table._invented.discard(column)


def delete_rows(table: Table, rows: RowSet, decision: str) -> None:
    _own(table, rows)
    for rid in rows.index:
        _record(decision, "row deleted", table, rid, letter="")
    table.df = table.df.drop(index=rows.index)


def normalize_whitespace(
    table: Table, decision: str, columns: list[str] | None = None
) -> None:
    """Strip leading and trailing spaces and collapse runs of spaces to one, in
    column names and values. Unusual spaces count as spaces; zero-width
    characters are removed."""

    def clean(s: pd.Series) -> pd.Series:
        visible = s.str.replace(f"[{ZERO_WIDTH}]", "", regex=True)
        return visible.str.replace(SPACES, " ", regex=True).str.strip(" ")

    for column in columns or []:
        table._need(column)
    # Clean the names first; listed columns are then found under their new names
    names = pd.Series(list(table.df.columns))
    renamed = {}
    for old, new in zip(names, clean(names)):
        if old != new and (columns is None or old in columns):
            rename_column(table, old, new, decision)
            renamed[old] = new
    listed = [renamed.get(c, c) for c in columns] if columns is not None else None
    for column in listed or list(table.df.columns):
        col = table.df[column]
        _change_cells(table, list(col.index), column, list(clean(col)), decision)


def stack(
    tables: list[Table],
    decision: str,
    source_column: str | None = None,
    name: str = "merged",
) -> Table:
    """Put tables with the same columns and ID column one after another."""
    first = list(tables[0].df.columns)
    id_column = tables[0].id_column
    if source_column:
        _refuse_column(tables[0], source_column, decision)
    for t in tables[1:]:
        if list(t.df.columns) != first:
            diff = sorted(set(first) ^ set(t.df.columns)) or [
                "(same names, different order)"
            ]
            raise Stop(
                f"{decision}: {t.name} has different columns from {tables[0].name}: "
                + ", ".join(diff)
            )
        if t.id_column != id_column:
            raise Stop(
                f"{decision}: {t.name} has ID column {t.id_column!r}, "
                f"not {id_column!r} like {tables[0].name}"
            )
    tables[0]._need(id_column)
    ids = Counter(i for t in tables for i in t.df[id_column])
    dups = [i for i, n in ids.items() if n > 1]
    if dups:
        raise Stop(
            f"{decision}: IDs in {id_column!r} repeat across the tables: "
            + ", ".join(dups[:10])
        )
    df = pd.concat([t.df for t in tables])
    merged = Table(
        name, df=df, file=name, col_ids={c: "" for c in first}, id_column=id_column
    )
    merged.parts = list(tables)
    merged._invented = set().union(*(t._invented for t in tables))
    if source_column:
        merged.df.insert(
            len(first),
            source_column,
            [t.file for t in tables for _ in range(len(t.df))],
        )
        merged._col_ids[source_column] = ""
        _record(decision, "column added", merged, column=source_column, letter="")
    return merged


def write_stacking_report(merged: Table, written: dict[str, Path], path: Path) -> str:
    """Rows from each stacked table, the totals, and whether the combined output
    equals the per-table outputs placed one after another. written maps each
    table's name to its output file."""
    refuse_existing(path)
    # Compare the written files: one header, then every table's rows in order
    merged_lines = written[merged.name].read_text(encoding="utf-8").splitlines()
    part_lines = [
        written[p.name].read_text(encoding="utf-8").splitlines() for p in merged.parts
    ]
    expected = part_lines[0][:1] + [line for lines in part_lines for line in lines[1:]]
    same = "yes" if merged_lines == expected else "no"
    # Write the report as item/value rows
    n_rows, n_cols = len(merged.df), len(merged.df.columns)
    items = [(f"rows from {p.file}", str(len(p.df))) for p in merged.parts]
    items += [
        ("rows in total", str(n_rows)),
        ("columns", str(n_cols)),
        ("same as the per-table outputs in order", same),
    ]
    write_tsv(path, ["item", "value"], items)
    summary = (
        f"{merged.name}: {len(merged.parts)} tables stacked, {n_rows} rows, {n_cols} columns; "
        f"same as the per-table outputs in order: {same}"
    )
    return summary


# -- the decision log against this script -----------------------------------
HEADING = re.compile(r"^## (D-\d+) · \d{4}-\d{2}-\d{2} \d{2}:\d{2}\s*$")


def parse_log(path: Path) -> list[dict]:
    entries, cur = [], None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = HEADING.match(line)
        if m:
            if any(e["id"] == m.group(1) for e in entries):
                raise Stop(f"decision log has more than one entry for {m.group(1)}")
            cur = {"id": m.group(1), "changes": None, "replaces": None}
            entries.append(cur)
        elif line.startswith("## D-"):
            raise Stop(f"decision log heading not in the expected form: {line!r}")
        elif line.startswith("## "):
            cur = None
        elif cur is not None:
            m = re.match(r"^Changes data: (yes|no)\s*$", line)
            if m:
                cur["changes"] = m.group(1) == "yes"
            m = re.match(r"^Replaces: (D-\d+)\s*$", line)
            if m:
                cur["replaces"] = m.group(1)
    for e in entries:
        if e["changes"] is None:
            raise Stop(
                f"decision log entry {e['id']} has no 'Changes data: yes/no' line"
            )
    return entries


def parse_blocks(source: str) -> dict[str, bool]:
    """Block ID -> True if the block is only `pass`, from the decisions() function."""
    start = source.find("def decisions(t):")
    end = source.find("# === END OF DECISIONS ===", start)
    body = source[start : end if end != -1 else len(source)].splitlines()[1:]
    blocks, cur = {}, None
    for line in body:
        m = re.match(r"^\s+# (D-\d+)\s*$", line)
        if m:
            cur = m.group(1)
            if cur in blocks:
                raise Stop(f"decisions() has more than one block for {cur}")
            blocks[cur] = []
        elif cur and line.strip() and not line.strip().startswith("#"):
            for other in re.findall(r'decision="(D-\d+)"', line):
                if other != cur:
                    raise Stop(f'{cur} passes decision="{other}"; it must be {cur}')
            blocks[cur].append(line.strip())
    return {k: v == ["pass"] for k, v in blocks.items()}


def log_mismatches(entries: list[dict], blocks: dict[str, bool]) -> list[str]:
    out = []
    logged = {e["id"] for e in entries}
    replaced = {e["replaces"]: e["id"] for e in entries if e["replaces"]}
    out += [
        f"{e['id']} replaces {e['replaces']}, which is not in the decision log"
        for e in entries
        if e["replaces"] and e["replaces"] not in logged
    ]
    for e in entries:
        did = e["id"]
        if did not in blocks:
            out.append(f"{did} is in the decision log but has no block")
        elif did in replaced:
            if not blocks[did]:
                out.append(
                    f"{did} is replaced by {replaced[did]}, so its block must be `pass`"
                )
        elif e["changes"] and blocks[did]:
            out.append(f"{did} changes data but its block is only `pass`")
        elif not e["changes"] and not blocks[did]:
            out.append(f"{did} changes no data but its block has code")
    out += [
        f"{b} has a block but is not in the decision log"
        for b in blocks
        if b not in logged
    ]
    return out


# -- writing -----------------------------------------------------------------
def write_table(table: Table, path: Path) -> None:
    """Rows written directly: cells joined by tabs, rows ended by LF."""
    refuse_existing(path)
    # A made-up name for a repeated or blank header is never written
    invented = [table.col_id(c) for c in table.df.columns if c in table._invented]
    if invented:
        raise Stop(
            f"{table.name}: columns {', '.join(invented)} have a repeated or blank "
            "name; rename or delete them with a decision first"
        )
    rows = [list(table.df.columns)] + table.df.values.tolist()
    for r in rows:
        for v in r:
            if "\t" in v or "\n" in v or "\r" in v:
                raise Stop(
                    f"{table.name}: a value contains a tab or line break: {v[:40]!r}"
                )
    with open(path, "w", encoding="utf-8", newline="") as fh:
        for r in rows:
            fh.write("\t".join(r) + "\n")  # same-pattern-ok: refuses tabs


CHANGE_COLUMNS = [
    "decision",
    "kind",
    "file",
    "row",
    "column_letter",
    "column",
    "table_unique_id",
    "old",
    "new",
]


def write_changes(path: Path) -> None:
    refuse_existing(path)
    rows = [[c[k] for k in CHANGE_COLUMNS] for c in CHANGES]
    write_tsv(path, CHANGE_COLUMNS, rows)


def previous_draft(outdir: Path, stem: str, timestamp: str, original: Path) -> Path:
    """The newest earlier draft output of this table, or the original file."""
    earlier = sorted(
        p
        for p in Path(outdir).glob(f"{glob.escape(stem)}__draft_*.tsv")
        if p.name[len(stem) + 8 : -4] < timestamp
    )
    return earlier[-1] if earlier else original


def make_diff(diff_script: Path, previous: Path, new: Path, key: str, out: Path) -> str:
    r = subprocess.run(
        [
            "uv",
            "run",
            "--quiet",
            str(diff_script),
            str(previous),
            str(new),
            "--key",
            key,
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise Stop(
            f"diff failed for {new.name}: {r.stderr.strip() or r.stdout.strip()}"
        )
    return r.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True, type=Path)
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--timestamp", required=True)
    ap.add_argument("--decision-log", required=True, type=Path)
    ap.add_argument("--final", action="store_true")
    ap.add_argument(
        "--diff-script",
        type=Path,
        help="the skill's scripts/diff_tables.py (required for drafts)",
    )
    a = ap.parse_args(argv)
    try:
        if not a.final and a.diff_script is None:
            raise Stop(
                "a draft run needs --diff-script (the skill's scripts/diff_tables.py)"
            )
        problems = log_mismatches(
            parse_log(a.decision_log),
            parse_blocks(Path(__file__).read_text(encoding="utf-8")),
        )
        if problems:
            raise Stop(
                "the script and the decision log disagree:\n  " + "\n  ".join(problems)
            )
        no_id = [name for name in INPUTS if name not in ID_COLUMNS]
        if no_id:
            raise Stop(f"ID_COLUMNS names no ID column for {', '.join(no_id)}")
        originals = {name: a.inputs / f for name, f in INPUTS.items()}
        missing = [p.name for p in originals.values() if not p.exists()]
        if missing:
            raise Stop(f"no input file named {', '.join(missing)} in {a.inputs}")
        t = {
            name: Table(name, p, id_column=ID_COLUMNS[name])
            for name, p in originals.items()
        }
        decisions(t)
        a.outdir.mkdir(parents=True, exist_ok=True)
        tag = "cleanup" if a.final else "draft"
        written = {}
        for name, table in t.items():
            stem = Path(table.file).stem if name in originals else name
            out = a.outdir / f"{stem}__{tag}_{a.timestamp}.tsv"
            write_table(table, out)
            written[name] = (stem, out)
        write_changes(a.outdir / f"changes__{tag}_{a.timestamp}.tsv")
        print(f"{len(written)} tables written; {len(CHANGES)} changes -> {a.outdir}")
        if not a.final:
            by_table = {t[name].name: out for name, (stem, out) in written.items()}
            for name, (stem, out) in written.items():
                prev = previous_draft(
                    a.outdir, stem, a.timestamp, originals.get(name, out)
                )
                # A stacked table with no earlier draft gets a report instead of a diff
                if prev == out and getattr(t[name], "parts", None):
                    report = a.outdir / f"{stem}__stacking__draft_{a.timestamp}.tsv"
                    print(write_stacking_report(t[name], by_table, report))
                elif prev != out:
                    page = a.outdir / f"{stem}__diff__draft_{a.timestamp}.html"
                    key = t[name].id_column
                    summary = make_diff(a.diff_script, prev, out, key, page)
                    print(f"{stem}: {summary}")
    except Stop as e:
        print(f"STOPPED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
