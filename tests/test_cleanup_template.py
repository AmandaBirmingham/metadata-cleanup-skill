"""Tests for scripts/cleanup_template.py (written before the template)."""

import sys
import textwrap
from pathlib import Path

import pytest

import cleanup_template as ct
from cleanup_template import Stop


@pytest.fixture(autouse=True)
def fresh_changes():
    ct.CHANGES.clear()
    yield
    ct.CHANGES.clear()


def load(write, rows, name="t.tsv", table="T"):
    return ct.Table(table, write(name, rows))


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


def test_csv_parsed_standard_way(write):
    t = ct.Table("C", write("c.csv", 'sample_name,note\nS1,"a, b"\n'))
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
        ct.Table("T", write("r.tsv", "sample_name\ta\nS1\tx\ty\n"))
    with pytest.raises(Stop, match="cells"):
        ct.Table("T", write("r2.tsv", "sample_name\ta\tb\nS1\tx\n"))
    with pytest.raises(Stop, match="UTF-8"):
        ct.Table(
            "T",
            write("l.tsv", None, raw="sample_name\ta\nS1\t\xe3\n".encode("latin-1")),
        )


def test_bom_and_crlf_read(write):
    t = ct.Table(
        "T", write("b.tsv", None, raw=b"\xef\xbb\xbfsample_name\ta\r\nS1\tx\r\n")
    )
    assert (
        list(t.df.columns) == ["sample_name", "a"] and t.df.loc["T|row 2", "a"] == "x"
    )


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
            "sample_id": "S1",
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
    assert list(t.df.columns) == ["sample_name", "box", "status", "date"]
    assert ct.CHANGES[0]["kind"] == "column added" and ct.CHANGES[0]["column"] == "box"
    ct.add_column(t, "site", "UCSD", decision="D-005")
    assert list(t.df["site"]) == ["UCSD"] * 3


def test_add_column_refusals(write):
    t = load(write, ROWS)
    with pytest.raises(Stop, match="S3"):
        ct.add_column(t, "box", {"S1": "3", "S2": "3"}, decision="D-004")
    with pytest.raises(Stop, match="already"):
        ct.add_column(t, "status", "x", decision="D-004")
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
    assert [c["kind"] for c in ct.CHANGES] == ["column renamed", "column deleted"]
    assert ct.CHANGES[0]["old"] == "date" and ct.CHANGES[0]["new"] == "collection_date"
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
            "sample_id": "S2",
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
        write, [["sample_name ", "a"], ["S1", " x  y "], ["S2", "x  y"], ["S3", "ok"]]
    )
    ct.normalize_whitespace(t, decision="D-010")
    assert list(t.df.columns) == ["sample_name", "a"]
    assert list(t.df["a"]) == ["x y", "x y", "ok"]
    assert [c["kind"] for c in ct.CHANGES] == [
        "column renamed",
        "value changed",
        "value changed",
    ]


def test_stack(write):
    a = load(write, [["sample_name", "x"], ["S1", "1"]], "a.tsv", "A")
    b = load(write, [["sample_name", "x"], ["S2", "2"]], "b.tsv", "B")
    m = ct.stack([a, b], decision="D-011", source_column="source_file")
    assert m.name == "merged" and list(m.df["sample_name"]) == ["S1", "S2"]
    assert list(m.df["source_file"]) == ["a.tsv", "b.tsv"]
    assert list(m.df.index) == ["A|row 2", "B|row 2"]


def stacked_outputs(write, tmp_path):
    a = load(write, [["sample_name", "x"], ["S1", "1"]], "a.tsv", "A")
    b = load(write, [["sample_name", "x"], ["S2", "2"]], "b.tsv", "B")
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


def test_parse_log(tmp_path):
    p = tmp_path / "log.md"
    p.write_text(LOG)
    entries = ct.parse_log(p)
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


def test_log_and_script_agree(tmp_path):
    p = tmp_path / "log.md"
    p.write_text(LOG)
    assert ct.log_mismatches(ct.parse_log(p), ct.parse_blocks(GOOD)) == []


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
def test_log_mismatches(tmp_path, script, expected):
    p = tmp_path / "log.md"
    p.write_text(LOG)
    assert expected in ct.log_mismatches(ct.parse_log(p), ct.parse_blocks(script))


def test_changes_data_yes_needs_code_unless_replaced(tmp_path):
    p = tmp_path / "log.md"
    p.write_text(LOG.replace("Changes data: no\nReplaces: D-002", "Changes data: yes"))
    out = ct.log_mismatches(ct.parse_log(p), ct.parse_blocks(GOOD))
    assert "D-002 changes data but its block is only `pass`" in out
    assert "D-003 changes data but its block is only `pass`" in out


def test_replaced_decision_must_be_pass(tmp_path):
    p = tmp_path / "log.md"
    p.write_text(LOG)
    out = ct.log_mismatches(
        ct.parse_log(p),
        ct.parse_blocks(
            GOOD.replace("    # D-002\n    pass", "    # D-002\n    x = 1")
        ),
    )
    assert out == ["D-002 is replaced by D-003, so its block must be `pass`"]


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
    start = src.index("def decisions(t):")
    end = src.index("# === END OF DECISIONS ===")
    src = src[:start] + "def decisions(t):\n" + decisions_body + "\n\n" + src[end:]
    script.write_text(src)
    return inputs, log, script


ENTRY = "## D-001 · 2026-10-22 14:05\nFinding: S3-13, findings_x.tsv\nDecided: Capitalize status.\nChanges data: yes\n"
BODY = (
    "    # D-001\n"
    '    map_values(t["batch_a"], "status", {"healthy": "Healthy"}, decision="D-001")\n'
)


def run_script(script, *args):
    import subprocess

    return subprocess.run(
        [sys.executable, str(script), *map(str, args)], capture_output=True, text=True
    )


def test_end_to_end_draft_run(tmp_path):
    inputs, log, script = make_project(tmp_path, BODY, ENTRY)
    outdir = tmp_path / "out"
    r = run_script(
        script,
        "--inputs",
        inputs,
        "--outdir",
        outdir,
        "--timestamp",
        "20261022-120000",
        "--decision-log",
        log,
    )
    assert r.returncode == 0, r.stderr
    out = (outdir / "2023-04-02_batch_a__draft_20261022-120000.tsv").read_text()
    assert out == "sample_name\tstatus\nS1\tHealthy\nS2\tHealthy\n"
    changes = (outdir / "changes__draft_20261022-120000.tsv").read_text().splitlines()
    assert changes[0].split("\t")[:3] == ["decision", "kind", "file"]
    assert (
        changes[1].split("\t")[:2] == ["D-001", "value changed"] and len(changes) == 2
    )


def test_end_to_end_is_deterministic(tmp_path):
    inputs, log, script = make_project(tmp_path, BODY, ENTRY)
    for ts in ("20261022-120000", "20261022-120100"):
        assert (
            run_script(
                script,
                "--inputs",
                inputs,
                "--outdir",
                tmp_path / "out",
                "--timestamp",
                ts,
                "--decision-log",
                log,
            ).returncode
            == 0
        )
    a = (
        tmp_path / "out" / "2023-04-02_batch_a__draft_20261022-120000.tsv"
    ).read_bytes()
    b = (
        tmp_path / "out" / "2023-04-02_batch_a__draft_20261022-120100.tsv"
    ).read_bytes()
    assert a == b


def test_end_to_end_final_names(tmp_path):
    inputs, log, script = make_project(tmp_path, BODY, ENTRY)
    r = run_script(
        script,
        "--inputs",
        inputs,
        "--outdir",
        tmp_path / "out",
        "--timestamp",
        "20261022-130000",
        "--decision-log",
        log,
        "--final",
    )
    assert r.returncode == 0, r.stderr
    assert (
        tmp_path / "out" / "2023-04-02_batch_a__cleanup_20261022-130000.tsv"
    ).exists()
    assert (tmp_path / "out" / "changes__cleanup_20261022-130000.tsv").exists()


def test_end_to_end_stops_on_log_mismatch(tmp_path):
    inputs, log, script = make_project(tmp_path, "    # D-001\n    pass\n", ENTRY)
    r = run_script(
        script,
        "--inputs",
        inputs,
        "--outdir",
        tmp_path / "out",
        "--timestamp",
        "20261022-120000",
        "--decision-log",
        log,
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
    src = script.read_text().replace(
        '{"batch_a": "2023-04-02_batch_a.txt"}',
        '{"batch_a": "2023-04-02_batch_a.txt", "batch_b": "2023-04-02_batch_b.txt"}',
    )
    script.write_text(src)
    out = tmp_path / "out"
    first = run_script(
        script,
        "--inputs",
        inputs,
        "--outdir",
        out,
        "--timestamp",
        "20261022-120000",
        "--decision-log",
        log,
    )
    assert first.returncode == 0, first.stderr
    assert "same as the per-table outputs in order: yes" in first.stdout
    assert (out / "merged__stacking__draft_20261022-120000.tsv").exists()
    second = run_script(
        script,
        "--inputs",
        inputs,
        "--outdir",
        out,
        "--timestamp",
        "20261022-120100",
        "--decision-log",
        log,
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
