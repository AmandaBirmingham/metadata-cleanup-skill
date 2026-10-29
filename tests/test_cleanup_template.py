"""Tests for scripts/cleanup_template.py (written before the template)."""

import subprocess
import sys
import textwrap
from pathlib import Path

import pandas as pd
import pytest

import cleanup_template as ct
from cleanup_template import Stop


@pytest.fixture(autouse=True)
def fresh_changes():
    ct.CHANGES.clear()
    yield
    ct.CHANGES.clear()


def load(write, rows, name="t.tsv", table="T", id_column="sample_name"):
    return ct.Table(table, write(name, rows), id_column=id_column)


ROWS = [
    ["sample_name", "status", "date"],
    ["S1", "Healthy", "2/9/22 6:52"],
    ["S2", "healthy", "2022-02-10 13:08:00"],
    ["S3", "Sick", "2/11/22 17:44"],
]


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------
def test_reads_every_cell_as_text_and_keeps_quotes(write):
    t = load(
        write,
        [["sample_name", "n", "q"], ["S1", "007", '"""x"""'], ["S2", "NA", "None"]],
    )
    assert t.df.loc["T|row 2", "n"] == "007"
    assert t.df.loc["T|row 2", "q"] == '"""x"""'
    assert list(t.df["n"]) == ["007", "NA"] and t.df.loc["T|row 3", "q"] == "None"


# The reader has its own tests (test_read_file); the Table tests below that
# overlap them check that Table builds its frame from what the reader returns


def test_csv_parsed_standard_way(write):
    t = ct.Table(
        "C", write("c.csv", 'sample_name,note\nS1,"a, b"\n'), id_column="sample_name"
    )
    assert t.df.loc["C|row 2", "note"] == "a, b"


def test_row_and_column_ids(write):
    t = load(write, ROWS)
    assert list(t.df.index) == ["T|row 2", "T|row 3", "T|row 4"]
    assert t.col_id("date") == "C"


def test_duplicate_and_blank_column_names_kept_apart(write):
    t = load(write, [["sample_name", "a", "a", ""], ["S1", "1", "2", "3"]])
    assert list(t.df.columns) == ["sample_name", "a", "a [col C]", "[col D]"]


def test_ragged_or_non_utf8_file_stops(write):
    with pytest.raises(Stop, match="cells"):
        ct.Table(
            "T", write("r.tsv", "sample_name\ta\nS1\tx\ty\n"), id_column="sample_name"
        )
    with pytest.raises(Stop, match="cells"):
        ct.Table(
            "T", write("r2.tsv", "sample_name\ta\tb\nS1\tx\n"), id_column="sample_name"
        )
    with pytest.raises(Stop, match="UTF-8"):
        ct.Table(
            "T",
            write("l.tsv", None, raw="sample_name\ta\nS1\t\xe3\n".encode("latin-1")),
            id_column="sample_name",
        )


def test_bom_and_crlf_read(write):
    t = ct.Table(
        "T",
        write("b.tsv", None, raw=b"\xef\xbb\xbfsample_name\ta\r\nS1\tx\r\n"),
        id_column="sample_name",
    )
    assert (
        list(t.df.columns) == ["sample_name", "a"] and t.df.loc["T|row 2", "a"] == "x"
    )


@pytest.mark.parametrize(
    "name,raw,expected",
    [
        (
            "t.tsv",
            b'sample_name\ta\nS1\t"x"\n\nS2\ty\n',
            ct.RawTable(
                "tsv",
                'sample_name\ta\nS1\t"x"\n\nS2\ty\n',
                False,
                True,
                0,
                [["sample_name", "a"], ["S1", '"x"'], [], ["S2", "y"]],
            ),
        ),
        (
            "t.csv",
            b'sample_name,a\nS1,"x, y"\n\nS2,z\n',
            ct.RawTable(
                "csv",
                'sample_name,a\nS1,"x, y"\n\nS2,z\n',
                False,
                True,
                0,
                [["sample_name", "a"], ["S1", "x, y"], [], ["S2", "z"]],
            ),
        ),
        (
            "t.txt",
            b"\xef\xbb\xbfsample_name\ta\r\nS1\tx\r\n",
            ct.RawTable(
                "tsv",
                "sample_name\ta\r\nS1\tx\r\n",
                True,
                True,
                2,
                [["sample_name", "a"], ["S1", "x"]],
            ),
        ),
        (
            "t.tsv",
            "sample_name\ta\nS1\t\xe3\n".encode("latin-1"),
            ct.RawTable(
                "tsv",
                "sample_name\ta\nS1\t\xe3\n",
                False,
                False,
                0,
                [["sample_name", "a"], ["S1", "\xe3"]],
            ),
        ),
    ],
)
def test_read_file(write, name, raw, expected):
    assert ct.read_file(write(name, None, raw=raw)) == expected


def test_read_file_unreadable_suffix_stops(write):
    with pytest.raises(Stop, match="cannot read .xlsx"):
        ct.read_file(write("t.xlsx", None, raw=b"PK\x03\x04"))


@pytest.mark.parametrize(
    "i,letter",
    [
        (0, "A"),
        (25, "Z"),
        (26, "AA"),
        (51, "AZ"),
        (52, "BA"),
        (701, "ZZ"),
        (702, "AAA"),
    ],
)
def test_column_letter(i, letter):
    assert ct.column_letter(i) == letter


def test_unique_column_names():
    assert ct.unique_column_names(["a", "a", "", "b"]) == [
        "a",
        "a [col B]",
        "[col C]",
        "b",
    ]


def test_one_line():
    assert ct.one_line("a\tb\r\nc") == "a\\tb\\r\\nc"


def test_refuse_existing(tmp_path):
    there = tmp_path / "there.tsv"
    there.write_text("x")
    ct.refuse_existing(tmp_path / "absent.tsv")
    with pytest.raises(Stop, match="there.tsv already exists"):
        ct.refuse_existing(tmp_path / "absent.tsv", there)


def test_write_tsv(tmp_path):
    out = tmp_path / "o.tsv"
    ct.write_tsv(out, ["a", "b"], [("x\ty", 1), ("line\nbreak", "")])
    assert out.read_text() == "a\tb\nx\\ty\t1\nline\\nbreak\t\n"


@pytest.mark.parametrize(
    "name,content",
    [
        ("t.tsv", "sample_name\ta\nS1\tx\n\nS2\ty\n"),
        ("t.csv", "sample_name,a\nS1,x\n\nS2,y\n"),
    ],
)
def test_table_blank_rows_kept(write, name, content):
    t = ct.Table("T", write(name, content), id_column="sample_name")
    expected = pd.DataFrame(
        {"sample_name": ["S1", "", "S2"], "a": ["x", "", "y"]},
        index=["T|row 2", "T|row 3", "T|row 4"],
        dtype=str,
    )
    pd.testing.assert_frame_equal(t.df, expected)
    # A blank row is removed only by a recorded decision, under its real row number
    ct.delete_rows(t, ct.select(t, sample_name=""), decision="D-001")
    assert [(c["kind"], c["row"]) for c in ct.CHANGES] == [("row deleted", "3")]


# ---------------------------------------------------------------------------
# select / exclude
# ---------------------------------------------------------------------------
def test_select_by_value_list_regex_function_and_ids(write):
    t = load(write, ROWS)
    assert ct.select(t, status="Sick").index == ["T|row 4"]
    assert ct.select(t, status=["Healthy", "Sick"]).index == ["T|row 2", "T|row 4"]
    assert ct.select(t, date=ct.matches(r"\d+/\d+/\d+ \d+:\d+")).index == [
        "T|row 2",
        "T|row 4",
    ]
    assert ct.select(t, status=lambda v: v.lower() == "healthy").index == [
        "T|row 2",
        "T|row 3",
    ]
    assert ct.select(t, ids=["S3", "S1"]).index == ["T|row 2", "T|row 4"]
    assert ct.select(t).index == ["T|row 2", "T|row 3", "T|row 4"]


def test_select_refusals(write):
    t = load(write, ROWS)
    with pytest.raises(Stop, match="matches no rows"):
        ct.select(t, status="Unknown")
    with pytest.raises(Stop, match="S9"):
        ct.select(t, ids=["S1", "S9"])
    with pytest.raises(Stop, match="no column"):
        ct.select(t, nope="x")


def test_exclude(write):
    t = load(write, ROWS)
    rows = ct.exclude(ct.select(t), status="Sick")
    assert rows.index == ["T|row 2", "T|row 3"]
    assert ct.exclude(ct.select(t), ids=["S1"]).index == ["T|row 3", "T|row 4"]
    with pytest.raises(Stop, match="matches no rows"):
        ct.exclude(ct.select(t), status="Unknown")


# ---------------------------------------------------------------------------
# changes and the change list
# ---------------------------------------------------------------------------
def test_set_value_records_only_changed_cells(write):
    t = load(write, ROWS)
    ct.set_value(
        t,
        ct.select(t, status=["Healthy", "healthy"]),
        "status",
        "healthy",
        decision="D-001",
    )
    assert list(t.df["status"]) == ["healthy", "healthy", "Sick"]
    assert ct.CHANGES == [
        {
            "decision": "D-001",
            "kind": "value changed",
            "file": "t.tsv",
            "row": "2",
            "column_letter": "B",
            "column": "status",
            "table_unique_id": "S1",
            "old": "Healthy",
            "new": "healthy",
        }
    ]


def test_set_value_that_changes_nothing_stops(write):
    t = load(write, ROWS)
    with pytest.raises(Stop, match="changes nothing"):
        ct.set_value(t, ct.select(t, status="Sick"), "status", "Sick", decision="D-001")


def test_map_values_exact_matches_only(write):
    t = load(write, ROWS)
    ct.map_values(t, "status", {"healthy": "Healthy", "Sic": "Sick"}, decision="D-002")
    assert list(t.df["status"]) == ["Healthy", "Healthy", "Sick"]
    assert [(c["row"], c["old"]) for c in ct.CHANGES] == [("3", "healthy")]


def test_map_values_with_no_match_stops(write):
    t = load(write, ROWS)
    with pytest.raises(Stop, match="matches no"):
        ct.map_values(t, "status", {"Well": "Healthy"}, decision="D-002")


def test_reformat_dates(write):
    t = load(write, ROWS)
    rows = ct.select(t, date=ct.matches(r"\d+/\d+/\d+ \d+:\d+"))
    ct.reformat_dates(
        t, rows, "date", "%m/%d/%y %H:%M", "%Y-%m-%d %H:%M:%S", decision="D-003"
    )
    assert list(t.df["date"]) == [
        "2022-02-09 06:52:00",
        "2022-02-10 13:08:00",
        "2022-02-11 17:44:00",
    ]
    assert len(ct.CHANGES) == 2


def test_reformat_dates_that_changes_nothing_stops(write):
    t = load(write, ROWS)
    rows = ct.select(t, sample_name="S2")
    with pytest.raises(Stop, match="changes nothing"):
        ct.reformat_dates(
            t, rows, "date", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", decision="D-003"
        )


def test__own_empty_rows_stop(write):
    t = load(write, ROWS)
    rows = ct.exclude(ct.select(t, status="Sick"), status="Sick")
    with pytest.raises(Stop, match="no rows left"):
        ct.delete_rows(t, rows, decision="D-009")


def test_reformat_dates_stops_on_unparseable(write):
    t = load(write, ROWS)
    with pytest.raises(Stop, match="row 3"):
        ct.reformat_dates(
            t, ct.select(t), "date", "%m/%d/%y %H:%M", "%Y-%m-%d", decision="D-003"
        )


def test_add_column(write):
    t = load(write, ROWS)
    ct.add_column(
        t,
        "box",
        {"S1": "3", "S2": "3", "S3": "4"},
        decision="D-004",
        after="sample_name",
    )
    ct.add_column(t, "site", "UCSD", decision="D-005")
    expected = pd.DataFrame(
        {
            "sample_name": ["S1", "S2", "S3"],
            "box": ["3", "3", "4"],
            "status": ["Healthy", "healthy", "Sick"],
            "date": ["2/9/22 6:52", "2022-02-10 13:08:00", "2/11/22 17:44"],
            "site": ["UCSD"] * 3,
        },
        index=["T|row 2", "T|row 3", "T|row 4"],
        dtype=str,
    )
    pd.testing.assert_frame_equal(t.df, expected)
    added = {"kind": "column added", "file": "t.tsv", "row": "", "column_letter": ""}
    added |= {"table_unique_id": "", "old": "", "new": ""}
    assert ct.CHANGES == [
        {"decision": "D-004", **added, "column": "box"},
        {"decision": "D-005", **added, "column": "site"},
    ]


def test_add_column_refusals(write):
    t = load(write, ROWS)
    with pytest.raises(Stop, match="S3"):
        ct.add_column(t, "box", {"S1": "3", "S2": "3"}, decision="D-004")
    with pytest.raises(Stop, match="already"):
        ct.add_column(t, "status", "x", decision="D-004")
    with pytest.raises(Stop, match="no column named 'nope'"):
        ct.add_column(t, "box", "x", decision="D-004", after="nope")
    with pytest.raises(Stop, match="S9"):
        ct.add_column(
            t, "box", {"S1": "3", "S2": "3", "S3": "4", "S9": "5"}, decision="D-004"
        )


def test_rename_and_delete_column(write):
    t = load(write, ROWS)
    ct.rename_column(t, "date", "collection_date", decision="D-006")
    assert t.col_id("collection_date") == "C"
    ct.delete_column(t, "status", decision="D-007")
    assert list(t.df.columns) == ["sample_name", "collection_date"]
    assert ct.CHANGES == [
        {
            "decision": "D-006",
            "kind": "column renamed",
            "file": "t.tsv",
            "row": "",
            "column_letter": "C",
            "column": "collection_date",
            "table_unique_id": "",
            "old": "date",
            "new": "collection_date",
        },
        {
            "decision": "D-007",
            "kind": "column deleted",
            "file": "t.tsv",
            "row": "",
            "column_letter": "B",
            "column": "status",
            "table_unique_id": "",
            "old": "",
            "new": "",
        },
    ]
    with pytest.raises(Stop):
        ct.rename_column(t, "nope", "x", decision="D-008")
    with pytest.raises(Stop):
        ct.rename_column(t, "sample_name", "collection_date", decision="D-008")


def test_delete_rows(write):
    t = load(write, ROWS)
    ct.delete_rows(t, ct.select(t, ids=["S2"]), decision="D-009")
    assert list(t.df["sample_name"]) == ["S1", "S3"]
    assert ct.CHANGES == [
        {
            "decision": "D-009",
            "kind": "row deleted",
            "file": "t.tsv",
            "row": "3",
            "column_letter": "",
            "column": "",
            "table_unique_id": "S2",
            "old": "",
            "new": "",
        }
    ]


def test_rows_from_another_table_refused(write):
    a, b = load(write, ROWS, "a.tsv", "A"), load(write, ROWS, "b.tsv", "B")
    with pytest.raises(Stop, match="another table"):
        ct.set_value(a, ct.select(b, ids=["S1"]), "status", "x", decision="D-001")


def test_normalize_whitespace(write):
    t = load(
        write,
        [["sample_name ", "a"], ["S1", " x  y "], ["S2", "x  y"], ["S3", "ok"]],
        id_column="sample_name ",
    )
    ct.normalize_whitespace(t, decision="D-010")
    assert list(t.df.columns) == ["sample_name", "a"]
    assert list(t.df["a"]) == ["x y", "x y", "ok"]
    assert [c["kind"] for c in ct.CHANGES] == [
        "column renamed",
        "value changed",
        "value changed",
    ]


def test_normalize_whitespace_listed_columns(write):
    t = load(write, [["sample_name", " a", "b "], ["S1", " x", " y"]])
    ct.normalize_whitespace(t, decision="D-010", columns=[" a"])
    expected = pd.DataFrame(
        {"sample_name": ["S1"], "a": ["x"], "b ": [" y"]}, index=["T|row 2"], dtype=str
    )
    pd.testing.assert_frame_equal(t.df, expected)
    with pytest.raises(Stop, match="no column named 'nope'"):
        ct.normalize_whitespace(t, decision="D-011", columns=["nope"])


def test_normalize_whitespace_unusual_spaces(write):
    t = load(
        write,
        [
            ["sample_name", "a\u200b"],
            ["S1", "x\u2009y"],
            ["S2", "\ufeffz"],
            ["S3", "b\u3000\u00a0c "],
        ],
    )
    ct.normalize_whitespace(t, decision="D-010")
    expected = pd.DataFrame(
        {"sample_name": ["S1", "S2", "S3"], "a": ["x y", "z", "b c"]},
        index=["T|row 2", "T|row 3", "T|row 4"],
        dtype=str,
    )
    pd.testing.assert_frame_equal(t.df, expected)


def stack_parts(write):
    """Two tables with the same columns and different samples."""
    a = load(write, [["sample_name", "x"], ["S1", "1"]], "a.tsv", "A")
    b = load(write, [["sample_name", "x"], ["S2", "2"]], "b.tsv", "B")
    return a, b


def test_stack(write):
    a, b = stack_parts(write)
    m = ct.stack([a, b], decision="D-011", source_column="source_file")
    assert m.name == "merged" and list(m.df["sample_name"]) == ["S1", "S2"]
    assert list(m.df["source_file"]) == ["a.tsv", "b.tsv"]
    assert list(m.df.index) == ["A|row 2", "B|row 2"]


def stacked_outputs(write, tmp_path):
    a, b = stack_parts(write)
    m = ct.stack([a, b], decision="D-011")
    written = {}
    for name, table in (("A", a), ("B", b), ("merged", m)):
        out = tmp_path / f"{name}__draft_t1.tsv"
        ct.write_table(table, out)
        written[table.name] = out
    return m, written


def test_write_stacking_report(write, tmp_path):
    m, written = stacked_outputs(write, tmp_path)
    report = tmp_path / "merged__stacking__draft_t1.tsv"
    summary = ct.write_stacking_report(m, written, report)
    assert report.read_text() == (
        "item\tvalue\nrows from a.tsv\t1\nrows from b.tsv\t1\n"
        "rows in total\t2\ncolumns\t2\n"
        "same as the per-table outputs in order\tyes\n"
    )
    assert (
        summary
        == "merged: 2 tables stacked, 2 rows, 2 columns; same as the per-table outputs in order: yes"
    )


def test_write_stacking_report_detects_difference_and_never_overwrites(write, tmp_path):
    m, written = stacked_outputs(write, tmp_path)
    written["merged"].write_text("sample_name\tx\nS2\t2\nS1\t1\n")
    report = tmp_path / "merged__stacking__draft_t1.tsv"
    assert ct.write_stacking_report(m, written, report).endswith("in order: no")
    with pytest.raises(Stop, match="already exists"):
        ct.write_stacking_report(m, written, report)


def test_stack_refusals(write):
    a = load(write, [["sample_name", "x"], ["S1", "1"]], "a.tsv", "A")
    b = load(write, [["sample_name", "y"], ["S2", "2"]], "b.tsv", "B")
    c = load(write, [["sample_name", "x"], ["S1", "2"]], "c.tsv", "C")
    with pytest.raises(Stop, match="columns"):
        ct.stack([a, b], decision="D-011")
    with pytest.raises(Stop, match="S1"):
        ct.stack([a, c], decision="D-011")
    with pytest.raises(Stop, match="already has a column named 'x'"):
        ct.stack(
            [a, load(write, [["sample_name", "x"], ["S2", "2"]], "d.tsv", "D")],
            decision="D-011",
            source_column="x",
        )


# ---------------------------------------------------------------------------
# tables identified by a column other than the sample ID
# ---------------------------------------------------------------------------
SUBJECTS = [["subject_id", "age"], ["P1", "40"], ["P2", "50"]]
DIFF_SCRIPT = ("--diff-script", "diff_tables.py")  # never run: make_diff is replaced


def test_table_missing_id_column_stops(write):
    with pytest.raises(Stop, match="no column named 'sample_name'"):
        load(write, SUBJECTS)


def test_select_ids_from_table_id_column(write):
    t = load(write, SUBJECTS, id_column="subject_id")
    assert ct.select(t, ids=["P2"]).index == ["T|row 3"]


def test_add_column_by_table_id_column(write):
    t = load(write, SUBJECTS, id_column="subject_id")
    ct.add_column(t, "sex", {"P1": "female", "P2": "male"}, decision="D-001")
    ct.add_column(t, "site", "UCSD", decision="D-002")
    expected = pd.DataFrame(
        {
            "subject_id": ["P1", "P2"],
            "age": ["40", "50"],
            "sex": ["female", "male"],
            "site": ["UCSD", "UCSD"],
        },
        index=["T|row 2", "T|row 3"],
        dtype=str,
    )
    pd.testing.assert_frame_equal(t.df, expected)


def test_rename_column_of_id_column(write):
    t = load(write, SUBJECTS, id_column="subject_id")
    ct.rename_column(t, "subject_id", "host_subject_id", decision="D-001")
    ct.set_value(t, ct.select(t, ids=["P1"]), "age", "41", decision="D-002")
    found = (t.id_column, ct.CHANGES[-1]["table_unique_id"])
    assert found == ("host_subject_id", "P1")


def test_stack_by_table_id_column(write):
    a = load(write, SUBJECTS, "a.tsv", "A", "subject_id")
    b = load(write, [["subject_id", "age"], ["P3", "60"]], "b.tsv", "B", "subject_id")
    m = ct.stack([a, b], decision="D-001")
    found = (m.id_column, list(m.df["subject_id"]))
    assert found == ("subject_id", ["P1", "P2", "P3"])


def test_stack_refusals_by_table_id_column(write):
    a = load(write, SUBJECTS, "a.tsv", "A", "subject_id")
    b = load(write, [["subject_id", "age"], ["P1", "60"]], "b.tsv", "B", "subject_id")
    c = load(write, [["subject_id", "age"], ["P3", "60"]], "c.tsv", "C", "age")
    with pytest.raises(Stop, match="P1"):
        ct.stack([a, b], decision="D-001")
    with pytest.raises(Stop, match="ID column"):
        ct.stack([a, c], decision="D-001")


# ---------------------------------------------------------------------------
# the decision log against the script
# ---------------------------------------------------------------------------
LOG = """# Decision log

## D-001 · 2026-10-22 14:05
Finding: S3-08, findings_20261022-101500.tsv
Decided: Keep the quotes.
Changes data: no

## D-002 · 2026-10-22 14:10
Finding: none
Decided: Lower-case the status values.
Changes data: yes

## D-003 · 2026-10-22 14:20
Finding: none
Decided: Undo D-002.
Changes data: no
Replaces: D-002
"""

GOOD = """
def decisions(t):
    # D-001
    pass

    # D-002
    pass

    # D-003
    pass
"""


@pytest.fixture
def log_file(tmp_path):
    """The decision log LOG, written to a file."""
    p = tmp_path / "log.md"
    p.write_text(LOG)
    return p


def test_parse_log(log_file):
    entries = ct.parse_log(log_file)
    assert [(e["id"], e["changes"], e["replaces"]) for e in entries] == [
        ("D-001", False, None),
        ("D-002", True, None),
        ("D-003", False, "D-002"),
    ]


def test_parse_blocks():
    blocks = ct.parse_blocks(
        textwrap.dedent(GOOD.replace("    # D-002\n    pass", "    # D-002\n    x = 1"))
    )
    assert blocks == {"D-001": True, "D-002": False, "D-003": True}  # True: only `pass`


def test_log_and_script_agree(log_file):
    assert ct.log_mismatches(ct.parse_log(log_file), ct.parse_blocks(GOOD)) == []


@pytest.mark.parametrize(
    "script,expected",
    [
        (
            GOOD.replace("    # D-003\n    pass\n", ""),
            "D-003 is in the decision log but has no block",
        ),
        (
            GOOD + "\n    # D-004\n    pass\n",
            "D-004 has a block but is not in the decision log",
        ),
        (
            GOOD.replace("    # D-001\n    pass", "    # D-001\n    x = 1"),
            "D-001 changes no data but its block has code",
        ),
    ],
)
def test_log_mismatches(log_file, script, expected):
    out = ct.log_mismatches(ct.parse_log(log_file), ct.parse_blocks(script))
    assert expected in out


def test_changes_data_yes_needs_code_unless_replaced(tmp_path):
    p = tmp_path / "log.md"
    p.write_text(LOG.replace("Changes data: no\nReplaces: D-002", "Changes data: yes"))
    out = ct.log_mismatches(ct.parse_log(p), ct.parse_blocks(GOOD))
    assert "D-002 changes data but its block is only `pass`" in out
    assert "D-003 changes data but its block is only `pass`" in out


def test_replaced_decision_must_be_pass(log_file):
    out = ct.log_mismatches(
        ct.parse_log(log_file),
        ct.parse_blocks(
            GOOD.replace("    # D-002\n    pass", "    # D-002\n    x = 1")
        ),
    )
    assert out == ["D-002 is replaced by D-003, so its block must be `pass`"]


def test_parse_log_repeated_id_stops(tmp_path):
    p = tmp_path / "log.md"
    p.write_text(LOG + "\n## D-002 · 2026-10-22 14:30\nDecided: x\nChanges data: no\n")
    with pytest.raises(Stop, match="more than one entry for D-002"):
        ct.parse_log(p)


def test_parse_blocks_repeated_block_stops():
    with pytest.raises(Stop, match="more than one block for D-001"):
        ct.parse_blocks(GOOD + "\n    # D-001\n    x = 1\n")


def test_parse_blocks_decision_of_another_block_stops():
    script = GOOD.replace(
        "    # D-002\n    pass",
        '    # D-002\n    set_value(x, y, "a", "b", decision="D-003")',
    )
    with pytest.raises(Stop, match='D-002 passes decision="D-003"'):
        ct.parse_blocks(script)


def test_parse_log_other_heading_ends_entry(tmp_path):
    p = tmp_path / "log.md"
    p.write_text(
        "## D-001 · 2026-10-22 14:05\nDecided: x\n\n## Study information\n"
        "Changes data: no\n"
    )
    with pytest.raises(Stop, match="D-001 has no 'Changes data"):
        ct.parse_log(p)


def test_log_mismatches_replaces_unknown_id(tmp_path):
    p = tmp_path / "log.md"
    p.write_text(LOG.replace("Replaces: D-002", "Replaces: D-099"))
    out = ct.log_mismatches(ct.parse_log(p), ct.parse_blocks(GOOD))
    assert "D-003 replaces D-099, which is not in the decision log" in out


def test_malformed_log_entry(tmp_path):
    p = tmp_path / "log.md"
    p.write_text("## D-001 · 2026-10-22 14:05\nFinding: none\nDecided: x\n")
    with pytest.raises(Stop, match="D-001.*Changes data"):
        ct.parse_log(p)


# ---------------------------------------------------------------------------
# writing outputs, the change list and the diff
# ---------------------------------------------------------------------------
def test_write_table_and_refusals(write, tmp_path):
    t = load(write, [["sample_name", "q"], ["S1", '"""x"""']])
    out = tmp_path / "o.tsv"
    ct.write_table(t, out)
    assert out.read_text() == 'sample_name\tq\nS1\t"""x"""\n'
    with pytest.raises(Stop, match="exists"):
        ct.write_table(t, out)
    t.df.loc["T|row 2", "q"] = "a\tb"
    with pytest.raises(Stop, match="tab or line break"):
        ct.write_table(t, tmp_path / "o2.tsv")


def test_write_table_invented_column_name_stops(write, tmp_path):
    t = load(write, [["sample_name", "a", "a", ""], ["S1", "1", "2", "3"]])
    with pytest.raises(Stop, match="columns C, D have a repeated or blank name"):
        ct.write_table(t, tmp_path / "o.tsv")
    ct.rename_column(t, "a [col C]", "a2", decision="D-001")
    ct.delete_column(t, "[col D]", decision="D-002")
    ct.write_table(t, tmp_path / "o.tsv")
    assert (tmp_path / "o.tsv").read_text() == "sample_name\ta\ta2\nS1\t1\t2\n"


@pytest.mark.parametrize("value", ["a\rb", "a\nb"])
def test_write_table_refuses_line_breaks(write, tmp_path, value):
    t = load(write, [["sample_name", "q"], ["S1", "x"]])
    t.df.loc["T|row 2", "q"] = value
    with pytest.raises(Stop, match="tab or line break"):
        ct.write_table(t, tmp_path / "o.tsv")


def make_project(tmp_path, decisions_body, log_entries):
    inputs = tmp_path / "in"
    inputs.mkdir()
    (inputs / "2023-04-02_batch_a.txt").write_text(
        "sample_name\tstatus\nS1\tHealthy\nS2\thealthy\n", encoding="utf-8"
    )
    log = tmp_path / "decision_log_20261022-100000.md"
    log.write_text("# Decision log\n\n" + log_entries)
    script = tmp_path / "cleanup_draft.py"
    src = Path(ct.__file__).read_text()
    src = src.replace(
        "INPUTS: dict[str, str] = {}",
        'INPUTS: dict[str, str] = {"batch_a": "2023-04-02_batch_a.txt"}',
    )
    src = src.replace(
        "ID_COLUMNS: dict[str, str] = {}",
        'ID_COLUMNS: dict[str, str] = {"batch_a": "sample_name"}',
    )
    start = src.index("def decisions(t):")
    end = src.index("# === END OF DECISIONS ===")
    src = src[:start] + "def decisions(t):\n" + decisions_body + "\n\n" + src[end:]
    script.write_text(src)
    (tmp_path / "diff_stub.py").write_text('print("diff stub")\n')
    return inputs, log, script


ENTRY = "## D-001 · 2026-10-22 14:05\nFinding: S3-13, findings_x.tsv\nDecided: Capitalize status.\nChanges data: yes\n"
BODY = (
    "    # D-001\n"
    '    map_values(t["batch_a"], "status", {"healthy": "Healthy"}, decision="D-001")\n'
)


def stub_diff(script):
    """The options naming make_project's stand-in diff script."""
    return ["--diff-script", script.parent / "diff_stub.py"]


def run_cleanup(script, inputs, outdir, timestamp, log, *extra):
    """Run a made cleanup script on the command line; extra: further options."""
    args = ["--inputs", inputs, "--outdir", outdir, "--timestamp", timestamp]
    args += ["--decision-log", log, *extra]
    return subprocess.run(
        [sys.executable, str(script), *map(str, args)], capture_output=True, text=True
    )


def test_end_to_end_draft_run(tmp_path):
    inputs, log, script = make_project(tmp_path, BODY, ENTRY)
    outdir = tmp_path / "out"
    r = run_cleanup(script, inputs, outdir, "20261022-120000", log, *stub_diff(script))
    assert r.returncode == 0, r.stderr
    out = (outdir / "2023-04-02_batch_a__draft_20261022-120000.tsv").read_text()
    assert out == "sample_name\tstatus\nS1\tHealthy\nS2\tHealthy\n"
    changes = (outdir / "changes__draft_20261022-120000.tsv").read_text()
    assert changes == (
        "decision\tkind\tfile\trow\tcolumn_letter\tcolumn\ttable_unique_id\told\tnew\n"
        "D-001\tvalue changed\t2023-04-02_batch_a.txt\t3\tB\tstatus\tS2\thealthy\tHealthy\n"
    )


def test_end_to_end_is_deterministic(tmp_path):
    inputs, log, script = make_project(tmp_path, BODY, ENTRY)
    for ts in ("20261022-120000", "20261022-120100"):
        r = run_cleanup(script, inputs, tmp_path / "out", ts, log, *stub_diff(script))
        assert r.returncode == 0, r.stderr
    a = (
        tmp_path / "out" / "2023-04-02_batch_a__draft_20261022-120000.tsv"
    ).read_bytes()
    b = (
        tmp_path / "out" / "2023-04-02_batch_a__draft_20261022-120100.tsv"
    ).read_bytes()
    assert a == b


def test_end_to_end_final_names(tmp_path):
    inputs, log, script = make_project(tmp_path, BODY, ENTRY)
    r = run_cleanup(script, inputs, tmp_path / "out", "20261022-130000", log, "--final")
    assert r.returncode == 0, r.stderr
    assert (
        tmp_path / "out" / "2023-04-02_batch_a__cleanup_20261022-130000.tsv"
    ).exists()
    assert (tmp_path / "out" / "changes__cleanup_20261022-130000.tsv").exists()


def test_end_to_end_stops_on_log_mismatch(tmp_path):
    inputs, log, script = make_project(tmp_path, "    # D-001\n    pass\n", ENTRY)
    r = run_cleanup(
        script, inputs, tmp_path / "out", "20261022-120000", log, *stub_diff(script)
    )
    assert (
        r.returncode != 0
        and "D-001 changes data but its block is only `pass`" in r.stderr
    )
    assert not (tmp_path / "out").exists() or not any((tmp_path / "out").iterdir())


STACK_ENTRY = "## D-001 · 2026-10-22 14:05\nFinding: none\nDecided: Stack the two batches.\nChanges data: yes\n"
STACK_BODY = '    # D-001\n    t["merged"] = stack([t["batch_a"], t["batch_b"]], decision="D-001")\n'


def test_end_to_end_stacking_report_only_on_first_draft(tmp_path):
    inputs, log, script = make_project(tmp_path, STACK_BODY, STACK_ENTRY)
    (inputs / "2023-04-02_batch_b.txt").write_text(
        "sample_name\tstatus\nS3\tHealthy\n", encoding="utf-8"
    )
    with_inputs = script.read_text().replace(
        '{"batch_a": "2023-04-02_batch_a.txt"}',
        '{"batch_a": "2023-04-02_batch_a.txt", "batch_b": "2023-04-02_batch_b.txt"}',
    )
    src = with_inputs.replace(
        '{"batch_a": "sample_name"}',
        '{"batch_a": "sample_name", "batch_b": "sample_name"}',
    )
    script.write_text(src)
    out = tmp_path / "out"
    first = run_cleanup(script, inputs, out, "20261022-120000", log, *stub_diff(script))
    assert first.returncode == 0, first.stderr
    assert "same as the per-table outputs in order: yes" in first.stdout
    assert (out / "merged__stacking__draft_20261022-120000.tsv").exists()
    second = run_cleanup(
        script, inputs, out, "20261022-120100", log, *stub_diff(script)
    )
    assert second.returncode == 0, second.stderr
    assert not (out / "merged__stacking__draft_20261022-120100.tsv").exists()


def test_previous_draft_found(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    for ts in ("20261022-100000", "20261022-110000", "20261022-130000"):
        (out / f"2023-04-02_batch_a__draft_{ts}.tsv").write_text("x")
    orig = tmp_path / "orig.txt"
    assert (
        ct.previous_draft(out, "2023-04-02_batch_a", "20261022-120000", orig).name
        == "2023-04-02_batch_a__draft_20261022-110000.tsv"
    )
    assert ct.previous_draft(out, "2023-04-02_batch_a", "20261022-090000", orig) == orig


def test_previous_draft_glob_characters(tmp_path):
    (tmp_path / "plate [1]__draft_20261022-100000.tsv").write_text("x")
    orig = tmp_path / "orig.txt"
    found = ct.previous_draft(tmp_path, "plate [1]", "20261022-120000", orig)
    assert found == tmp_path / "plate [1]__draft_20261022-100000.tsv"


def test_main_draft_needs_diff_script(tmp_path, monkeypatch, capsys):
    found = main_on_subjects(tmp_path, monkeypatch, {"subjects": "subject_id"})
    assert (found, capsys.readouterr().err) == (
        (1, []),
        "STOPPED: a draft run needs --diff-script (the skill's scripts/diff_tables.py)\n",
    )


def test_main_stops_on_missing_input(tmp_path):
    inputs, log, script = make_project(tmp_path, BODY, ENTRY)
    src = script.read_text().replace('"2023-04-02_batch_a.txt"}', '"missing.txt"}')
    script.write_text(src)
    r = run_cleanup(script, inputs, tmp_path / "out", "20261022-120000", log, "--final")
    assert (r.returncode, r.stderr) == (
        1,
        f"STOPPED: no input file named missing.txt in {inputs}\n",
    )


def test_diff_called_for_drafts(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        ct.subprocess,
        "run",
        lambda cmd, **k: (
            calls.append(cmd)
            or type(
                "R", (), {"returncode": 0, "stdout": "1 rows changed", "stderr": ""}
            )()
        ),
    )
    ct.make_diff(
        Path("diff_tables.py"),
        Path("prev.tsv"),
        Path("new.tsv"),
        "sample_name",
        Path("d.html"),
    )
    assert calls[0][-6:] == [
        "prev.tsv",
        "new.tsv",
        "--key",
        "sample_name",
        "--out",
        "d.html",
    ]
    assert "diff_tables.py" in calls[0]


def main_on_subjects(tmp_path, monkeypatch, id_columns, *extra):
    """Run main in-process on one subject table, recording each diff's key;
    extra: further options."""
    inputs = tmp_path / "in"
    inputs.mkdir()
    (inputs / "subjects.tsv").write_text("subject_id\tage\nP1\t40\n")
    log = tmp_path / "log.md"
    log.write_text("# Decision log\n")
    monkeypatch.setattr(ct, "INPUTS", {"subjects": "subjects.tsv"})
    monkeypatch.setattr(ct, "ID_COLUMNS", id_columns)
    keys = []
    monkeypatch.setattr(
        ct, "make_diff", lambda script, prev, new, key, out: keys.append(key) or ""
    )
    argv = ["--inputs", str(inputs), "--outdir", str(tmp_path / "out")]
    argv += ["--timestamp", "20261022-120000", "--decision-log", str(log)]
    argv += list(extra)
    returned = ct.main(argv)
    return returned, keys


def test_main_diff_key_is_table_id_column(tmp_path, monkeypatch):
    found = main_on_subjects(
        tmp_path, monkeypatch, {"subjects": "subject_id"}, *DIFF_SCRIPT
    )
    assert found == (0, ["subject_id"])


def test_main_stops_without_id_column(tmp_path, monkeypatch, capsys):
    found = main_on_subjects(tmp_path, monkeypatch, {}, *DIFF_SCRIPT)
    assert found == (1, [])
    assert "ID_COLUMNS names no ID column for subjects" in capsys.readouterr().err
