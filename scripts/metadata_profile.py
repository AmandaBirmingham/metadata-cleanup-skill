"""Generic part of the check script: column profile and generic checks.

Imported by a study's check script. Needs frictionless==5.19.1 (declare it in
the check script's dependency block); structural checks (ragged and blank
rows, blank and duplicate column names, duplicate rows, truncated values) are
done by frictionless, run with quoting off and every column read as text.

    import sys; sys.path.insert(0, "<skill>/scripts")
    from metadata_profile import CheckRun

    run = CheckRun(["batch1.tsv", "batch2.tsv"], sample_id="sample_name",
                   as_of="2026-10-22")
    run.generic_checks()

    @run.check("X-01", "control whose material says sea water")
    def _(table):
        for row in table.rows:
            if row["sample_type"] == "control" and row["env_material"] == "sea water":
                yield row, "env_material"

    run.write("outputs", "20261022-101500")   # profile_<ts>.html, findings_<ts>.tsv

A check is a function of one table that yields hits:
    (row, column)             a value in one cell
    (row, column, note)
    (None, column, note)      something about a whole column or the table
"column" may be None, a column name, or several names joined by " = ".

Reading: TSV files are read with every cell exactly as written (rows split on
LF, cells on TAB; quote characters kept). CSV files are parsed the standard
way, since quotes are part of the CSV format. Nothing is converted.
"""

from __future__ import annotations

import csv
import difflib
import html
import io
import re
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable

import frictionless
from frictionless import Schema, fields as fl_fields, formats

NULL_TERMS = {"not provided", "not applicable", "not collected", "restricted access",
              "missing: control sample"}
NAN_LIKE = {"nan", "NaN", "NAN", "None", "NULL", "null", "NA", "N/A", "n/a", "#N/A"}
UNUSUAL_SPACE = re.compile("[\u00a0\u1680\u2000-\u200b\u202f\u205f\u3000\ufeff]")
MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
GENE_DATE = re.compile(rf"(\d{{1,2}}-({MONTHS})|({MONTHS})-\d{{1,2}})", re.I)
# Columns whose names mark them as labels (identifiers, codes), never numbers.
# A name matches when one of its parts (split at _ - . spaces and camelCase)
# is one of these words, so "sample_id" and "shipping_number" match but
# "humidity" and "acidity" don't.
LABEL_WORDS = {"id", "ids", "identifier", "identifiers", "taxid", "uuid", "guid", "uid",
               "number", "code", "barcode", "lot", "accession"}


def is_label_name(name: str) -> bool:
    parts = re.split(r"[\s_\-.]+|(?<=[a-z])(?=[A-Z])", name)
    return any(p.lower() in LABEL_WORDS for p in parts if p)


KINDS = ("numeric", "categorical", "date/time", "identifier", "free text")
PARTIAL_DATE = re.compile(r"\d{4}(-\d{2})?")
NUMBER = re.compile(r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?")
DATE_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S",
                "%m/%d/%Y %H:%M", "%m/%d/%y %H:%M", "%m/%d/%Y", "%m/%d/%y",
                "%d.%m.%Y", "%Y-%m", "%Y"]
PII_COLUMN = re.compile(
    r"(^|_)(first_?name|last_?name|full_?name|sur_?name|given_?name|patient_?name|"
    r"participant_?name|initials|ssn|social_?security|mrn|medical_?record|dob|bday|"
    r"date_?of_?birth|birth_?date|birthday|street|address|zip_?code|zip|postal_?code|"
    r"phone|telephone|mobile|fax|e_?mail|passport|driver|license|licence|insurance|"
    r"account_?number|ip_?address)($|_)", re.I)
PII_VALUE = [
    ("SSN pattern", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("phone number pattern", re.compile(r"\(\d{3}\)\s*\d{3}-\d{4}|\b\d{3}[-.]\d{3}[-.]\d{4}\b")),
    ("email address", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
]
RANGE_SUGGESTIONS = [  # (column-name pattern, low, high, reason) -- suggestions only
    (re.compile(r"(^|_)age($|_)", re.I), 0, 90, "age 0 or over 90 is unusual; over 89 is a HIPAA identifier"),
    (re.compile(r"(^|_)(bmi|body_mass_index)($|_)", re.I), 14, 60, "BMI below 14 or above 60 is implausible"),
    (re.compile(r"(depth|volume|concentration|conc|weight|height|mass)", re.I), 0, None,
     "negative values are impossible"),
]


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
def column_letter(index0: int) -> str:
    s, i = "", index0 + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def display_name(path: Path) -> str:
    """The file name without an 8-hex-digit prefix that an upload may add."""
    return re.sub(r"^[0-9a-f]{8}-(?=\d)", "", path.name)


class Row(dict):
    """One data row: column -> value, plus .line (spreadsheet row, header = 1)."""
    line: int
    cells: list[str]


class Table:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.name = display_name(self.path)
        self.kind = "csv" if self.path.suffix.lower() == ".csv" else "tsv"
        raw = self.path.read_bytes()
        self.bom = raw.startswith(b"\xef\xbb\xbf")
        try:
            self.text = raw.decode("utf-8-sig")
            self.utf8 = True
        except UnicodeDecodeError:
            self.text = raw.decode("latin-1")
            self.utf8 = False
        self.crlf_lines = self.text.count("\r\n")
        if self.kind == "csv":
            records = list(csv.reader(io.StringIO(self.text, newline="")))
        else:
            lines = self.text.split("\n")
            if lines and lines[-1] == "":
                lines = lines[:-1]
            records = [(l[:-1] if l.endswith("\r") else l).split("\t") for l in lines]
        self.header = records[0] if records else []
        # Column keys: the column name, made unique where names repeat or are
        # blank ("status [col C]", "[col D]"), so no column is lost.
        seen = Counter(self.header)
        self.keys = [c if (c.strip() and seen[c] == 1) or (c.strip() and i == self.header.index(c))
                     else (f"{c} [col {column_letter(i)}]" if c.strip() else f"[col {column_letter(i)}]")
                     for i, c in enumerate(self.header)]
        self.index = {k: i for i, k in enumerate(self.keys)}
        self.kinds: dict[str, str] = {}   # the scientist's corrections, set by CheckRun
        self.rows: list[Row] = []
        for i, cells in enumerate(records[1:], start=2):
            row = Row(zip(self.keys, cells + [""] * (len(self.keys) - len(cells))))
            row.line, row.cells = i, cells
            self.rows.append(row)

    def letter(self, column: str) -> str:
        return column_letter(self.index[column]) if column in self.index else ""

    def values(self, column: str) -> list[str]:
        return [r.get(column, "") for r in self.rows]


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------
def is_null(v: str) -> bool:
    return v == "" or v in NULL_TERMS


def as_number(v: str):
    return float(v) if NUMBER.fullmatch(v.strip()) else None


def parse_date(v: str):
    v = v.strip()
    if v.isdigit() and not (len(v) == 4 and 1800 <= int(v) <= 2100):
        return None, None          # bare numbers count only as plausible years
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(v.strip(), f), f
        except ValueError:
            pass
    return None, None


def shape(v: str) -> str:
    return re.sub(r"[A-Za-z]", "a", re.sub(r"\d", "9", v))


def column_kind(values: list[str], name: str = "") -> str:
    """A guess, shown as a guess: numeric, date, categorical, identifier, free text.
    A column whose name marks it as a label (is_label_name) is never numeric."""
    vals = [v for v in values if not is_null(v)]
    if not vals:
        return "empty or null only"
    n, distinct = len(vals), len(set(vals))
    numeric = sum(as_number(v) is not None for v in vals) >= 0.9 * n
    if is_label_name(name):
        if distinct <= 20 or distinct <= 0.05 * n:
            return "categorical (numbers)" if numeric else "categorical"
        return "identifier"
    if numeric:
        return "categorical (numbers)" if distinct <= 20 and n >= 2 * distinct else "numeric"
    if sum(parse_date(v)[0] is not None for v in vals) >= 0.9 * n:
        return "date/time"
    if distinct <= 20 or distinct <= 0.05 * n:
        return "categorical"
    if max(len(v) for v in vals) <= 40 and not any(" " in v for v in vals[:200]):
        return "identifier"
    return "free text"


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------
Check = Callable[["Table"], Iterable[tuple]]


class CheckRun:
    def __init__(self, paths: list[str | Path], sample_id: str, as_of: str | None = None,
                 kinds: dict[str, str] | None = None):
        """kinds: the scientist's corrections to the guessed column kinds, for this
        dataset only, e.g. {"station": "categorical"}. Kept in the study's check
        script, so they apply every time the profile is remade."""
        self.tables = [Table(p) for p in paths]
        self.sample_id = sample_id
        self.as_of = datetime.strptime(as_of, "%Y-%m-%d").date() if as_of else None
        self.checks: list[tuple[str, str, Check]] = []
        self.kinds = dict(kinds or {})
        known = {k for t in self.tables for k in t.keys}
        for col, kind in self.kinds.items():
            if col not in known:
                raise ValueError(f"kinds: no column named {col!r} in these files")
            if kind not in KINDS:
                raise ValueError(f"kinds: {kind!r} for {col!r} is not one of {', '.join(KINDS)}")
        for t in self.tables:
            t.kinds = self.kinds

    # -- registering checks -------------------------------------------------
    def check(self, cid: str, description: str):
        if any(c[0] == cid for c in self.checks):
            raise ValueError(f"check ID {cid} is already used")

        def deco(fn: Check) -> Check:
            self.checks.append((cid, description, fn))
            return fn
        return deco

    def add(self, cid: str, description: str, fn: Check) -> None:
        self.check(cid, description)(fn)

    def generic_checks(self) -> None:
        for cid, description, fn in GENERIC_CHECKS:
            self.add(cid, description, fn)

    def suggest_range_columns(self) -> list[tuple[str, float | None, float | None, str]]:
        """Columns whose names suggest a plausible range. For the agent to ASK the
        scientist about; nothing is checked until range_check() is called."""
        out, seen = [], set()
        for t in self.tables:
            for c in t.keys:
                if re.search(r"units?$", c, re.I):
                    continue
                for pat, lo, hi, why in RANGE_SUGGESTIONS:
                    if c not in seen and pat.search(c):
                        out.append((c, lo, hi, why))
                        seen.add(c)
                        break
        return out

    def range_check(self, column: str, low: float | None = None, high: float | None = None,
                    cid: str | None = None) -> None:
        """Flag numeric values below low or above high (only after the scientist agrees)."""
        cid = cid or f"R-{column}"
        bounds = " or ".join(x for x in [f"below {low}" if low is not None else "",
                                          f"above {high}" if high is not None else ""] if x)

        def fn(t: Table):
            if column not in t.index:
                return
            for r in t.rows:
                x = as_number(r[column])
                if x is not None and ((low is not None and x < low) or (high is not None and x > high)):
                    yield r, column
        self.add(cid, f"{column} {bounds}", fn)

    def stage9_checks(self, required: list[str] | None = None,
                      expected_rows: dict[str, int] | None = None) -> None:
        """Stage 9 (final validation), run on the latest draft outputs."""
        self.add("S9-01", "empty or NaN-like value", _s9_empty)
        if required:
            def fn(t: Table):
                for c in required:
                    if c not in t.index:
                        yield None, c, "required column missing"
                        continue
                    for r in t.rows:
                        if r[c] == "" or r[c] in NAN_LIKE:
                            yield r, c
            self.add("S9-02", "required field not filled", fn)
        if expected_rows:
            def fn(t: Table):
                exp = expected_rows.get(t.name)
                if exp is not None and exp != len(t.rows):
                    yield None, None, f"{len(t.rows)} data rows; expected {exp}"
            self.add("S9-03", "row count differs from the expected count", fn)

    # -- running and writing ------------------------------------------------
    def run(self) -> list[tuple]:
        hits = []
        for cid, description, fn in self.checks:
            found = 0
            for t in self.tables:
                for hit in fn(t) or ():
                    row, column = hit[0], hit[1]
                    note = hit[2] if len(hit) > 2 else ""
                    found += 1
                    hits.append(self._finding(cid, description, t, row, column, note))
            if cid in CROSS_TABLE:
                for hit in CROSS_TABLE[cid](self):
                    t, row, column, note = hit
                    found += 1
                    hits.append(self._finding(cid, description, t, row, column, note))
            if not found:
                hits.append((cid, description, "", "", "", "", "", "", "no findings"))
        return hits

    def _finding(self, cid, description, t, row, column, note):
        cols = column.split(" = ") if column else []
        letters = ", ".join(t.letter(c) for c in cols if t.letter(c))
        value = row.get(column, "") if (row is not None and column in (row or {})) else ""
        sample = row.get(self.sample_id, "") if row is not None else ""
        return (cid, description, t.name, str(row.line) if row is not None else "",
                letters, column or "", sample, value, note)

    def write(self, outdir: str | Path, timestamp: str) -> tuple[Path, Path]:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        fpath, ppath = outdir / f"findings_{timestamp}.tsv", outdir / f"profile_{timestamp}.html"
        for p in (fpath, ppath):
            if p.exists():
                raise FileExistsError(f"{p} already exists; choose a new timestamp")
        hits = self.run()
        header = ["check", "description", "file", "spreadsheet_row", "column_letter", "column",
                  "sample_id", "value", "note"]
        with open(fpath, "w", encoding="utf-8", newline="") as fh:
            fh.write("\t".join(header) + "\n")
            for h in hits:
                fh.write("\t".join(_one_line(str(x)) for x in h) + "\n")
        ppath.write_text(render_profile(self), encoding="utf-8")
        counts = Counter(h[0] for h in hits if h[8] != "no findings")
        for cid, description, _ in self.checks:
            print(f"{cid}\t{counts.get(cid, 0)}\t{description}")
        print(f"-> {fpath}\n-> {ppath}")
        return fpath, ppath


def _one_line(v: str) -> str:
    """Findings are TSV: show tabs and line breaks inside a value visibly."""
    return v.replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")


# ---------------------------------------------------------------------------
# Generic checks
# ---------------------------------------------------------------------------
def _s0_utf8(t):
    if not t.utf8:
        yield None, None, "not valid UTF-8; read as Latin-1 to continue"


def _s0_bom(t):
    if t.bom:
        yield None, None, "file starts with a UTF-8 byte-order mark"


def frictionless_errors(t) -> list[tuple[str, int | None, int | None, str]]:
    """Structural errors found by frictionless, once per table:
    (type, row number with header = 1, column number from 1, note).
    TSV is read with quoting off (quote_char is a character that never occurs),
    and every column is declared as text so nothing is type-checked."""
    if getattr(t, "_fl_errors", None) is None:
        control = (formats.CsvControl(delimiter="\t", quote_char="\x01") if t.kind == "tsv"
                   else formats.CsvControl())
        encoding = "utf-8-sig" if t.utf8 else "latin-1"
        # frictionless refuses absolute paths ("unsafe"), so open the file by name
        # from its own folder
        p = Path(t.path).resolve()
        res = frictionless.Resource(p.name, basepath=str(p.parent), format="csv",
                                    control=control, encoding=encoding)
        res.infer()
        res.schema = Schema(fields=[fl_fields.StringField(name=f.name or f"field{i + 1}")
                                    for i, f in enumerate(res.schema.fields)])
        report = frictionless.validate(res, limit_errors=10**7, checks=[
            frictionless.checks.duplicate_row(), frictionless.checks.truncated_value()])
        errors = [tuple(e) for e in report.flatten(["type", "rowNumber", "fieldNumber", "note"])]
        failed = [e for e in errors if e[1] is None and e[2] is None]
        if failed:   # an error about the file itself: frictionless could not check it
            raise RuntimeError(f"frictionless could not check {t.name}: {failed[0][0]} {failed[0][3]}")
        t._fl_errors = errors
    return t._fl_errors


def _row_at(t, line):
    return next((r for r in t.rows if r.line == line), None)


def _s0_ragged(t):
    lines = sorted({row for kind, row, _, _ in frictionless_errors(t)
                    if kind in ("missing-cell", "extra-cell") and row})
    for line in lines:
        r = _row_at(t, line)
        if r is not None:
            yield r, None, f"{len(r.cells)} cells; header has {len(t.header)}"


def _s0_blank_rows(t):
    for kind, line, _, _ in frictionless_errors(t):
        if kind == "blank-row" and _row_at(t, line) is not None:
            yield _row_at(t, line), None


def _blank_label_keys(t):
    return [t.keys[col - 1] for kind, _, col, _ in frictionless_errors(t)
            if kind == "blank-label" and col and col <= len(t.keys)]


def _s0_blank_columns(t):
    for c in _blank_label_keys(t):
        if all(v.strip() == "" for v in t.values(c)):
            yield None, c, "no header and no values"


def _s0_duplicate_rows(t):
    for kind, line, _, note in frictionless_errors(t):
        if kind == "duplicate-row" and _row_at(t, line) is not None:
            yield _row_at(t, line), None, note


def _s0_quotes(t):
    if t.kind != "tsv":
        return
    parsed = list(csv.reader(io.StringIO(t.text, newline=""), delimiter="\t"))[1:]
    if len(parsed) != len(t.rows):
        yield None, None, (f"read CSV-style, the file has {len(parsed)} data rows instead of "
                           f"{len(t.rows)}: quote characters span cells or lines")
        return
    for r, cells in zip(t.rows, parsed):
        if len(cells) != len(r.cells):
            yield r, None, (f"read CSV-style, this row has {len(cells)} cells instead of "
                            f"{len(r.cells)}: a quote wraps a tab")
            continue
        for c, a, b in zip(t.keys, r.cells, cells):
            if a.rstrip("\r") != b.rstrip("\r"):
                yield r, c, f"read CSV-style: {b}"


def _s1_breaks(t):
    for r in t.rows:
        for c, v in r.items():
            if "\t" in v or "\n" in v or ("\r" in v and t.kind == "csv"):
                yield r, c


def _s1_spaces(t):
    for c in t.header:
        if c != c.strip() or "  " in c:
            yield None, c, "column name has leading, trailing or doubled spaces"
    for r in t.rows:
        for c, v in r.items():
            v = v.rstrip("\r")
            if v != v.strip(" ") or "  " in v:
                yield r, c


def _s1_unusual(t):
    for c in t.header:
        if UNUSUAL_SPACE.search(c):
            yield None, c, "column name contains an unusual space character"
    for r in t.rows:
        for c, v in r.items():
            m = UNUSUAL_SPACE.search(v)
            if m:
                yield r, c, f"contains U+{ord(m.group()):04X}"


def _s1_crlf(t):
    if t.crlf_lines:
        yield None, None, f"{t.crlf_lines} rows end in CRLF"


def _s2_duplicates(t):
    dup_cols = {col for kind, _, col, _ in frictionless_errors(t) if kind == "duplicate-label" and col}
    names = {t.header[col - 1] for col in dup_cols if col <= len(t.header)}
    for c in sorted(names):
        letters = ", ".join(column_letter(i) for i, h in enumerate(t.header) if h == c)
        n = t.header.count(c)
        yield None, None, f"{n} columns are named {c!r} (columns {letters})"


def _s2_empty_names(t):
    for c in _blank_label_keys(t):
        if any(v.strip() for v in t.values(c)):
            yield None, c, "column has no name but has values"


def _s3_truncated(t):
    for kind, line, col, note in frictionless_errors(t):
        if kind == "truncated-value" and col and _row_at(t, line) is not None:
            yield _row_at(t, line), t.keys[col - 1], note


def _pairs(t, test):
    cols = [k for name, k in zip(t.header, t.keys) if name.strip()]
    if len(cols) > 300:
        return
    vals = {c: t.values(c) for c in cols}
    null_only = {c for c in cols if all(is_null(v) for v in vals[c])}
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            if a in null_only and b in null_only:
                continue           # matching only because both are empty (see S3-04)
            note = test(vals[a], vals[b])
            if note is not None:
                yield None, f"{a} = {b}", note


def _s3_identical(t):
    yield from _pairs(t, lambda x, y: "" if x == y else None)


def _s3_case_only(t):
    yield from _pairs(t, lambda x, y: "" if x != y and [v.lower() for v in x] == [v.lower() for v in y] else None)


def _s3_mostly_identical(t):
    def test(x, y):
        n = sum(a == b for a, b in zip(x, y))
        real = sum(a == b and not is_null(a) for a, b in zip(x, y))
        if 0.95 * len(x) <= n < len(x) and real >= 0.5 * n:   # not just shared nulls
            rows = [str(r.line) for r, a, b in zip(t.rows, x, y) if a != b]
            return f"{len(x) - n} rows differ: rows {', '.join(rows[:20])}" + (" ..." if len(rows) > 20 else "")
        return None
    yield from _pairs(t, test)


def _s3_null_only(t):
    for name, c in zip(t.header, t.keys):
        vals = t.values(c)
        if name.strip() and vals and all(is_null(v) for v in vals):
            yield None, c, " / ".join(sorted(set(vals))) or "empty"


def _s3_pii_name(t):
    for c in t.header:
        if PII_COLUMN.search(c):
            yield None, c, "column name suggests PII or PHI (see pii.md)"


def _s3_pii_value(t):
    """One finding per column and pattern, with the count and example rows."""
    found = defaultdict(list)
    for r in t.rows:
        for c, v in r.items():
            for label, pat in PII_VALUE:
                if pat.search(v):
                    found[(c, label)].append(r)
                    break
            else:
                if re.fullmatch(r"\d{10}", v):
                    found[(c, "10-digit number (phone number?)")].append(r)
                elif re.fullmatch(r"\d{6}|\d{8}", v) and _date_like_digits(v):
                    found[(c, "6- or 8-digit number that reads as a date")].append(r)
    for (c, label), rows in found.items():
        if len(rows) == 1:
            yield rows[0], c, label
        else:
            eg = ", ".join(str(r.line) for r in rows[:5])
            yield None, c, f"{label}: {len(rows)} values, e.g. rows {eg}" + (" ..." if len(rows) > 5 else "")


def _date_like_digits(v: str) -> bool:
    fmts = ["%d%m%y", "%m%d%y", "%y%m%d"] if len(v) == 6 else ["%Y%m%d", "%d%m%Y", "%m%d%Y"]
    for f in fmts:
        try:
            d = datetime.strptime(v, f)
            if 1900 <= d.year <= 2100:
                return True
        except ValueError:
            pass
    return False


def _date_columns(t):
    for c in t.keys:
        vals = [v for v in t.values(c) if not is_null(v)]
        if vals and sum(parse_date(v)[0] is not None for v in vals) >= 0.5 * len(vals):
            yield c


def _s3_gene_dates(t):
    dates = set(_date_columns(t))
    for r in t.rows:
        for c, v in r.items():
            if c not in dates and GENE_DATE.fullmatch(v.strip()):
                yield r, c, "looks like a gene name converted to a date"


def _date_format(v: str) -> str:
    """The date format a value is written in (e.g. %m/%d/%y), or its shape if none."""
    return parse_date(v)[1] or f"unrecognised ({shape(v)})"


def _s3_mixed_dates(t):
    for c in _date_columns(t):
        vals = [v for v in t.values(c) if not is_null(v) and not PARTIAL_DATE.fullmatch(v.strip())]
        if not vals:
            continue
        common = Counter(_date_format(v) for v in vals).most_common(1)[0][0]
        for r in t.rows:
            v = r[c]
            if v in vals and _date_format(v) != common:
                yield r, c, f"written as {_date_format(v)}; most of the column is {common}"


def _s3_partial_dates(t):
    for c in _date_columns(t):
        for r in t.rows:
            if PARTIAL_DATE.fullmatch(r[c].strip()):
                yield r, c, "year or year-month only"


def _s3_heaping(t):
    for c in t.keys:
        if t.kinds.get(c, "numeric" if not is_label_name(c) else "") != "numeric":
            continue
        nums = [as_number(v) for v in t.values(c) if not is_null(v)]
        nums = [x for x in nums if x is not None]
        if len(nums) >= 20 and len(set(nums)) >= 5:
            share = sum(x % 5 == 0 for x in nums) / len(nums)
            if share >= 0.5:
                yield None, c, f"{share:.0%} of values are multiples of 5"


SCI_NOTATION = re.compile(r"[-+]?\d+(\.\d+)?[eE][-+]?\d+")


def _s3_scientific(t):
    for r in t.rows:
        for c, v in r.items():
            if SCI_NOTATION.fullmatch(v.strip()):
                yield r, c, "written in scientific notation (spreadsheet damage?): digits may have been lost"


def _s3_leading_zeros(t):
    for c in t.keys:
        vals = [v for v in t.values(c) if not is_null(v)]
        if vals and sum(as_number(v) is not None for v in vals) >= 0.8 * len(vals):
            z = [v for v in vals if re.fullmatch(r"0\d+", v)]
            if z:
                yield None, c, f"{len(z)} values have leading zeros (e.g. {z[0]}): probably not a number"


def _s3_case_variants(t):
    for c in t.keys:
        groups = defaultdict(set)
        for v in t.values(c):
            if not is_null(v):
                groups[v.lower()].add(v)
        for forms in groups.values():
            if len(forms) > 1:
                cnt = Counter(t.values(c))
                yield None, c, "; ".join(f"{f}={cnt[f]}" for f in sorted(forms))


def _s3_near_duplicates(t):
    for c in t.keys:
        cnt = Counter(v for v in t.values(c) if not is_null(v))
        if not 2 <= len(cnt) <= 50:
            continue
        vals = sorted(cnt)
        for i, a in enumerate(vals):
            for b in vals[i + 1:]:
                if a.lower() == b.lower() or min(len(a), len(b)) < 4:
                    continue
                if as_number(a) is not None and as_number(b) is not None:
                    continue
                if re.sub(r"\d", "#", a) == re.sub(r"\d", "#", b):
                    continue           # differ only in digits (Arm_2 / Arm_3)
                if difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.9:
                    yield None, c, f"{a}={cnt[a]}; {b}={cnt[b]} (typo, or genuinely different? ask)"


def _s9_empty(t):
    for r in t.rows:
        for c, v in r.items():
            if v == "" or v in NAN_LIKE:
                yield r, c


def _dup_ids(run: CheckRun):
    seen = defaultdict(list)
    for t in run.tables:
        for r in t.rows:
            seen[r.get(run.sample_id, "")].append((t, r))
    for sid, where in seen.items():
        if len(where) > 1:
            places = "; ".join(f"{t.name} row {r.line}" for t, r in where)
            for t, r in where:
                yield t, r, run.sample_id, f"{len(where)} rows: {places}"


def _across_tables(t):
    return ()  # computed over all tables at once; see CROSS_TABLE


GENERIC_CHECKS: list[tuple[str, str, Check]] = [
    ("S0-01", "file is not valid UTF-8", _s0_utf8),
    ("S0-02", "file starts with a byte-order mark", _s0_bom),
    ("S0-03", "row has a different number of cells from the header", _s0_ragged),
    ("S0-04", "entirely blank row", _s0_blank_rows),
    ("S0-05", "blank column (no header, no values)", _s0_blank_columns),
    ("S0-06", "value read differently if quotes are treated CSV-style (TSV)", _s0_quotes),
    ("S0-07", "row repeats an earlier row exactly", _s0_duplicate_rows),
    ("S1-01", "tab or line break inside a cell", _s1_breaks),
    ("S1-02", "leading, trailing or doubled spaces", _s1_spaces),
    ("S1-03", "unusual space character (non-breaking, zero-width, ...)", _s1_unusual),
    ("S1-04", "CRLF row endings", _s1_crlf),
    ("S2-01", "duplicate column name", _s2_duplicates),
    ("S2-02", "column with values but no name", _s2_empty_names),
    ("S3-01", "two columns identical in every row", _s3_identical),
    ("S3-02", "two columns identical except for capitalization", _s3_case_only),
    ("S3-03", "two columns identical in at least 95% of rows", _s3_mostly_identical),
    ("S3-04", "column holds only empty or null values", _s3_null_only),
    ("S3-05", "column name suggests PII or PHI", _s3_pii_name),
    ("S3-06", "value pattern suggests PII or PHI", _s3_pii_value),
    ("S3-07", "value looks like a gene name converted to a date", _s3_gene_dates),
    ("S3-08", "date/time in a different format from most of its column", _s3_mixed_dates),
    ("S3-09", "date after the as-of date", _across_tables),
    ("S3-10", "partial date (year or year-month only)", _s3_partial_dates),
    ("S3-11", "round-number heaping in a numeric column", _s3_heaping),
    ("S3-12", "leading zeros in a numeric-looking column", _s3_leading_zeros),
    ("S3-13", "same value written with different capitalization", _s3_case_variants),
    ("S3-14", "near-duplicate values that might be typos", _s3_near_duplicates),
    ("S3-15", "sample ID not unique (all tables)", _across_tables),
    ("S3-16", "number written in scientific notation", _s3_scientific),
    ("S3-17", "value may have been cut off at a length limit", _s3_truncated),
]


def _future(run: CheckRun):
    if run.as_of is None:
        return
    for t in run.tables:
        for c in _date_columns(t):
            for r in t.rows:
                d, _ = parse_date(r[c])
                if d and d.date() > run.as_of:
                    yield t, r, c, f"after {run.as_of}"


CROSS_TABLE = {"S3-09": _future, "S3-15": _dup_ids}


# ---------------------------------------------------------------------------
# Profile (HTML)
# ---------------------------------------------------------------------------
CSS = """
body{font-family:system-ui,sans-serif;margin:24px;color:#222;max-width:1100px}
h1{font-size:22px} h2{font-size:18px;margin-top:32px;border-bottom:2px solid #ccc}
.col{border:1px solid #ddd;border-radius:6px;padding:10px 14px;margin:12px 0}
.col h3{font-size:15px;margin:0 0 4px} .meta{color:#555;font-size:13px;margin-bottom:6px}
table.freq{border-collapse:collapse;font-size:13px} table.freq td{padding:1px 8px 1px 0;vertical-align:middle}
.bar{background:#4a7bd0;height:10px;display:inline-block}
.v{max-width:520px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hist{display:flex;align-items:flex-end;gap:2px;height:60px;margin:6px 0 2px}
.hist div{background:#4a7bd0;width:28px} .hlab{display:flex;gap:2px;font-size:10px;color:#666}
.hlab span{width:28px;text-align:center;overflow:hidden}
.toc a{margin-right:10px;font-size:13px}
"""


def render_profile(run: CheckRun) -> str:
    groups: dict[tuple, list[Table]] = defaultdict(list)
    for t in run.tables:
        groups[tuple(t.header)].append(t)
    e = html.escape
    out = ["<!doctype html><html><head><meta charset='utf-8'><title>Column profile</title>",
           f"<style>{CSS}</style></head><body><h1>Column profile</h1>"]
    for gi, (header, tables) in enumerate(groups.items(), start=1):
        rows = [r for t in tables for r in t.rows]
        out.append(f"<h2>{'Tables' if len(tables) > 1 else 'Table'}: "
                   f"{len(tables)} file{'s' if len(tables) > 1 else ''}, {len(rows)} rows, "
                   f"{len(header)} columns</h2>")
        out.append("<table class='freq'><tr><td><b>File</b></td><td><b>Rows</b></td></tr>" +
                   "".join(f"<tr><td>{e(t.name)}</td><td>{len(t.rows)}</td></tr>" for t in tables) +
                   "</table>")
        out.append("<p class='toc'>" + " ".join(
            f"<a href='#g{gi}c{i}'>{e(c) or '(no name)'}</a>" for i, c in enumerate(header)) + "</p>")
        keys = tables[0].keys
        for i, (c, k) in enumerate(zip(header, keys)):
            vals = [r.get(k, "") for r in rows]
            out.append(_column_card(f"g{gi}c{i}", column_letter(i), c, vals, run.kinds.get(k)))
    out.append("</body></html>")
    return "\n".join(out)


def _column_card(anchor: str, letter: str, name: str, vals: list[str], set_kind: str | None) -> str:
    e = html.escape
    cnt = Counter(vals)
    filled = sum(n for v, n in cnt.items() if v != "")
    nulls = sum(n for v, n in cnt.items() if v in NULL_TERMS)
    nums = [x for x in (as_number(v) for v in vals if not is_null(v)) if x is not None]
    non_null = [v for v in vals if not is_null(v)]
    if set_kind:
        kind, label = set_kind, "set by scientist"
        if kind == "categorical" and nums and len(nums) >= 0.9 * len(non_null):
            kind = "categorical (numbers)"
    else:
        kind, label = column_kind(vals, name), "guess"
    parts = [f"<div class='col' id='{anchor}'><h3>{letter}: {e(name) or '(no name)'}</h3>",
             f"<div class='meta'>{label}: <b>{kind}</b> &middot; "
             f"filled {filled} &middot; empty {cnt.get('', 0)} &middot; null terms {nulls} "
             f"&middot; distinct {len(cnt)}</div>"]
    if kind == "numeric" and len(set(nums)) > 1:
        parts.append(f"<div class='meta'>{len(nums)} numbers: min {_fmt(min(nums))} &middot; "
                     f"max {_fmt(max(nums))} &middot; mean {_fmt(statistics.mean(nums))} &middot; "
                     f"median {_fmt(statistics.median(nums))}</div>")
        parts.append(_histogram(nums))
    dates = sorted(d for d in (parse_date(v)[0] for v in non_null) if d)
    if dates and len(dates) >= 0.8 * len(non_null):
        parts.append(f"<div class='meta'>{len(dates)} dates: earliest {dates[0]:%Y-%m-%d} &middot; "
                     f"latest {dates[-1]:%Y-%m-%d}</div>")
    if len(cnt) <= 50 or (set_kind and kind.startswith("categorical")):
        items = cnt.most_common()
        if kind == "categorical (numbers)":   # in order of value, like a histogram of the actual values
            items = sorted(items, key=lambda vn: (as_number(vn[0]) is None, as_number(vn[0]) or 0, vn[0]))
        parts.append(_freq_table(items[:200]))
        if len(items) > 200:
            parts.append(f"<div class='meta'>... and {len(items) - 200} more distinct values</div>")
    else:
        nulls_shown = [(v, n) for v, n in cnt.most_common() if v == "" or v in NULL_TERMS]
        if nulls_shown:
            parts.append(_freq_table(nulls_shown))
        step = max(1, len(non_null) // 10)
        examples = non_null[::step][:10]
        parts.append(f"<div class='meta'>{len(cnt)} distinct values; {len(examples)} examples "
                     f"from throughout the column:</div><div class='meta'>" +
                     " &middot; ".join(f"<code>{e(v)}</code>" for v in examples) + "</div>")
    parts.append("</div>")
    return "\n".join(parts)


def _freq_table(items: list[tuple[str, int]]) -> str:
    e = html.escape
    top = max((n for _, n in items), default=1)
    rows = []
    for v, n in items:
        label = e(v) if v != "" else "<i>(empty)</i>"
        rows.append(f"<tr><td>{n}</td><td><span class='bar' style='width:{max(1, round(160 * n / top))}px'>"
                    f"</span></td><td class='v' title='{e(v)}'>{label}</td></tr>")
    return "<table class='freq'>" + "".join(rows) + "</table>"


def _histogram(nums: list[float], bins: int = 10) -> str:
    lo, hi = min(nums), max(nums)
    width = (hi - lo) / bins
    counts = [0] * bins
    for x in nums:
        counts[min(bins - 1, int((x - lo) / width))] += 1
    top = max(counts)
    bars = "".join(f"<div style='height:{max(1, round(60 * n / top))}px' title='{n}'></div>" for n in counts)
    labels = "".join(f"<span>{_fmt(lo + k * width)}</span>" for k in range(bins))
    return f"<div class='hist'>{bars}</div><div class='hlab'>{labels}</div>"


def _fmt(x: float) -> str:
    """Plain notation, never exponential: whole numbers exactly, others to 4 significant digits."""
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return format(Decimal(f"{x:.4g}"), "f")
