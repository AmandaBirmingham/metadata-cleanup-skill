# Phase 2 — Checks for each table (Stages 0–6)

Run every stage on every table. One file may hold several tables (spreadsheet
tabs). Report findings to the scientist in plain language; each answer goes
into the decision log, and each fix that changes data is carried out in the
cleanup script (see `cleanup_script.md`).

When several tables share one layout (the same columns in batches of
samples), most findings will be the same for all of them. Report such a
finding once, for all the tables, and give per-table detail only where the
tables differ.

## Triage

After the first check run, and before raising any finding, work through the
whole findings file. The stages below say what each check looks for; triage
decides the order in which the scientist hears about it.

1. **Group.** Findings that fall on the same rows, or within the same
   batch-like group (input file, package, plate, manifest, storage unit, or
   whatever marks a batch in this study), often share one cause. A batch
   whose dates and identifiers are both written oddly was probably damaged
   by a spreadsheet program, and that is one problem, not two. Treat each
   group as one problem. The check script finds batches written differently
   from most others (S3-19), comparing input files and each column passed as
   `batch_columns`; before the first run, ask the scientist which columns
   mark batches in this study.
2. **Rank.** Order the problems, most serious first:
   1. information lost or corrupted: damaged identifiers (scientific
      notation, truncation), partial sorts, spreadsheet damage;
   2. sample identity: repeated or mismatched sample IDs;
   3. possible PII or PHI;
   4. contradictions between fields;
   5. counts that differ from the Phase 1 estimates;
   6. inconsistent category values;
   7. cosmetic formatting.
3. **Present** each problem with all of its affected rows and every check
   involved, in ranked order.

## Stage 0 — Sanity checks

- **Encoding.** Not always ASCII or UTF-8. Identify it; converting to UTF-8 is a
  decision (show any characters that change).
- **Ragged rows.** Rows with more or fewer fields than the header are
  error-prone. Report where they occur, and offer to reformat the table
  (as a decision) if that would make it easier to work with.
- **Blank rows and columns.** Entirely empty rows, and columns with no header
  and no values. Their presence raises the risk of a partial sort (some
  columns sorted, others not), which scrambles which values belong to which
  sample.
- **Quote characters.** Compare the file read with quotes kept as written
  (see "Helper layer" in `cleanup_script.md`) against a CSV-style reading,
  and report every cell that differs. Whether to unwrap them is a decision
  for the scientist: ask, never guess.
- **Excel files.** Read every cell as text, but also record what Excel stored
  versus what it displays (for example, displays `1-Mar`, stored as a date).
  This catches some values Excel has already converted. It cannot help with
  a CSV that Excel has already saved; there, look for the patterns listed in
  Stage 3. *(Neither bundled script reads Excel yet; see BACKLOG.md. Until
  they do, write the reading code in the check and cleanup scripts, as
  described here.)*

## Stage 1 — String cleaning

Each of these is shown as a diff (SKILL.md, rule 4), and may be approved as a batch.

Do these in order:

1. **Tabs and line breaks inside a cell** break TSV output. Flag each one
   first and ask how it should be handled (replace with a space, with a
   separator such as `; `, or something else). They are never included in a
   batch normalization.
2. Remove entirely blank rows and entirely blank columns.
3. Report any other unusual whitespace (non-breaking spaces, zero-width
   characters), then normalize every cell, headers included:
   - strip leading and trailing whitespace;
   - collapse runs of internal spaces (including non-breaking spaces) to one
     space.
4. Convert the file's row endings to LF (CRLF → LF). This concerns the ends of
   rows, not line breaks inside cells, which step 1 has already resolved.

## Stage 2 — Headers

Column names can be whatever the scientist chose, but **no two columns may have
the same name**. If there are duplicates, work through them with the scientist
(rename, merge, or drop) before going further.

## Stage 3 — Profiling

> Look and think. Take a real look at what you have before deciding what to
> do with it.

Profile the values **as text, before any value cleanup**. Never let software
guess types. Columns are usually one of: identifier, categorical, numeric,
date/time, or free text. Classifying them takes judgment, not just type
inference:

- A column of integers may be categorical (taxon_id; cage_id = 4 is a label).
- Leading zeros are often essential information and must never be dropped.
- A column of unique values is likely a sample identifier if they don't fall
  into a biological vocabulary. But identifiers of other things (subject) are
  not expected to be unique, and some unique columns are measurements (blood glucose). Use the
  column name, and ask.
- Categorical: few distinct values (roughly 20 or fewer), or matches a
  controlled vocabulary.
- Numeric: quantitative values that support arithmetic. Much of the world uses
  a comma as the decimal separator.
- Date/time: many formats exist (`1/15/26`, `2026-01-15`, `2026`, `15-1-2026`,
  `15.01.2026`). Partial dates (a year only) are valid as dates; whether they
  are acceptable for a particular field must be confirmed.
- Anything else is free text.

### Whole-table checks

- **Row count.** Does it match what the scientist expects? ("You collected 100
  samples, but there are 4 rows — why?")
- **Column count.** Does it make sense? Thousands of columns may be valid in
  some domains (ASVs as metadata), but ask.
- **Partial-sort damage.** Look for signs that some columns were sorted
  independently of others, especially if there were blank rows or columns.
- **Columns that duplicate each other.** Compare every pair of columns:
  identical in every row; identical except for capitalization; identical in
  at least 95% of rows (list the rows that differ). Such pairs are often
  intended, but ask which to keep.

### Every column

- Counts of filled values, empty values, and distinct values.
- Column name suggesting PII or PHI (see `pii.md`).
- Values that don't fit the header (a column named `age` containing M/F; a
  column named `sex` containing CA, MA, FL).
- Columns containing only empty or null values (including ENA null terms).
- PII in unexpected places. Birthdates have turned up as 4–6 digit numbers in a
  column labeled "zipcode".
- Long free text in any column, whatever its guessed kind: the check script
  lists each distinct value of 40 or more characters containing a space
  (S3-18). Read every one for PII/PHI before raising the first finding.

Sample values from throughout the column, never only the first or last rows:
files are often sorted, which makes a column look uniform when it isn't.

### Probable identifier columns

- Look at a spread of values to understand their format.
- PII patterns (SSN format `###-##-####`, etc.).
- Excel date serial numbers (`44927` where an ID or date is expected).

### Probable categorical columns

- List every distinct value with its frequency.
- Gene names converted to dates by Excel (`1-Mar`, `2-Sep`, `1-Dec`).
- Inconsistencies:
  - mixed case for the same concept (Female, female, FEMALE);
  - mixed abbreviations (F, f, fem);
  - near-duplicates that *might* be typos (Healthy / Heathy; Arm / Arrm).
- **Near-duplicates need domain knowledge.** IIB and IIIB look like typos of
  each other but are different cancer stages. Always ask.

### Probable numeric columns

- Leading zeros: the field is probably not a number (maybe an ID or a date).
- Minimum, maximum, mean, median, rough distribution.
- PII patterns: 10-digit numbers that look like phone numbers (8585342230);
  6- or 8-digit numbers that look like dates (281025, 28102025, 20251028).
- Excel date serial numbers.
- Round numbers that occur suspiciously often (80% of ages are multiples of 5),
  suggesting estimates or hidden categories.
- Biologically implausible values: negative concentrations, volumes or
  depths; zeros where zero is impossible. What is plausible depends on the
  domain, so ask: in many but not all human studies, age > 90 or = 0 and/or
  BMI < 14 or > 60 are implausible. Range checks agreed in the study
  discussion are already in the check script. For other columns, when going
  through the profile with the scientist, use `suggest_range_columns()` to
  find columns whose names suggest a range and ask about each; add
  `range_check()` for those they agree to, and rerun the check script.

### Probable date columns

- Dates in the future (compare with today's date from the system). Some
  people use future dates as placeholders for missing information, which later
  become plausible past dates — ask about any that look like placeholders.
- Dates in the remote past (can be correct for historical or archaeological
  work).
- Collection dates outside the study period.
- Birthdates (PII).

### Probable free-text columns

- PII patterns: phone numbers ((858) 534-2230); personal names (Jane Doe,
  J. Doe, Doe J); see `pii.md`.
- Gene names converted to dates. The conversions differ by Excel's language:
  AGO2 → Aug-02 (Italian, Spanish, Portuguese), MEI1 → May-01 (Dutch),
  TAMM41 → Jan-41 (Finnish). Source:
  https://lastwordonnothing.com/2024/08/14/whats-in-a-gene-name/
- Gene names "autocorrected" into words (thisbe → "this be").

If profiling reveals serious problems, stop and ask the scientist to fix the
source (rule 9 in SKILL.md).

## Stage 4 — Categorical values

Typical fixes to propose — a typical but not exhaustive list (never apply
without approval):

- **Misspellings.** Microbial Insittute → Microbial Institute. Risky: British
  and American spellings, trade names, and real terms that resemble typos.
- **Capitalization.** healthy, Healthy → healthy.
- **Synonyms.** F, f, female, Female, FEMALE → female.
- **Shorthand.** Week 4, W4, wk4 → Week 4, after confirming they are the same
  timepoint.
- **Placeholders → ENA null terms.** For example, body_site = not applicable
  for controls, blanks or samples with no host.
- **Leave unclear values alone.** 1, 2, 3 in a sex column: do not guess.
- **Offer values already in use.** When a value needs replacing, offer the
  values the file already uses for the same thing before proposing a new
  one.

## Stage 5 — Cross-field consistency

Values can each be valid yet contradict each other within one sample. This is
common where the scientist copied subject-level information onto every sample
by hand. Domain knowledge makes these checks far more effective, so ask the
scientist which combinations matter in their field.

Raise each contradiction as a question, not a correction. Show how the
sample differs from comparable samples in the same file, offer the
explanations you can see, and ask which applies.

Choose checks that fit this study, for example:

- diagnosis and treatment pairs;
- BMI, height and weight together;
- environmental material and sample type pairs;
- control status against sample type, material and sample taxon;
- country against location name and coordinates;
- measured values against their stated units;
- the same subject_id with different birth years.

For each check, identify samples with **definite or possible**
inconsistencies, and say which is which. Examples of things to flag:

- 5 human male samples with pregnant = True;
- a sterile water blank with diseased = True;
- 2 samples with the same subject_id but different birth_year values.

Examples of things that are not errors:

- human ages above 120 where the unit is months;
- male seahorses with pregnant = True.

If the scientist confirms that flagged values are correct, record that in the
decision log as a decision that changes no data.

## Stage 6 — Formatting

Changes surface form only, never meaning.

- **Numbers:** localize to en_US: `.` as the decimal separator, no thousands separator
  (100,2 → 100.2; 5,280 → 5280). Confirm which convention the file uses before
  converting; `5,280` is ambiguous.
- **Integers:** remove spreadsheet `.0` artifacts (9606.0 → 9606).
- **Booleans:** one form (TRUE, true, Yes, 1 → True).
- **Dates:** the format each field requires (03/17/2026, March 17 at 5pm,
  2026-3-17 → 2026-03-17). Not every date field uses the same format. Never invent
  precision: `2026` stays a year unless the scientist supplies more.
- **Nulls:** N/A, NA, n/a, None, empty → the right ENA null term, chosen with
  the scientist for each case (see `ena_requirements.md`). For example:
  - N/A, NA, n/a, None or empty in a field the scientist was asked for but
    did not supply → `not provided`;
  - empty in a field that does not apply to this sample type →
    `not applicable`.
