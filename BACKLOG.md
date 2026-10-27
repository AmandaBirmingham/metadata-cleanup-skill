# Backlog

Work still to do on this skill, in priority order. Sessions using the skill
do not read this file; the skill's docs mark each unbuilt piece where it
applies and say what to do in the meantime.

Remove an item when it ships, along with the "planned" marker that points
here. Add newly found gaps in their priority position, or under "Not yet
placed".

## Ordered

1. **Helper for setting an ENA null term.** A cleanup-template function that
   sets a value only if it is a term in `assets/ena_null_terms.tsv`, and
   stops otherwise. The template is copied into each study, so it cannot
   read the asset at run time; the accepted terms must be embedded and kept
   in step with the asset (test that they match). Files:
   `scripts/cleanup_template.py`, tests. Marker: `references/cleanup_script.md`,
   `references/ena_requirements.md`.
2. **Helper for setting a sample type.** As item 1, for the identifiers in
   `assets/sample_types.tsv`, with the label and abbreviation accepted as
   input to map from. Shares item 1's design for embedding a bundled list.
   Marker: `references/cleanup_script.md`, SKILL.md "Lookups".
3. **Excel input.** Both `Table` classes read `.xlsx` (one table per tab),
   every cell as text, and the check script records what Excel stored versus
   what it displays (Stage 0). Adds openpyxl to the dependency blocks.
   Files: `scripts/metadata_profile.py`, `scripts/cleanup_template.py`,
   tests. Marker: `references/table_checks.md`, Stage 0.
4. **Identifier-based merge, with matched/unmatched reporting.** Link
   column, join type and expected cardinality stated and checked; rows with
   an empty link value removed and reported; counts of rows matched, only
   left and only right. Files: `scripts/cleanup_template.py`, tests. Marker:
   `references/cleanup_script.md`.
5. **Formatting helpers, except locale.** Integer `.0` artifacts, booleans,
   and null values (using item 1). Locale-aware numbers are item 15. Files:
   `scripts/cleanup_template.py`, tests. Marker:
   `references/cleanup_script.md`.
6. **Stage 9 key-field variation and confounding.** A check that reports
   counts per value (or range and spread) for each key field, and each pair
   of key fields that vary only together, so the numbers given to the
   scientist come from a check file. Files: `scripts/metadata_profile.py`,
   tests. Spec: `references/merge_and_validation.md`, "Inadequate
   variation".
7. **Missing Stage 3 checks.** Partial-sort damage; values that don't fit the
   column name (M/F in `age`); Excel date serial numbers where an ID or date
   is expected (confirm first whether S3-06 already covers any of these).
   Files: `scripts/metadata_profile.py`, tests. Spec:
   `references/table_checks.md`, Stage 3.
8. **Encoding conversion.** The cleanup template stops on non-UTF-8 input;
   instead, detect the encoding (charset-normalizer) and convert as an
   approved decision that shows every character that changes. Files:
   `scripts/cleanup_template.py`, tests. Spec: `references/table_checks.md`,
   Stage 0.
9. **`scripts/taxon_lookup.py`.** Search the bundled taxonomy without loading
   it whole, report obsolete IDs and their replacements, and check with ENA
   that a taxon is submittable when the network is available. Marker:
   SKILL.md bundled-files table, `references/ena_requirements.md`.
10. **`scripts/envo_lookup.py`.** Search `assets/envo_lookup.tsv` filtered by
    field (biome, environmental system, material), never offering obsolete
    terms. Marker: SKILL.md bundled-files table,
    `references/ena_requirements.md`.
11. **Snapshot of ENA checklist required fields.** A bundled list of the
    required fields of the common checklists, for use offline. Marker:
    `references/ena_requirements.md`.
12. **Merged-table changes reach the per-table copies; Stage 9 consistency
    check.** A change made after merging is applied to every per-table copy
    that holds the field, and a Stage 9 check confirms the per-table copies
    match the merged file for every field they share. Files:
    `scripts/cleanup_template.py`, `scripts/metadata_profile.py`, tests.
    Marker: `references/cleanup_script.md`; spec: SKILL.md "What goes in
    which output", `references/merge_and_validation.md`, Stage 9.
13. **Expected sample and control counts.** A generic, parameterized count
    check (beside `range_check`) comparing non-control and control counts,
    and each control type, with the Phase 1 estimates. Files:
    `scripts/metadata_profile.py`, tests. Spec: SKILL.md Phase 2,
    `references/merge_and_validation.md`, Stage 9.
14. **Time-based merge.** `merge_asof` with direction, maximum window and
    grouping column all stated; rows with an empty date excluded and
    reported; matched/unmatched reporting as in item 4. Marker:
    `references/cleanup_script.md`.
15. **Locale formatting.** Numbers converted from a stated locale with Babel
    (`parse_decimal`), after the scientist confirms the convention. Marker:
    `references/cleanup_script.md`; spec: `references/table_checks.md`,
    Stage 6.
16. **Row number and column letter in the diff page.** Files:
    `scripts/diff_tables.py`, tests. Marker: `references/diff_view.md`,
    "Known gap".
17. **Remaining placeholders,** each needing input from the maintainers:
    - the repository's column names (SKILL.md, "Lookups");
    - which ENVO branches each environment field should draw from, per
      current MIxS guidance (`references/ena_requirements.md`).

## Not yet placed

- **Check that sample types are on the list.** A generic check that flags any
  `sample_type` value that is not an identifier in `assets/sample_types.tsv`.
