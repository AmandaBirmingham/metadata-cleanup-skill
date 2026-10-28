# Backlog

Work still to do on this skill, in priority order. Sessions using the skill
do not read this file; the skill's docs mark each unbuilt piece where it
applies and say what to do in the meantime.

Remove an item when it ships, along with the "planned" marker that points
here (search the skill for "see BACKLOG.md"). Add newly found gaps in their
priority position, or under "Not yet placed".

## Ordered

1. **Check that sample types are on the list.** A generic Stage 3 check that
   flags any `sample_type` value that is not an identifier in
   `assets/sample_types.tsv`; when the value is a label or abbreviation
   there, the finding names its identifier. It runs again at Stage 9, on
   the outputs. Which values were meant as which sample type is left to the
   judgment review. Files: `scripts/metadata_profile.py`, tests. Spec:
   SKILL.md "Lookups".
2. **Check that taxon IDs and ENVO terms exist and are current.** A generic
   check, given the taxon-ID and ENVO-term columns the scientist names, that
   flags values missing from `assets/ncbi_taxonomy.tsv.gz` or
   `assets/envo_lookup.tsv`, and obsolete ones, naming the replacement.
   Streams the taxonomy file, never loading it whole. Like item 1, it runs
   again at Stage 9. Files: `scripts/metadata_profile.py`, tests. Spec:
   `references/ena_requirements.md`, "Taxon IDs" and "ENVO terms".
3. **Excel input.** Both `Table` classes read `.xlsx` (one table per tab),
   every cell as text, and the check script records what Excel stored versus
   what it displays (Stage 0). Adds openpyxl to the dependency blocks.
   Replaces the template reader's stop on other file types. Files:
   `scripts/metadata_profile.py`, `scripts/cleanup_template.py`, tests.
4. **Identifier-based merge, with matched/unmatched reporting.** Link
   column, join type and expected cardinality stated and checked; rows with
   an empty link value removed and reported; counts of rows matched, only
   left and only right. Files: `scripts/cleanup_template.py`, tests.
5. **Formatting helpers, except locale.** Integer `.0` artifacts and
   booleans. Locale-aware numbers are item 13. Files:
   `scripts/cleanup_template.py`, tests.
6. **Stage 9 key-field variation and confounding.** A check that reports
   counts per value (or range and spread) for each key field, and each pair
   of key fields that vary only together, so the numbers given to the
   scientist come from a check file. Files: `scripts/metadata_profile.py`,
   tests. Spec: `references/merge_and_validation.md`, "Inadequate
   variation".
7. **Excel date serial numbers.** A generic Stage 3 check for Excel date
   serial numbers where an ID or date is expected (confirm first whether
   S3-06 already covers them). Files: `scripts/metadata_profile.py`, tests.
   Spec: `references/table_checks.md`, Stage 3.
8. **Encoding conversion.** The cleanup template stops on non-UTF-8 input;
   instead, detect the encoding (charset-normalizer) and convert as an
   approved decision that shows every character that changes. Files:
   `scripts/cleanup_template.py`, tests. Spec: `references/table_checks.md`,
   Stage 0.
9. **Snapshot of ENA checklist required fields.** A bundled list of the
   required fields of the common checklists, for use offline.
10. **Merged-table changes reach the per-table copies; Stage 9 consistency
    check.** A change made after merging is applied to every per-table copy
    that holds the field, and a Stage 9 check confirms the per-table copies
    match the merged file for every field they share. Files:
    `scripts/cleanup_template.py`, `scripts/metadata_profile.py`, tests.
    Spec: SKILL.md "What goes in which output",
    `references/merge_and_validation.md`, Stage 9.
11. **Expected sample and control counts.** A generic, parameterized count
    check (beside `range_check`) comparing non-control and control counts,
    and each control type, with the Phase 1 estimates. Files:
    `scripts/metadata_profile.py`, tests. Spec: SKILL.md Phase 2,
    `references/merge_and_validation.md`, Stage 9.
12. **Time-based merge.** `merge_asof` with direction, maximum window and
    grouping column all stated; rows with an empty date excluded and
    reported; matched/unmatched reporting as in item 4.
13. **Locale formatting.** Numbers converted from a stated locale with Babel
    (`parse_decimal`), after the scientist confirms the convention. Spec:
    `references/table_checks.md`, Stage 6.
14. **Row number and column letter in the diff page.** Files:
    `scripts/diff_tables.py`, tests.
15. **Remaining placeholders,** each needing input from the maintainers:
    - the repository's column names (SKILL.md, "Lookups");
    - which ENVO branches each environment field should draw from, per
      current MIxS guidance (`references/ena_requirements.md`).

## Not yet placed
