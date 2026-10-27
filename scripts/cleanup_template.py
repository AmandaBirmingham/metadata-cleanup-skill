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

Without uv: install pandas==3.0.5 into Python >= 3.11 and run with python.
Each run starts from the original files, never writes to them, and never
overwrites an output.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

# ===========================================================================
# EDIT HERE: the input files and the decisions
# ===========================================================================
INPUTS: dict[str, str] = {}   # table name -> file name in --inputs
SAMPLE_ID = "sample_name"     # the column that identifies each sample


def decisions(t):
    """One block per decision in the decision log, in ID order, headed by the
    ID alone. A decision that changes no data is just `pass`."""
    pass

# === END OF DECISIONS ===


# ===========================================================================
# Helper layer: do not edit
# ===========================================================================
class Stop(Exception):
    """A problem that must be fixed before the script can go on."""


CHANGES: list[dict] = []   # one entry per change, in the order made


def column_letter(index0: int) -> str:
    s, i = "", index0 + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def display_name(path: Path) -> str:
    """The file name without an 8-hex-digit prefix that an upload may add."""
    return re.sub(r"^[0-9a-f]{8}-(?=\d)", "", path.name)


class Table:
    """One table: .df holds every cell as text. Rows are identified as
    "<table>|row N" (N = spreadsheet row, header = row 1); each column keeps
    its original letter, so renames don't lose track of it."""

    def __init__(self, name: str, path: str | Path | None = None, df: pd.DataFrame | None = None,
                 file: str | None = None, col_ids: dict[str, str] | None = None):
        self.name = name
        if df is not None:                      # built by stack()
            self.df, self.file, self._col_ids = df, file or name, dict(col_ids or {})
            return
        path = Path(path)
        self.path, self.file = path, display_name(path)
        raw = path.read_bytes()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            raise Stop(f"{self.file} is not valid UTF-8; converting it is a decision to make first")
        tsv = path.suffix.lower() != ".csv"
        # Count each row's cells first: pandas silently pads short rows.
        text = raw.decode("utf-8-sig")
        records = ([l.rstrip("\r").split("\t") for l in text.split("\n") if l != ""] if tsv
                   else [r for r in csv.reader(io.StringIO(text, newline=""))])
        for i, r in enumerate(records[1:], start=2):
            if len(r) != len(records[0]):
                raise Stop(f"{self.file}: row {i} has {len(r)} cells but the header has "
                           f"{len(records[0])}; fix the file first")
        try:
            df = pd.read_csv(io.BytesIO(raw), sep="\t" if tsv else ",", header=None, dtype=str,
                             keep_default_na=False, na_filter=False, encoding="utf-8-sig",
                             quoting=csv.QUOTE_NONE if tsv else csv.QUOTE_MINIMAL)
        except pd.errors.ParserError as e:
            raise Stop(f"{self.file}: a row has more cells than the header ({e}); fix the file first")
        if df.isna().any().any():
            bad = df.index[df.isna().any(axis=1)][0] + 1
            raise Stop(f"{self.file}: row {bad} has fewer cells than the header; fix the file first")
        header = list(df.iloc[0])
        seen = Counter(header)
        names = [h if h.strip() and (seen[h] == 1 or i == header.index(h))
                 else (f"{h} [col {column_letter(i)}]" if h.strip() else f"[col {column_letter(i)}]")
                 for i, h in enumerate(header)]
        df = df.iloc[1:].copy()
        df.columns = names
        df.index = [f"{name}|row {i}" for i in range(2, len(df) + 2)]
        self.df = df
        self._col_ids = {n: column_letter(i) for i, n in enumerate(names)}

    def col_id(self, column: str) -> str:
        return self._col_ids.get(column, "")

    def _need(self, column: str) -> None:
        if column not in self.df.columns:
            raise Stop(f"{self.name}: no column named {column!r}")

    def sample(self, row_id: str) -> str:
        return self.df.at[row_id, SAMPLE_ID] if SAMPLE_ID in self.df.columns else ""


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
        known = set(table.df[SAMPLE_ID])
        missing = [i for i in ids if i not in known]
        if missing:
            raise Stop(f"{table.name}: no sample with ID {', '.join(missing)}")
        mask &= table.df[SAMPLE_ID].isin(ids)
    for column, cond in conditions.items():
        if column not in table.df.columns:
            raise Stop(f"{table.name}: no column named {column!r}")
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
    a function of the value, or ids=[sample IDs]. Stops if nothing matches."""
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
    CHANGES.append({
        "decision": decision, "kind": kind, "file": table.file,
        "row": row_id.rsplit("row ", 1)[-1] if row_id else "",
        "column_letter": table.col_id(column) if letter is None else letter,
        "column": column, "sample_id": table.sample(row_id) if row_id else "",
        "old": old, "new": new})


def _own(table: Table, rows: RowSet) -> None:
    if rows.table is not table:
        raise Stop(f"these rows were selected from another table ({rows.table.name}), not {table.name}")


def _change_cells(table: Table, row_ids, column: str, new_values, decision: str) -> int:
    n = 0
    for rid, new in zip(row_ids, new_values):
        old = table.df.at[rid, column]
        if old != new:
            table.df.at[rid, column] = new
            _record(decision, "value changed", table, rid, column, old, new)
            n += 1
    return n


def set_value(table: Table, rows: RowSet, column: str, value: str, decision: str) -> None:
    _own(table, rows)
    table._need(column)
    if not _change_cells(table, rows.index, column, [value] * len(rows.index), decision):
        raise Stop(f"{decision}: setting {column!r} to {value!r} changes nothing")


def map_values(table: Table, column: str, mapping: dict[str, str], decision: str,
               rows: RowSet | None = None) -> None:
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


def reformat_dates(table: Table, rows: RowSet, column: str, from_format: str, to_format: str,
                   decision: str) -> None:
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
        raise Stop(f"{decision}: {len(bad)} values in {column!r} don't match {from_format!r}: "
                   + ", ".join(bad[:5]))
    _change_cells(table, rows.index, column, new, decision)


def add_column(table: Table, column: str, values: str | dict[str, str], decision: str,
               after: str | None = None) -> None:
    """Add a column: one value for every row, or a value for every sample ID."""
    if column in table.df.columns:
        raise Stop(f"{decision}: {table.name} already has a column named {column!r}")
    ids = list(table.df[SAMPLE_ID])
    if isinstance(values, dict):
        unknown = [k for k in values if k not in set(ids)]
        missing = [i for i in ids if i not in values]
        if unknown:
            raise Stop(f"{decision}: no sample with ID {', '.join(unknown)}")
        if missing:
            raise Stop(f"{decision}: no value given for {', '.join(missing[:10])}")
        col = [values[i] for i in ids]
    else:
        col = [values] * len(ids)
    pos = len(table.df.columns) if after is None else list(table.df.columns).index(after) + 1
    table.df.insert(pos, column, col)
    table._col_ids[column] = ""
    _record(decision, "column added", table, column=column, letter="")


def rename_column(table: Table, old: str, new: str, decision: str) -> None:
    table._need(old)
    if new in table.df.columns:
        raise Stop(f"{decision}: {table.name} already has a column named {new!r}")
    table.df = table.df.rename(columns={old: new})
    table._col_ids[new] = table._col_ids.pop(old, "")
    _record(decision, "column renamed", table, column=new, old=old, new=new)


def delete_column(table: Table, column: str, decision: str) -> None:
    table._need(column)
    _record(decision, "column deleted", table, column=column)
    table.df = table.df.drop(columns=[column])
    table._col_ids.pop(column, None)


def delete_rows(table: Table, rows: RowSet, decision: str) -> None:
    _own(table, rows)
    for rid in rows.index:
        _record(decision, "row deleted", table, rid, letter="")
    table.df = table.df.drop(index=rows.index)


SPACES = r"[ \u00a0]+"


def normalize_whitespace(table: Table, decision: str, columns: list[str] | None = None) -> None:
    """Strip leading and trailing spaces and collapse runs of spaces (including
    non-breaking spaces) to one, in column names and values."""
    def clean(s: pd.Series) -> pd.Series:
        return s.str.replace(SPACES, " ", regex=True).str.strip(" ")
    names = pd.Series(list(table.df.columns))
    for old, new in zip(names, clean(names)):
        if old != new and (columns is None or old in columns):
            rename_column(table, old, new, decision)
    for column in (columns or list(table.df.columns)):
        col = table.df[column]
        _change_cells(table, list(col.index), column, list(clean(col)), decision)


def stack(tables: list[Table], decision: str, source_column: str | None = None,
          name: str = "merged") -> Table:
    """Put tables with the same columns one after another."""
    first = list(tables[0].df.columns)
    for t in tables[1:]:
        if list(t.df.columns) != first:
            diff = sorted(set(first) ^ set(t.df.columns)) or ["(same names, different order)"]
            raise Stop(f"{decision}: {t.name} has different columns from {tables[0].name}: "
                       + ", ".join(diff))
    ids = Counter(i for t in tables for i in t.df[SAMPLE_ID])
    dups = [i for i, n in ids.items() if n > 1]
    if dups:
        raise Stop(f"{decision}: sample IDs repeat across the tables: {', '.join(dups[:10])}")
    df = pd.concat([t.df for t in tables])
    merged = Table(name, df=df, file=name, col_ids={c: "" for c in first})
    if source_column:
        merged.df.insert(len(first), source_column, [t.file for t in tables for _ in range(len(t.df))])
        merged._col_ids[source_column] = ""
        _record(decision, "column added", merged, column=source_column, letter="")
    return merged


# -- the decision log against this script -----------------------------------
HEADING = re.compile(r"^## (D-\d+) · \d{4}-\d{2}-\d{2} \d{2}:\d{2}\s*$")


def parse_log(path: Path) -> list[dict]:
    entries, cur = [], None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = HEADING.match(line)
        if m:
            cur = {"id": m.group(1), "changes": None, "replaces": None}
            entries.append(cur)
        elif line.startswith("## D-"):
            raise Stop(f"decision log heading not in the expected form: {line!r}")
        elif cur is not None:
            m = re.match(r"^Changes data: (yes|no)\s*$", line)
            if m:
                cur["changes"] = m.group(1) == "yes"
            m = re.match(r"^Replaces: (D-\d+)\s*$", line)
            if m:
                cur["replaces"] = m.group(1)
    for e in entries:
        if e["changes"] is None:
            raise Stop(f"decision log entry {e['id']} has no 'Changes data: yes/no' line")
    return entries


def parse_blocks(source: str) -> dict[str, bool]:
    """Block ID -> True if the block is only `pass`, from the decisions() function."""
    start = source.find("def decisions(t):")
    end = source.find("# === END OF DECISIONS ===", start)
    body = source[start:end if end != -1 else len(source)].splitlines()[1:]
    blocks, cur = {}, None
    for line in body:
        m = re.match(r"^\s+# (D-\d+)\s*$", line)
        if m:
            cur = m.group(1)
            blocks[cur] = []
        elif cur and line.strip() and not line.strip().startswith("#"):
            blocks[cur].append(line.strip())
    return {k: v == ["pass"] for k, v in blocks.items()}


def log_mismatches(entries: list[dict], blocks: dict[str, bool]) -> list[str]:
    out = []
    replaced = {e["replaces"]: e["id"] for e in entries if e["replaces"]}
    for e in entries:
        did = e["id"]
        if did not in blocks:
            out.append(f"{did} is in the decision log but has no block")
        elif did in replaced:
            if not blocks[did]:
                out.append(f"{did} is replaced by {replaced[did]}, so its block must be `pass`")
        elif e["changes"] and blocks[did]:
            out.append(f"{did} changes data but its block is only `pass`")
        elif not e["changes"] and not blocks[did]:
            out.append(f"{did} changes no data but its block has code")
    logged = {e["id"] for e in entries}
    out += [f"{b} has a block but is not in the decision log" for b in blocks if b not in logged]
    return out


# -- writing -----------------------------------------------------------------
def write_table(table: Table, path: Path) -> None:
    """Rows written directly: cells joined by tabs, rows ended by LF."""
    if path.exists():
        raise Stop(f"{path} already exists; never overwrite an output")
    rows = [list(table.df.columns)] + table.df.values.tolist()
    for r in rows:
        for v in r:
            if "\t" in v or "\n" in v or "\r" in v:
                raise Stop(f"{table.name}: a value contains a tab or line break: {v[:40]!r}")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        for r in rows:
            fh.write("\t".join(r) + "\n")


CHANGE_COLUMNS = ["decision", "kind", "file", "row", "column_letter", "column", "sample_id", "old", "new"]


def write_changes(path: Path) -> None:
    if path.exists():
        raise Stop(f"{path} already exists; never overwrite an output")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("\t".join(CHANGE_COLUMNS) + "\n")
        for c in CHANGES:
            fh.write("\t".join(str(c[k]).replace("\t", "\\t").replace("\n", "\\n")
                               for k in CHANGE_COLUMNS) + "\n")


def previous_draft(outdir: Path, stem: str, timestamp: str, original: Path) -> Path:
    """The newest earlier draft output of this table, or the original file."""
    earlier = sorted(p for p in Path(outdir).glob(f"{stem}__draft_*.tsv")
                     if p.name[len(stem) + 8:-4] < timestamp)
    return earlier[-1] if earlier else original


def make_diff(diff_script: Path, previous: Path, new: Path, key: str, out: Path) -> str:
    r = subprocess.run(["uv", "run", "--quiet", str(diff_script), str(previous), str(new),
                        "--key", key, "--out", str(out)], capture_output=True, text=True)
    if r.returncode != 0:
        raise Stop(f"diff failed for {new.name}: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def find_input(inputs: Path, name: str) -> Path:
    exact = inputs / name
    if exact.exists():
        return exact
    found = [p for p in inputs.iterdir() if p.name.endswith(name)]
    if len(found) != 1:
        raise Stop(f"expected one file named {name!r} in {inputs}, found {len(found)}")
    return found[0]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True, type=Path)
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--timestamp", required=True)
    ap.add_argument("--decision-log", required=True, type=Path)
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--diff-script", type=Path, help="the skill's scripts/diff_tables.py (drafts only)")
    a = ap.parse_args(argv)
    try:
        problems = log_mismatches(parse_log(a.decision_log),
                                  parse_blocks(Path(__file__).read_text(encoding="utf-8")))
        if problems:
            raise Stop("the script and the decision log disagree:\n  " + "\n  ".join(problems))
        originals = {name: find_input(a.inputs, f) for name, f in INPUTS.items()}
        t = {name: Table(name, p) for name, p in originals.items()}
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
        if not a.final and a.diff_script:
            for name, (stem, out) in written.items():
                prev = previous_draft(a.outdir, stem, a.timestamp, originals.get(name, out))
                if prev != out:
                    page = a.outdir / f"{stem}__diff__draft_{a.timestamp}.html"
                    print(f"{stem}: {make_diff(a.diff_script, prev, out, SAMPLE_ID, page)}")
    except Stop as e:
        print(f"STOPPED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
