# The cleanup script

The cleanup script carries out every decision in the decision log that
changes data, and when run on the original input files it produces the
corrected outputs. It does not record decisions: what was decided, and why,
is in the decision log only. Repository staff use the two together to audit
the work, so the script must be readable without the skill installed.

## Starting the script

Copy `scripts/cleanup_template.py` to `cleanup_draft.py`, then edit only
`INPUTS`, `ID_COLUMNS` (each table's ID column; see "The PII-only run" in
`check_script.md`) and the `decisions()` function. Everything after
`# === END OF DECISIONS ===` is the helper layer and stays as it is (for the
one exception, see "Continuing earlier work" in SKILL.md). How to run the
script is in the text at the top of the template.

## Requirements

- **Self-contained, with pinned dependencies.** One Python file. Heavy lifting
  is done by established libraries, declared with exact versions in a PEP 723
  inline metadata block at the top of the script, so `uv run <script>` runs it
  with those versions; the header of `scripts/cleanup_template.py` says how
  to run it without `uv`. Dates are always read and written with an
  explicit, scientist-confirmed format per column, never a format-guessing
  parser.
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

1. PEP 723 dependency block (exact versions), then the header (see the top
   of the template).
2. The input files and the decisions, then the embedded helper layer after
   `# === END OF DECISIONS ===`.

Each run then carries out these steps:

3. **Load:** read each input table as text, with no type conversion.
   Decisions select rows by their values and are replayed in order from the
   originals, so renaming sample IDs or columns later doesn't break earlier
   decisions.
4. **Phase A — per-table decisions**, in the order agreed.
5. **Merge decisions.**
6. **Phase B — decisions on the merged table.** Which outputs such a change
   reaches is set out in SKILL.md, "What goes in which output".
7. **Write outputs:** one TSV per input table (a workbook gives one per
   tab), plus the merged TSV. Until the scientist says the discussion is
   done, outputs are drafts, named `<file>__draft_<timestamp>.tsv`
   (`<file>__<tab>__draft_<timestamp>.tsv` for a workbook); the final run's
   outputs are named `<file>__cleanup_<timestamp>.tsv`, and the merged one
   `merged__cleanup_<timestamp>.tsv`. Stop if any value contains a tab or
   line break, or if a repeated or blank column name has not been renamed
   or deleted by a decision. Every output follows the same conventions,
   whatever the original's form, and they are the only changes made without
   a decision (SKILL.md, rule 3): tab-separated, UTF-8 with no byte-order
   mark, and every row ended by a line feed (LF).
8. **Write the change list and the diff.** The change list
   (`changes__draft_<timestamp>.tsv`) has one row per change: a changed
   cell, or a column or row added, renamed or deleted. A change to a row
   of a stacked table gives the file, row and column letter the row came
   from. Then call `scripts/diff_tables.py` to write the diff between the
   previous draft output and this one (see `diff_view.md`). The change list is mainly for
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
rows = select(t["samples"], sample_type="control blank")
rows = exclude(rows, sample_name=["not-a-blank.12"])
rows = exclude(rows, collection_date="2025-03-04")
set_value(t["samples"], rows, "sample_type", "control_blank", decision="D-014")
```

When a later decision replaces an earlier one, the earlier block becomes
`pass` and the new block holds the code.

A proposed change is logged before it is shown (SKILL.md, rule 4). If the
scientist rejects it, add a new entry with `Replaces:` naming the proposal
and `Changes data: no`; both blocks are then `pass`, and the rejected
proposal stays in the log as a record.

The script checks itself against the decision log every time it runs, and
stops if they disagree: every ID in the log needs exactly one entry and
exactly one block, every block needs an entry, decisions marked "Changes
data: yes" need code, those marked "no" need `pass`, a replaced decision's
block must be `pass`, and `Replaces:` must name an ID in the log.
Tell the scientist about any mismatch before going on.

## Helper layer

The embedded layer wraps the libraries and adds what they don't provide:
reading, ID checks, the change list and timestamped output names. It must:

- read every cell as text, exactly as written, with no type guessing, so
  `NA`, `None` and empty cells stay as written and leading zeros survive;
- read a TSV by splitting rows on line feeds and cells on tabs, so quote
  characters are kept as data; unwrapping them, if the scientist wants it,
  is a decision like any other. A CSV is parsed the standard way, since in
  CSV the quotes are part of the format, not the data;
- write every TSV (outputs and the change list) row by row: cells joined by
  tabs, rows ended by a line feed, values exactly as they are. Don't use a
  CSV writer: with quoting turned off, Python's CSV writer refuses values
  that contain a quote character, and with quoting on, it adds quotes that
  weren't there.

Every change function must:

- **stop with a clear message** if:
  - an explicitly listed sample ID doesn't exist;
  - a condition matches no rows at all;
- **record** each change in the change list (Structure, step 8).

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

Not yet in the template. Until each exists, write the code in the
decision's block, meeting the requirements where each is specified:

- **other formatting normalization** (numbers, booleans): Stage 6 in
  `table_checks.md`;
- **merging:** Stage 7 in `merge_and_validation.md`;
- **applying a change made to the merged table to the per-table copies,**
  and checking at Stage 9 that they match the merged file for every field
  they share *(planned; see BACKLOG.md)*. Until then, after merging, compare
  the fields they share with a study-specific check.

## New or replacement input files

When the scientist supplies a corrected or additional file:

1. Treat it as a new original: never write to it.
2. Record a replacement in the decision log as a decision that changes no
   data, naming the file it supersedes, so the history is visible.
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
