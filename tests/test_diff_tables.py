"""Tests for scripts/diff_tables.py."""

import sys

import pytest

import diff_tables

ROWS = [["sample_name", "a", "b"], ["S1", "x", '"""q"""'], ["S2", "y", "z"]]


def run(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["diff_tables.py", *map(str, args)])
    return diff_tables.main()


def test_no_changes_writes_no_page(write, tmp_path, monkeypatch, capsys):
    p = write("p.tsv", ROWS)
    out = tmp_path / "d.html"
    assert run(monkeypatch, p, p, "--key", "sample_name", "--out", out) == 0
    assert "No changes" in capsys.readouterr().out and not out.exists()


def test_changed_cell(write, tmp_path, monkeypatch, capsys):
    new = [r[:] for r in ROWS]
    new[2][1] = "Y"
    out = tmp_path / "d.html"
    run(monkeypatch, write("p.tsv", ROWS), write("n.tsv", new), "--key", "sample_name", "--out", out)
    assert capsys.readouterr().out.startswith("1 rows changed, 0 added, 0 removed")
    page = out.read_text()
    assert '<td class="modify">y→Y</td>' in page
    assert 'class="highlighter"' in page


def test_quotes_compared_literally(write, tmp_path, monkeypatch, capsys):
    new = [r[:] for r in ROWS]
    new[1][2] = '"q"'
    out = tmp_path / "d.html"
    run(monkeypatch, write("p.tsv", ROWS), write("n.tsv", new), "--key", "sample_name", "--out", out)
    assert capsys.readouterr().out.startswith("1 rows changed")
    assert '"""q"""' in out.read_text().replace("&quot;", '"')


def test_rows_and_columns_added_removed(write, tmp_path, monkeypatch, capsys):
    prev = write("p.tsv", ROWS)
    run(monkeypatch, prev, write("n1.tsv", ROWS[:2]), "--key", "sample_name", "--out", tmp_path / "d1.html")
    assert "0 rows changed, 0 added, 1 removed" in capsys.readouterr().out
    wider = [r + [v] for r, v in zip(ROWS, ["c", "1", "2"])]
    run(monkeypatch, prev, write("n2.tsv", wider), "--key", "sample_name", "--out", tmp_path / "d2.html")
    assert "1 columns added" in capsys.readouterr().out


def test_rows_matched_by_key_not_position(write, tmp_path, monkeypatch, capsys):
    reordered = [ROWS[0], ROWS[2], ROWS[1]]
    p = write("p.tsv", ROWS)
    run(monkeypatch, p, write("n.tsv", reordered), "--key", "sample_name", "--out", tmp_path / "d.html")
    out = capsys.readouterr().out
    assert "0 rows changed" in out or "No changes" in out


@pytest.mark.parametrize("problem", ["missing key", "repeated key", "page exists"])
def test_refusals(write, tmp_path, monkeypatch, problem):
    p = write("p.tsv", ROWS)
    out = tmp_path / "d.html"
    if problem == "missing key":
        args = (p, p, "--key", "nope", "--out", out)
    elif problem == "repeated key":
        args = (p, write("n.tsv", ROWS + [ROWS[1]]), "--key", "sample_name", "--out", out)
    else:
        out.write_text("x")
        args = (p, write("n.tsv", ROWS[:2]), "--key", "sample_name", "--out", out)
    with pytest.raises(SystemExit, match="STOPPED"):
        run(monkeypatch, *args)
