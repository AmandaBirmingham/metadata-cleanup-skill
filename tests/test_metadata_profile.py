"""Tests for scripts/metadata_profile.py."""

import re

import pytest

import cleanup_template as ct
import metadata_profile as mp
from metadata_profile import CheckRun, Table


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def hits(paths, cid, sample_id="sample_name", **kw):
    """Findings of one generic check, without the 'no findings' row."""
    run = CheckRun([str(p) for p in paths], sample_id=sample_id, **kw)
    run.generic_checks()
    return [h for h in run.run() if h[0] == cid and h[8] != "no findings"]


def table(write, rows, name="t.tsv"):
    return Table(write(name, rows))


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
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
    assert mp.column_letter(i) == letter


def test_display_name_strips_upload_prefix(tmp_path):
    assert (
        mp.display_name(tmp_path / "5e17a0c3-2023-04-02_batch_b.txt")
        == "2023-04-02_batch_b.txt"
    )
    assert (
        mp.display_name(tmp_path / "deadbeef-notes.txt") == "deadbeef-notes.txt"
    )  # no date after prefix
    assert mp.display_name(tmp_path / "samples.tsv") == "samples.tsv"


@pytest.mark.parametrize(
    "v,ok",
    [
        ("2022-02-09 06:52:00", True),
        ("2/9/22 6:52", True),
        ("2022-02", True),
        ("2022", True),
        ("9606", False),
        ("56", False),
        ("812604319", False),
        ("1799", False),
        ("2101", False),
        ("hello", False),
    ],
)
def test_parse_date(v, ok):
    assert (mp.parse_date(v)[0] is not None) == ok


@pytest.mark.parametrize(
    "name",
    [
        "sample_id",
        "SampleID",
        "sampleId",
        "taxid",
        "host_taxid",
        "identifier",
        "shipping_number",
        "bottle_number",
        "reagent_lot",
        "barcode",
        "site_code",
        "id",
        "ID",
        "accession",
    ],
)
def test_label_names(name):
    assert mp.is_label_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "humidity",
        "acidity",
        "liquid_volume",
        "valid",
        "oxidation",
        "num_reads",
        "depth_m",
        "age",
        "station",
    ],
)
def test_not_label_names(name):
    assert not mp.is_label_name(name)


@pytest.mark.parametrize(
    "x,s",
    [
        (812604319.0, "812604319"),
        (715208846132.0, "715208846132"),
        (53.2648, "53.26"),
        (0.000123456, "0.0001235"),
        (7.15208e11, "715208000000"),
        (-2.5, "-2.5"),
        (0.0, "0"),
        (1.5e20, "150000000000000000000"),
    ],
)
def test_fmt_never_exponential(x, s):
    assert mp._fmt(x) == s
    assert "e" not in mp._fmt(x).lower()


# ---------------------------------------------------------------------------
# column kind guesses
# ---------------------------------------------------------------------------
def test_column_kind_guesses():
    ck = mp.column_kind
    assert ck([str(x) for x in range(100)]) == "numeric"
    assert ck(["1", "2", "3"] * 10) == "categorical (numbers)"
    assert ck([str(x) for x in range(100)], name="sample_id") == "identifier"
    assert ck(["9606"] * 50, name="host_taxid") == "categorical (numbers)"
    assert ck(["2025-01-%02d" % d for d in range(1, 29)]) == "date/time"
    assert ck(["red", "blue"] * 20) == "categorical"
    assert ck([f"S{i}" for i in range(100)]) == "identifier"
    assert ck([f"note number {i} here" for i in range(100)]) == "free text"
    assert ck(["", "not provided", "not applicable"]) == "empty or null only"


@pytest.mark.parametrize(
    "v",
    [
        "",
        "not applicable",
        "not collected",
        "not provided",
        "restricted access",
        "missing: control sample",
        "missing: sample group",
        "missing: synthetic construct",
        "missing: lab stock",
        "missing: third party data",
        "missing: data agreement established pre-2023",
        "missing: endangered species",
        "missing: human-identifiable",
    ],
)
def test_is_null_ena_terms(v):
    assert mp.is_null(v)


def test_is_null_other_values():
    assert not mp.is_null("missing")
    assert not mp.is_null("Not Provided")
    assert not mp.is_null("NA")


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------
def test_tsv_read_literally(write):
    t = table(
        write, [["sample_name", "note"], ["S1", '"""quoted"""'], ["S2", 'a "b" c']]
    )
    assert t.rows[0]["note"] == '"""quoted"""'
    assert t.rows[1]["note"] == 'a "b" c'
    assert [r.line for r in t.rows] == [2, 3]


def test_csv_parsed_standard_way(write):
    p = write("t.csv", 'sample_name,note\nS1,"a, b"\nS2,"line one\nline two"\n')
    t = Table(p)
    assert t.kind == "csv"
    assert t.rows[0]["note"] == "a, b"
    assert t.rows[1]["note"] == "line one\nline two"


def test_table_unreadable_suffix_stops(write):
    with pytest.raises(mp.Stop, match="cannot read .xlsx"):
        Table(write("t.xlsx", None, raw=b"PK\x03\x04"))


def test_table_row_numbers_match_cleanup_template(write):
    p = write("t.tsv", "sample_name\ta\nS1\tx\n\nS2\ty\n")
    profile_lines = [r.line for r in Table(p).rows]
    cleanup_rows = list(ct.Table("T", p).df.index)
    assert (profile_lines, cleanup_rows) == (
        [2, 3, 4],
        ["T|row 2", "T|row 3", "T|row 4"],
    )


def test_duplicate_and_blank_column_names_kept_apart(write):
    t = table(write, [["sample_name", "status", "status", ""], ["S1", "a", "b", "c"]])
    assert t.keys == ["sample_name", "status", "status [col C]", "[col D]"]
    assert t.rows[0]["status"] == "a" and t.rows[0]["status [col C]"] == "b"
    assert t.letter("status [col C]") == "C"


def test_short_rows_padded(write):
    t = table(write, [["sample_name", "a", "b"], ["S1", "x"]])
    assert t.rows[0]["b"] == "" and t.rows[0].cells == ["S1", "x"]


def test_crlf_bom_and_latin1(write):
    t = Table(write("crlf.tsv", "sample_name\ta\r\nS1\tx\r\n"))
    assert t.crlf_lines == 2 and t.rows[0]["a"] == "x"
    t = Table(write("bom.tsv", None, raw=b"\xef\xbb\xbfsample_name\ta\nS1\tx\n"))
    assert t.bom and t.header[0] == "sample_name"
    t = Table(
        write(
            "latin.tsv", None, raw="sample_name\tsite\nS1\tS\xe3o\n".encode("latin-1")
        )
    )
    assert not t.utf8 and t.rows[0]["site"] == "S\xe3o"


# ---------------------------------------------------------------------------
# generic checks: each fires on a bad file and not on a clean one
# ---------------------------------------------------------------------------
CLEAN = [["sample_name", "a"], ["S1", "x"], ["S2", "y"]]


# S3-18 lists values for judgment review, so it has rows even for a clean file
@pytest.mark.parametrize("cid", [c for c, _, _ in mp.GENERIC_CHECKS if c != "S3-18"])
def test_clean_file_has_no_findings(write, cid):
    assert hits([write("clean.tsv", CLEAN)], cid, as_of="2026-10-22") == []


def test_s0_01_not_utf8(write):
    assert (
        len(
            hits(
                [
                    write(
                        "l.tsv",
                        None,
                        raw="sample_name\ta\nS1\t\xe3\n".encode("latin-1"),
                    )
                ],
                "S0-01",
            )
        )
        == 1
    )


def test_s0_02_bom(write):
    assert (
        len(
            hits(
                [write("b.tsv", None, raw=b"\xef\xbb\xbfsample_name\ta\nS1\tx\n")],
                "S0-02",
            )
        )
        == 1
    )


def test_s0_03_ragged(write):
    h = hits(
        [write("t.tsv", "sample_name\ta\tb\nS1\tx\nS2\tx\ty\tz\nS3\tx\ty\n")], "S0-03"
    )
    assert [x[3] for x in h] == ["2", "3"]


def test_s0_04_blank_row(write):
    h = hits([write("t.tsv", [["sample_name", "a"], ["S1", "x"], ["", ""]])], "S0-04")
    assert [x[3] for x in h] == ["3"]


def test_s0_05_blank_column(write):
    h = hits([write("t.tsv", [["sample_name", "", "a"], ["S1", "", "x"]])], "S0-05")
    assert len(h) == 1 and h[0][4] == "B"


def test_s0_06_quotes_cell_and_row(write):
    h = hits([write("t.tsv", [["sample_name", "a"], ["S1", '"""x"""']])], "S0-06")
    assert len(h) == 1 and h[0][7] == '"""x"""' and 'read CSV-style: "x"' in h[0][8]
    h = hits([write("t.tsv", 'sample_name\ta\tb\nS1\t"x\ty"\tz\n')], "S0-06")
    assert len(h) == 1 and "a quote wraps a tab" in h[0][8]


def test_s0_06_not_for_csv(write):
    assert hits([write("t.csv", 'sample_name,a\nS1,"x"\n')], "S0-06") == []


def test_s1_01_breaks_in_csv(write):
    h = hits([write("t.csv", 'sample_name,a\nS1,"one\ntwo"\nS2,"t\tab"\n')], "S1-01")
    assert len(h) == 2


def test_s1_02_spaces(write):
    h = hits(
        [
            write(
                "t.tsv",
                [
                    ["sample_name", "a"],
                    ["S1", "x "],
                    ["S2", " x"],
                    ["S3", "x  y"],
                    ["S4", "x y"],
                ],
            )
        ],
        "S1-02",
    )
    assert [x[3] for x in h] == ["2", "3", "4"]
    h = hits([write("t2.tsv", [["sample_name", "a "], ["S1", "x"]])], "S1-02")
    assert len(h) == 1


def test_s1_03_unusual_space(write):
    h = hits(
        [write("t.tsv", [["sample_name", "a"], ["S1", "x y"], ["S2", "x​y"]])], "S1-03"
    )
    assert ["U+00A0" in h[0][8], "U+200B" in h[1][8]] == [True, True]


def test_s1_04_crlf(write):
    assert len(hits([write("t.tsv", "sample_name\ta\r\nS1\tx\r\n")], "S1-04")) == 1


def test_s2_01_duplicate_names(write):
    h = hits([write("t.tsv", [["sample_name", "a", "a"], ["S1", "x", "y"]])], "S2-01")
    assert len(h) == 1 and "columns B, C" in h[0][8]


def test_s2_02_values_without_name(write):
    h = hits([write("t.tsv", [["sample_name", ""], ["S1", "x"]])], "S2-02")
    assert len(h) == 1 and h[0][4] == "B"


def test_s3_01_02_03_column_pairs(write):
    rows = [["sample_name", "a", "b", "c", "d", "e"]]
    for i in range(40):
        rows.append(
            [
                f"S{i}",
                f"v{i}",
                f"v{i}",
                f"V{i}",
                f"v{i}" if i else "other",
                "not provided",
            ]
        )
    rows.append(["S99", "", "", "", "", "not provided"])
    p = write("t.tsv", rows)
    assert {h[5] for h in hits([p], "S3-01")} == {"a = b"}
    assert {h[5] for h in hits([p], "S3-02")} == {"a = c", "b = c"}
    three = {h[5]: h[8] for h in hits([p], "S3-03")}
    assert set(three) == {"a = d", "b = d"}  # 40 of 41 rows agree; row 2 differs
    assert three["a = d"] == "1 rows differ: rows 2"


def test_s3_01_skips_pairs_of_null_only_columns(write):
    p = write(
        "t.tsv",
        [
            ["sample_name", "a", "b"],
            ["S1", "not provided", "not provided"],
            ["S2", "", ""],
        ],
    )
    assert hits([p], "S3-01") == []


def test_s3_04_null_only(write):
    h = hits(
        [write("t.tsv", [["sample_name", "a"], ["S1", "not provided"], ["S2", ""]])],
        "S3-04",
    )
    assert len(h) == 1 and h[0][5] == "a"


@pytest.mark.parametrize(
    "name",
    [
        "patient_name",
        "phone",
        "email",
        "dob",
        "date_of_birth",
        "bday",
        "subject_bday",
        "zip_code",
        "mrn",
    ],
)
def test_s3_05_pii_names(write, name):
    assert (
        len(hits([write("t.tsv", [["sample_name", name], ["S1", "x"]])], "S3-05")) == 1
    )


@pytest.mark.parametrize(
    "name", ["sample_name", "scientific_name", "geo_loc_name", "host_common_name"]
)
def test_s3_05_not_pii_names(write, name):
    assert hits([write("t.tsv", [["sample_name", name], ["S1", "x"]])], "S3-05") == []


@pytest.mark.parametrize(
    "value,label",
    [
        ("(858) 534-2230", "phone"),
        ("858-534-2230", "phone"),
        ("8585342230", "10-digit"),
        ("123-45-6789", "SSN"),
        ("me@example.org", "email"),
        ("19840312", "date"),
    ],
)
def test_s3_06_pii_values(write, value, label):
    h = hits([write("t.tsv", [["sample_name", "a"], ["S1", value]])], "S3-06")
    assert len(h) == 1 and label in h[0][8]


def test_s3_06_many_values_become_one_finding(write):
    rows = [["sample_name", "lot"]] + [[f"S{i}", "230517"] for i in range(30)]
    h = hits([write("t.tsv", rows)], "S3-06")
    assert len(h) == 1 and "30 values" in h[0][8]


def test_s3_07_gene_dates(write):
    h = hits(
        [
            write(
                "t.tsv",
                [
                    ["sample_name", "gene"],
                    ["S1", "1-Mar"],
                    ["S2", "Sep-02"],
                    ["S3", "MARCH1"],
                ],
            )
        ],
        "S3-07",
        fallback_columns=["gene"],
    )
    assert [x[7] for x in h] == ["1-Mar", "Sep-02"]


def test_s3_08_mixed_date_formats(write):
    rows = (
        [["sample_name", "d"]]
        + [[f"S{i}", f"2022-02-{i + 1:02d} 13:08"] for i in range(9)]
        + [["S9", "2/9/22 6:52"]]
    )
    h = hits([write("t.tsv", rows)], "S3-08")
    assert [x[7] for x in h] == ["2/9/22 6:52"]


def test_s3_08_digit_count_is_not_a_format_change(write):
    rows = [
        ["sample_name", "d"],
        ["S1", "7/1/26"],
        ["S2", "11/16/25"],
        ["S3", "7/21/26"],
    ]
    assert hits([write("t.tsv", rows)], "S3-08") == []


def test_s3_09_future_date(write):
    p = write(
        "t.tsv", [["sample_name", "d"], ["S1", "2025-01-01"], ["S2", "2031-01-01"]]
    )
    assert [x[7] for x in hits([p], "S3-09", as_of="2026-10-22")] == ["2031-01-01"]
    assert hits([p], "S3-09") == []  # no as-of date: not checked


def test_s3_10_partial_dates(write):
    p = write(
        "t.tsv",
        [["sample_name", "d"], ["S1", "2025-01-01"], ["S2", "2025-06"], ["S3", "2024"]],
    )
    assert [x[7] for x in hits([p], "S3-10")] == ["2025-06", "2024"]


def test_s3_09_10_taxon_id_is_not_a_year(write):
    p = write(
        "t.tsv", [["sample_name", "host_taxid"]] + [[f"S{i}", "9606"] for i in range(5)]
    )
    assert hits([p], "S3-09", as_of="2026-10-22") == [] and hits([p], "S3-10") == []


def test_s3_11_heaping(write):
    rows = [["sample_name", "age", "sample_id"]] + [
        [f"S{i}", str(5 * (i % 9 + 1)), str(5 * i)] for i in range(30)
    ]
    h = hits([write("t.tsv", rows)], "S3-11")
    assert [x[5] for x in h] == ["age"]  # sample_id is a label, not a number


def test_s3_12_leading_zeros(write):
    h = hits(
        [write("t.tsv", [["sample_name", "code_x"], ["S1", "007"], ["S2", "8"]])],
        "S3-12",
    )
    assert len(h) == 1


def test_s3_13_case_variants(write):
    h = hits(
        [
            write(
                "t.tsv",
                [
                    ["sample_name", "sex"],
                    ["S1", "Female"],
                    ["S2", "female"],
                    ["S3", "male"],
                ],
            )
        ],
        "S3-13",
    )
    assert len(h) == 1 and "Female=1; female=1" in h[0][8]


def test_s3_14_near_duplicates(write):
    rows = [
        ["sample_name", "status"],
        ["S1", "Healthy"],
        ["S2", "Heathy"],
        ["S3", "Treatment_Arm_2"],
        ["S4", "Treatment_Arm_3"],
    ]
    h = hits([write("t.tsv", rows)], "S3-14", fallback_columns=["status"])
    assert len(h) == 1 and "Healthy" in h[0][8]  # Arm_2 / Arm_3 differ only in digits


def test_s3_14_large_column(write):
    rows = [["sample_name", "status"]] + [
        [f"S{i}", f"site {i:03d}x"] for i in range(60)
    ]
    rows += [["S60", "Healthy"], ["S61", "Heathy"]]
    h = hits([write("t.tsv", rows)], "S3-14", fallback_columns=["status"])
    assert [x[8] for x in h] == [
        "Healthy=1; Heathy=1 (typo, or genuinely different? ask)"
    ]


@pytest.mark.parametrize("cid", ["S3-07", "S3-14"])
def test_s3_07_14_only_on_fallback_columns(write, cid):
    rows = [
        ["sample_name", "gene"],
        ["S1", "1-Mar"],
        ["S2", "Healthy"],
        ["S3", "Heathy"],
    ]
    assert hits([write("t.tsv", rows)], cid) == []


def test_fallback_column_unknown_refused(write):
    with pytest.raises(ValueError, match="fallback_columns"):
        CheckRun(
            [str(write("t.tsv", CLEAN))],
            sample_id="sample_name",
            fallback_columns=["plate"],
        )


def test_s3_15_duplicate_ids_across_tables(write):
    a = write("a.tsv", [["sample_name", "x"], ["S1", "1"], ["S2", "2"]])
    b = write("b.tsv", [["sample_name", "x"], ["S2", "3"]])
    h = hits([a, b], "S3-15")
    assert len(h) == 2 and all(x[6] == "S2" for x in h)


def test_s3_16_scientific_notation(write):
    h = hits(
        [
            write(
                "t.tsv",
                [
                    ["sample_name", "shipping_number"],
                    ["S1", "7.15208E+11"],
                    ["S2", "715208846132"],
                ],
            )
        ],
        "S3-16",
    )
    assert [x[7] for x in h] == ["7.15208E+11"]


def test_s3_16_identifier_column_says_digits_lost(write):
    rows = [["sample_name", "shipping_number", "conc"], ["S1", "7.15208E+11", "1.2E-3"]]
    h = hits([write("t.tsv", rows)], "S3-16")
    notes = {x[5]: x[8] for x in h}
    assert notes == {"shipping_number": mp.SCI_ID_NOTE, "conc": mp.SCI_NOTE}


LONG_NOTE = "Participant reported the tube leaked slightly in transit"
OTHER_NOTE = "Collected two days late because of a holiday weekend closure"


def review_lines(paths, column, **kw):
    """Review-file lines for one column, as (value, count, rows)."""
    run = CheckRun([str(p) for p in paths], sample_id="sample_name", **kw)
    return [(x[4], x[5], x[6]) for x in run.review_lines() if x[3] == column]


def test_review_lines_list_each_distinct_value_once(write):
    rows = [["sample_name", "notes"]] + [[f"S{i}", "not provided"] for i in range(20)]
    rows += [["S20", LONG_NOTE], ["S21", "Jo"], ["S22", LONG_NOTE], ["S23", ""]]
    assert review_lines([write("t.tsv", rows)], "notes") == [
        (LONG_NOTE, "2", "22, 24"),
        ("Jo", "1", "23"),
    ]


def test_review_lines_numeric_column_lists_only_non_numbers(write):
    rows = [["sample_name", "depth"]] + [[f"S{i}", str(i)] for i in range(30)]
    rows += [["S30", "unknwn"], ["S31", "5m"]]
    assert review_lines([write("t.tsv", rows)], "depth") == [
        ("unknwn", "1", "32"),
        ("5m", "1", "33"),
    ]


def test_review_lines_list_every_value_and_shorten_row_lists(write):
    rows = [["sample_name", "notes"]] + [[f"S{i}", f"note {i}"] for i in range(300)]
    rows += [[f"T{i}", "same"] for i in range(12)]
    found = review_lines([write("t.tsv", rows)], "notes")
    assert (len(found), found[-1]) == (
        301,
        ("same", "12", "302, 303, 304, 305, 306, 307, 308, 309, 310, 311 (+2 more)"),
    )


def test_review_lines_include_pii_pattern_values(write):
    # PII is removed before review, so what is left (confirmed not PII) is read
    rows = [
        ["sample_name", "notes", "dob"],
        ["S1", "call 858-534-2230", "1984-03-12"],
        ["S2", "fine", "1990-01-01"],
    ]
    p = write("t.tsv", rows)
    assert (review_lines([p], "notes"), review_lines([p], "dob")) == (
        [("call 858-534-2230", "1", "2"), ("fine", "1", "3")],
        [("1984-03-12", "1", "2"), ("1990-01-01", "1", "3")],
    )


def test_review_lines_slices_and_s3_18_coverage(write, monkeypatch):
    monkeypatch.setattr(mp, "REVIEW_SLICE_CHARS", 60)
    monkeypatch.setattr(mp, "REVIEW_DIRECT_MAX_CHARS", 100)
    monkeypatch.setattr(mp, "REVIEW_MAX_SLICES", 2)
    rows = [["sample_name", "a", "b"]]
    rows += [[f"S{i}", f"alpha{i}", f"beta{i}"] for i in range(4)]
    p = write("t.tsv", rows)
    run = CheckRun([str(p)], sample_id="sample_name")
    run.generic_checks()
    slices = [(x[0], x[3]) for x in run.review_lines()]
    summary = [(h[5], h[8]) for h in run.run() if h[0] == "S3-18"]
    assert (slices, summary) == (
        [
            ("1", "sample_name"),
            ("1", "sample_name"),
            ("2", "sample_name"),
            ("2", "sample_name"),
            ("3", "a"),
            ("3", "a"),
            ("4", "a"),
            ("4", "a"),
            ("5", "b"),
            ("5", "b"),
            ("6", "b"),
            ("6", "b"),
        ],
        [
            (
                "sample_name",
                "4 values in the review file, slices 1-2: split across helpers",
            ),
            ("a", "4 values in the review file, slices 3-4: split across helpers"),
            ("b", "4 values in the review file, slices 5-6: split across helpers"),
        ],
    )


@pytest.mark.parametrize(
    "direct,max_slices,advice",
    [
        (10_000, 50, "read directly"),
        (10, 50, "split across helpers"),
        (10, 0, "too large: fallback"),
    ],
)
def test_s3_18_coverage_advice(write, monkeypatch, direct, max_slices, advice):
    monkeypatch.setattr(mp, "REVIEW_DIRECT_MAX_CHARS", direct)
    monkeypatch.setattr(mp, "REVIEW_MAX_SLICES", max_slices)
    p = write("t.tsv", [["sample_name", "a"], ["S1", "x"]])
    h = hits([p], "S3-18")
    assert [x[8].split(": ", 1)[1] for x in h] == [advice, advice]


# ---------------------------------------------------------------------------
# PII checks: their findings never show values; they can run alone
# ---------------------------------------------------------------------------
def test__finding_pii_checks_show_no_value(write):
    p = write(
        "t.tsv",
        [["sample_name", "notes"], ["S1", "call 858-534-2230 "], ["S2", "fine "]],
    )
    found = [h[3:9] for h in hits([p], "S1-02") + hits([p], "S3-06")]
    assert found == [
        ("2", "B", "notes", "S1", "call 858-534-2230 ", ""),
        ("3", "B", "notes", "S2", "fine ", ""),
        ("2", "B", "notes", "S1", "", "phone number pattern"),
    ]


def test_pii_checks(write):
    run = CheckRun([str(write("t.tsv", CLEAN))], sample_id="sample_name")
    run.pii_checks()
    assert [c[0] for c in run.checks] == list(mp.PII_CHECKS)


def test_write_findings(write, tmp_path):
    p = write("t.tsv", [["sample_name", "dob"], ["S1", "1984-03-12"]])
    run = CheckRun([str(p)], sample_id="sample_name")
    run.pii_checks()
    out = tmp_path / "out"
    f = run.write_findings(out, "t1")
    assert (sorted(x.name for x in out.iterdir()), f) == (
        ["findings_t1.tsv"],
        out / "findings_t1.tsv",
    )
    with pytest.raises(FileExistsError):
        run.write_findings(out, "t1")


def test_main_pii_only(write, tmp_path):
    p = write(
        "t.tsv",
        [["sample_name", "phone", "notes"], ["S1", "x", "mail a@b.org"]],
    )
    out = tmp_path / "out"
    argv = ["--pii", str(p), "--sample-id", "sample_name"]
    argv += ["--out", str(out), "--timestamp", "t1"]
    assert mp.main(argv) == 0
    lines = (out / "findings_t1.tsv").read_text().splitlines()
    found = [tuple(x.split("\t")[i] for i in (0, 5, 7, 8)) for x in lines[1:]]
    assert (sorted(x.name for x in out.iterdir()), found) == (
        ["findings_t1.tsv"],
        [
            ("S3-05", "phone", "", "column name suggests PII or PHI (see pii.md)"),
            ("S3-06", "notes", "", "email address"),
        ],
    )


def batch_rows(odd_dates=True):
    """Three packages of three samples, plus two blanks with no package."""
    rows = [["sample_name", "package", "collected", "shipping_number", "comment"]]
    for p, start in (("P1", 1), ("P2", 4), ("P3", 7)):
        for i in range(start, start + 3):
            odd = p == "P3" and odd_dates
            date = f"2/{i}/22 6:52" if odd else f"2022-02-{i:02d} 06:52:00"
            ship = "7.15208E+11" if odd else f"71520884613{i % 10}"
            rows.append([f"S{i}", p, date, ship, f"note {'x' * i} {i}"])
    rows += [
        ["B1", "not applicable", "2022-02", "not applicable", "not applicable"],
        ["B2", "not applicable", "2022-02", "not applicable", "not applicable"],
    ]
    return rows


def test_s3_19_batch_written_differently(write):
    h = hits([write("t.tsv", batch_rows())], "S3-19", batch_columns=["package"])
    assert sorted((x[5], x[8].split(":")[0]) for x in h) == [
        ("collected", "package P3 (rows 8-10)"),
        ("shipping_number", "package P3 (rows 8-10)"),
    ]


def test_s3_19_damage_spanning_two_batches(write):
    rows = batch_rows()
    for r in rows[1:10]:  # five boxes of samples; boxes 4 and 5 hold all of P3
        r.append(
            {
                "S1": "K1",
                "S2": "K1",
                "S3": "K2",
                "S4": "K2",
                "S5": "K3",
                "S6": "K3",
                "S7": "K4",
                "S8": "K4",
                "S9": "K5",
            }[r[0]]
        )
    rows[0].append("box")
    rows[9][2] = "2/10/22 6:52"
    rows[10].append("not applicable")
    rows[11].append("not applicable")
    rows.insert(10, ["S10", "P3", "2/11/22 6:52", "7.15208E+11", "note x 10", "K5"])
    h = hits([write("t.tsv", rows)], "S3-19", batch_columns=["box"])
    assert sorted((x[5], x[8].split(":")[0]) for x in h) == [
        ("collected", "box K4 (rows 8-9)"),
        ("collected", "box K5 (rows 10-11)"),
        ("shipping_number", "box K4 (rows 8-9)"),
        ("shipping_number", "box K5 (rows 10-11)"),
    ]


def test_s3_19_uniform_batches_not_flagged(write):
    assert (
        hits(
            [write("t.tsv", batch_rows(odd_dates=False))],
            "S3-19",
            batch_columns=["package"],
        )
        == []
    )


def test_s3_19_groups_by_file_without_batch_columns(write):
    rows = batch_rows()
    a = write("a.tsv", [rows[0]] + rows[1:4])
    b = write("b.tsv", [rows[0]] + rows[4:7])
    c = write("c.tsv", [rows[0]] + rows[7:10])
    h = hits([a, b, c], "S3-19")
    assert sorted((x[2], x[5]) for x in h) == [
        ("c.tsv", "collected"),
        ("c.tsv", "shipping_number"),
    ]


def test_s3_19_needs_two_values_in_a_group(write):
    rows = batch_rows(odd_dates=False)
    rows[7][2] = rows[8][2] = "not provided"
    rows[9][2] = "2/9/22 6:52"  # P3's only date: one value is not a batch pattern
    assert hits([write("t.tsv", rows)], "S3-19", batch_columns=["package"]) == []


def test_s3_19_unknown_batch_column_refused(write):
    with pytest.raises(ValueError, match="batch_columns"):
        CheckRun(
            [str(write("t.tsv", CLEAN))],
            sample_id="sample_name",
            batch_columns=["plate"],
        )


# ---------------------------------------------------------------------------
# run, findings and locations
# ---------------------------------------------------------------------------
def test_finding_location(write):
    p = write(
        "5e17a0c3-2023-04-02_x.tsv", [["sample_name", "a", "b"], ["S1", "x", "y "]]
    )
    (h,) = hits([p], "S1-02")
    assert h[2:9] == ("2023-04-02_x.tsv", "2", "C", "b", "S1", "y ", "")


def test_no_findings_row(write):
    run = CheckRun([str(write("t.tsv", CLEAN))], sample_id="sample_name")
    run.generic_checks()
    rows = [h for h in run.run() if h[0] == "S0-03"]
    assert rows == [
        (
            "S0-03",
            "row has a different number of cells from the header",
            "",
            "",
            "",
            "",
            "",
            "",
            "no findings",
        )
    ]


def test_duplicate_check_id_refused(write):
    run = CheckRun([str(write("t.tsv", CLEAN))], sample_id="sample_name")
    run.add("X-01", "one", lambda t: ())
    with pytest.raises(ValueError):
        run.add("X-01", "two", lambda t: ())


def test_study_specific_check(write):
    run = CheckRun(
        [
            str(
                write(
                    "t.tsv",
                    [
                        ["sample_name", "type", "material"],
                        ["S1", "control", "sea water"],
                        ["S2", "control", "sterile water"],
                    ],
                )
            )
        ],
        sample_id="sample_name",
    )

    @run.check("X-01", "control whose material says sea water")
    def _(t):
        for r in t.rows:
            if r["type"] == "control" and r["material"] == "sea water":
                yield r, "material"

    (h,) = run.run()
    assert h[0] == "X-01" and h[3] == "2" and h[4] == "C" and h[6] == "S1"


def test_range_check(write):
    p = write(
        "t.tsv",
        [
            ["sample_name", "age", "age_units", "bmi", "depth_m"],
            ["S1", "95", "years", "70", "-1"],
            ["S2", "40", "years", "25", "3"],
        ],
    )
    run = CheckRun([str(p)], sample_id="sample_name")
    run.range_check("age", 0, 90)
    (h,) = run.run()
    assert h[0] == "R-age" and h[7] == "95" and h[1] == "age below 0 or above 90"


def test_stage9_checks(write):
    p = write(
        "t.tsv",
        [["sample_name", "host_taxid"], ["S1", "9606"], ["S2", ""], ["S3", "nan"]],
    )
    run = CheckRun([str(p)], sample_id="sample_name")
    run.stage9_checks(
        required=["host_taxid", "sample_type"], expected_rows={"t.tsv": 4}
    )
    out = run.run()
    assert [h[3] for h in out if h[0] == "S9-01"] == ["3", "4"]
    assert [(h[3], h[5]) for h in out if h[0] == "S9-02"] == [
        ("3", "host_taxid"),
        ("4", "host_taxid"),
        ("", "sample_type"),
    ]
    assert [h[8] for h in out if h[0] == "S9-03"] == ["3 data rows; expected 4"]


# ---------------------------------------------------------------------------
# column-kind corrections
# ---------------------------------------------------------------------------
def test_kinds_validated(write):
    p = str(write("t.tsv", CLEAN))
    with pytest.raises(ValueError, match="no column named"):
        CheckRun([p], sample_id="sample_name", kinds={"aa": "categorical"})
    with pytest.raises(ValueError, match="is not one of"):
        CheckRun([p], sample_id="sample_name", kinds={"a": "category"})


def test_kind_correction_changes_checks_and_profile(write, tmp_path):
    rows = [["sample_name", "station"]] + [
        [f"S{i}", str(5 * (i % 9 + 1))] for i in range(30)
    ]
    p = write("t.tsv", rows)
    assert len(hits([p], "S3-11")) == 1
    assert hits([p], "S3-11", kinds={"station": "categorical"}) == []
    run = CheckRun([str(p)], sample_id="sample_name", kinds={"station": "categorical"})
    _, prof, _ = run.write(tmp_path / "out", "t1")
    page = prof.read_text()
    assert "set by scientist: <b>categorical (numbers)</b>" in page
    assert "guess: <b>identifier</b>" in page


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------
def test_write_outputs_and_refuse_overwrite(write, tmp_path):
    p = write("t.csv", 'sample_name,note\nS1,"tab\there"\n')
    run = CheckRun([str(p)], sample_id="sample_name")
    run.generic_checks()
    f, prof, rev = run.write(tmp_path / "out", "t1")
    lines = f.read_text().split("\n")
    assert lines[0].split("\t") == [
        "check",
        "description",
        "file",
        "spreadsheet_row",
        "column_letter",
        "column",
        "sample_id",
        "value",
        "note",
    ]
    assert all(len(line.split("\t")) == 9 for line in lines if line)
    assert any(
        "tab\\there" in line for line in lines
    )  # tabs inside values shown, not split
    assert prof.exists()
    assert rev.read_text().split("\n")[0].split("\t") == [
        "slice",
        "file",
        "column_letter",
        "column",
        "value",
        "count",
        "rows",
    ]
    with pytest.raises(FileExistsError):
        run.write(tmp_path / "out", "t1")
    rev.unlink()
    with pytest.raises(FileExistsError):  # the other two still exist
        run.write(tmp_path / "out", "t1")


def test_profile_content(write, tmp_path):
    rows = [["sample_name", "age", "taxid", "lot"]]
    rows += [
        [f"S{i}", str(20 + i), "9606" if i % 2 else "10090", str(812604319 + i)]
        for i in range(60)
    ]
    run = CheckRun([str(write("t.tsv", rows))], sample_id="sample_name")
    _, prof, _ = run.write(tmp_path / "out", "t1")
    page = prof.read_text()
    assert (
        "guess: <b>numeric</b>" in page and "mean 49.5" in page
    )  # age: numeric summary
    taxid = page[page.index(": taxid</h3>") : page.index(": lot</h3>")]
    assert "mean" not in taxid and taxid.index("9606") < taxid.index(
        "10090"
    )  # sorted by value
    lot = page[page.index(": lot</h3>") :]
    assert "mean" not in lot and "10 examples from throughout the column" in lot
    assert not re.search(r"\d\.\d+e[+-]\d", page, re.I)  # no exponential notation
    assert "looks like" not in page and "(a guess)" not in page


def test_tables_with_same_layout_pooled(write, tmp_path):
    a = write("a.tsv", [["sample_name", "x"], ["S1", "1"]])
    b = write("b.tsv", [["sample_name", "x"], ["S2", "2"]])
    c = write("c.tsv", [["sample_name", "y"], ["S3", "3"]])
    run = CheckRun([str(a), str(b), str(c)], sample_id="sample_name")
    _, prof, _ = run.write(tmp_path / "out", "t1")
    page = prof.read_text()
    assert (
        "Tables: 2 files, 2 rows, 2 columns" in page
        and "Table: 1 file, 1 rows, 2 columns" in page
    )


# ---------------------------------------------------------------------------
# checks done by frictionless
# ---------------------------------------------------------------------------
def test_s0_07_duplicate_rows(write):
    h = hits(
        [write("t.tsv", [["sample_name", "a"], ["S1", "x"], ["S2", "y"], ["S1", "x"]])],
        "S0-07",
    )
    assert [x[3] for x in h] == ["4"]


def test_s3_17_truncated_value(write):
    long = "a" * 255  # a common spreadsheet / database length limit
    h = hits(
        [write("t.tsv", [["sample_name", "note"], ["S1", long], ["S2", "short"]])],
        "S3-17",
    )
    assert [(x[3], x[5]) for x in h] == [("2", "note")]


def test_structural_checks_ignore_null_terms_in_number_columns(write):
    # frictionless would report type errors here if columns weren't all read as text
    p = write("t.tsv", [["sample_name", "age"], ["S1", "45"], ["S2", "not applicable"]])
    run = CheckRun([str(p)], sample_id="sample_name")
    run.generic_checks()
    # S3-18 lists values for judgment review, so its rows are not problems
    found = [h for h in run.run() if h[8] != "no findings" and h[0] != "S3-18"]
    assert found == []


def test_structural_checks_keep_quotes_literal(write):
    # with CSV-style quoting this file has a quote wrapping a tab; read literally it is
    # a ragged row, which is what S0-03 must report
    h = hits([write("t.tsv", 'sample_name\ta\tb\nS1\t"x\ty"\tz\n')], "S0-03")
    assert len(h) == 1 and h[0][3] == "2" and "4 cells" in h[0][8]


def test_frictionless_failure_is_not_silent(write, monkeypatch):
    class Report:
        def flatten(self, spec):
            return [["resource-error", None, None, "cannot open the file"]]

    monkeypatch.setattr(mp.frictionless, "validate", lambda *a, **k: Report())
    run = CheckRun([str(write("t.tsv", CLEAN))], sample_id="sample_name")
    run.generic_checks()
    with pytest.raises(RuntimeError, match="frictionless could not check"):
        run.run()
