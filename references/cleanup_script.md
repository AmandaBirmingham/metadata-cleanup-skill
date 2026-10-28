# The cleanup script

The cleanup script carries out every decision in the decision log that
changes data, and when run on the original input files it produces the
corrected outputs. It does not record decisions: what was decided, and why,
is in the decision log only. Repository staff use the two together to audit
the work, so the script must be readable without the skill installed.

## Starting the script

Copy `scripts/cleanup_template.py` to `cleanup_draft.py`, then edit only
`INPUTS`, `SAMPLE_ID` and the `decisions()` function. Everything after
`# === END OF DECISIONS ===` is the helper layer and stays as it is (for the
one exception, see "Continuing earlier work" in SKILL.md). How to run the
script is in the text at the top of the template.

## Requirements

- **Self-contained, with pinned dependencies.** One Python file. Heavy lifting
  is done by established libraries, declared with exact versions in a PEP 723
  inline metadata block at the top of the script, so `uv run <script>` runs it
  with those versions:
  - pandas — reading tables and merging: `merge(..., validate=..., indicator=True)`
    for identifier-based merges, `merge_asof(..., direction=..., tolerance=...)`
    for time-based matching;
  - openpyxl — `.xlsx` input (`.xls` and `.ods` need other readers);
  - charset-normalizer — encoding detection;
  - Babel — number localization (`parse_decimal` with an explicit locale);
  - standard-library `datetime.strptime` — dates, always with an explicit,
    scientist-confirmed format per column, never a format-guessing parser.

  The same block also tells anyone without `uv` exactly which versions to
  install.
- **A thin embedded layer.** The study-independent code no library provides
  is copied into each script (see "Helper layer" below), not imported from the
  skill.
- **Deterministic.** Same inputs, same outputs, every time. No randomness, no
  network access, no dependence on today's date: the run timestamp is passed
  in or recorded, never used to decide anything.
- **Never writes to the originals or overwrites anything** (SKILL.md, rules
  1 and 2); output names are given under "Structure" below.
- **Always replays from the originals.** Each run applies every decision in
  order, starting from the untouched input files. Never edit an earlier
  output.
- **One draft, edited in place.** While the discussion goes on there is a
  single draft script, `cleanup_draft.py`, which you edit as decisions are
  made. At delivery it is copied, unchanged, to a final timestamped script
  (SKILL.md, Phase 5).

## Structure

1. PEP 723 dependency block (exact versions), then the header: study name,
   scientist, date started, the input file names.
2. Embedded helper layer.
3. **Load:** read each input table as text, with no type conversion. Give every
   row an internal ID from its original file and position (for example,
   `samples.xlsx|Sheet1|row 14`). Decisions refer to rows through this ID
   behind the scenes, so renaming sample IDs later doesn't break earlier
   decisions. Columns likewise get internal IDs (`samples.xlsx|Sheet1|col 3`)
   mapped to the scientist's column names, so the scientist's names can be
   anything, and renaming a column later doesn't break earlier decisions.
4. **Phase A — per-table decisions**, in the order agreed.
5. **Merge decisions.**
6. **Phase B — decisions on the merged table.** Which outputs such a change
   reaches is set out in SKILL.md, "What goes in which output".
7. **Write outputs:** one UTF-8 TSV per input table (a workbook gives one per
   tab), plus the merged TSV. Drafts are named `<file>__draft_<timestamp>.tsv`
   (`<file>__<tab>__draft_<timestamp>.tsv` for a workbook); the final run's
   outputs are named `<file>__cleanup_<timestamp>.tsv`, and the merged one
   `merged__cleanup_<timestamp>.tsv`. Stop if any value contains a tab
   or line break.
8. **Write the change list and the diff.** The change list
   (`changes__draft_<timestamp>.tsv`) has one row per changed cell: decision
   ID, file, row, column, old value, new value. Then call
   `scripts/diff_tables.py` to write the diff between the previous draft
   output and this one (see `diff_view.md`). The change list is mainly for
   you; the diff is what the scientist looks at. A stacked table with no
   earlier draft has nothing to diff against; the run writes
   `<name>__stacking__draft_<timestamp>.tsv` instead (rows from each table,
   totals, and whether the stacked output equals the per-table outputs in
   order) and prints its summary.

## Decision blocks

Every decision in the decision log has one block, headed by its ID alone, in
ID order. A decision that changes data has the code that carries it out; one
that changes nothing is just `pass`. Nothing else goes in the block: what was
decided, and why, is in the decision log.

```python
# D-013
pass

# D-014
rows = select(t["samples"], sample_type="control")
rows = exclude(rows, sample_name=["not-a-blank.12"])
rows = exclude(rows, collection_date="2025-03-04")
set_value(t["samples"], rows, "sample_type", "extraction blank", decision="D-014")
```

When a later decision replaces an earlier one, the earlier block becomes
`pass` and the new block holds the code.

A proposed change is logged before it is shown (SKILL.md, rule 4). If the
scientist rejects it, add a new entry with `Replaces:` naming the proposal
and `Changes data: no`; both blocks are then `pass`, and the rejected
proposal stays in the log as a record.

The script checks itself against the decision log every time it runs, and
stops if they disagree: every ID in the log needs exactly one block, every
block needs an entry, decisions marked "Changes data: yes" need code, those
marked "no" need `pass`, and a replaced decision's block must be `pass`.
Tell the scientist about any mismatch before going on.

## Helper layer

The embedded layer wraps the libraries above and adds what they don't provide:
ID checks, the change list and timestamped output names. It must also force safe library settings:

- always read with pandas `dtype=str, keep_default_na=False, na_filter=False`,
  so `NA`, `None` and empty cells stay as written, no types are guessed, and
  leading zeros survive;
- read text files with `quoting=csv.QUOTE_NONE` as well, so quote characters
  are kept as written. Without it, pandas unwraps quoted cells (`"""x"""`
  becomes `"x"`), an unapproved change. Unwrapping, if the scientist wants
  it, is a decision like any other;
- write every TSV (outputs and the change list) row by row: cells joined by
  tabs, rows ended by a line feed, values exactly as they are. Don't use a
  CSV writer: with quoting turned off, Python's CSV writer refuses values
  that contain a quote character, and with quoting on, it adds quotes that
  weren't there;
- before every merge, remove and report rows whose link value is empty, since
  pandas treats empty or missing link values as matching each other.

Every change function must:

- **stop with a clear message** if:
  - an explicitly listed sample ID doesn't exist;
  - a condition matches no rows at all;
- **record** each changed cell in the change list (decision ID, file, row,
  column, old value, new value).

Available in the template:

- selecting and excluding rows by value, by condition, or by an explicit list
  of IDs (`select`, `exclude`, `matches`);
- setting values (`set_value`);
- mapping values, exact matches only (`map_values`);
- reformatting dates with explicit formats (`reformat_dates`);
- adding, renaming and deleting columns (`add_column`, `rename_column`,
  `delete_column`);
- deleting rows (`delete_rows`);
- whitespace normalization (`normalize_whitespace`);
- stacking tables with the same columns (`stack`), with a stacking report on
  the first draft;
- writing the change list, and calling `scripts/diff_tables.py` for the diff.

Not yet in the template (planned; see BACKLOG.md). Until each exists, write
the code in the decision's block, meeting these requirements:

- **other formatting normalization** (numbers, booleans);
- **merging,** in three forms (see Stage 7 in `merge_and_validation.md`):
  - **identifier-based:** link column, join type and expected cardinality
    checked;
  - **time-based:** pandas `merge_asof`, with the direction (only earlier
    events, only later events, or nearest either way), the maximum time
    window, and the grouping column (for example, subject_id, so one
    subject's events never attach to another's samples) all stated explicitly
    in the code. Both time columns must already be converted to real dates by
    earlier, approved decisions; rows with an empty date are excluded and
    reported;
  - **custom rules** that neither form covers: written as explicit code in the
    decision's block; the rule in plain language is in the decision log;
  - for every form, report matched and unmatched records, and show the diff
    before approval;
- **applying a change made to the merged table to the per-table copies.**

## New or replacement input files

When the scientist supplies a corrected or additional file:

1. Treat it as a new original: never write to it.
2. A replacement keeps the old file's name in the header, marked as
   superseded, so the history is visible.
3. Rerun the check script on the new originals.
4. Rerun the draft cleanup script and show the scientist the diff against the
   previous draft output. What the existing decisions now do to the new file
   must be approved again, and each approval goes into the decision log as a
   new entry.
5. New tables go through Phase 2 before being merged.

## Information that isn't in the metadata

When a rule depends on information that isn't in any table (SKILL.md,
"Information that isn't in the metadata"), the script adds it first as a new
column, by its own decision with the values the scientist supplies; later
decisions refer to that column.
