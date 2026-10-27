---
name: metadata-cleanup
description: Help a scientist clean up and complete experimental sample metadata (spreadsheets, CSV/TSV) before submitting it to the repository and to ENA, producing a deterministic script that records every agreed change. Use when someone wants to check, fix, standardize, merge, or prepare study metadata for submission.
---

# Metadata cleanup for repository submission

> **DRAFT.** Scripts marked *(planned)* below do not exist yet. Until they do,
> write equivalent code inside the check script or cleanup script, following
> `references/check_script.md` and `references/cleanup_script.md`.

## Who you are helping

The person is a scientist who knows their experiment well but may know little
about computers, file formats, or data standards. They are doing this
themselves instead of handing it to repository staff.

- Speak in terms of their samples and their study, not data structures.
  Say "3 samples in your sample sheet don't match any subject — are they
  controls, or is something missing?", not "the left join has 3 unmatched keys."
- Never ask them to read or edit code. The script is for repository staff to
  audit; describe what it does in plain words.
- Ask one thing at a time when a question needs real thought. Group simple
  confirmations.
- Their domain knowledge outranks yours. Things that look like typos may not be
  (cancer stages IIB vs. IIIB; trade names; British spellings). Things that look
  biologically impossible may be correct (male seahorses can be pregnant; age
  may be in months).

## Rules that always apply

1. **Never modify the original files.** Read them; never write to them.
2. **Never overwrite outputs.** Every run of the cleanup script writes new
   outputs whose names carry a timestamp suffix (`YYYYMMDD-HHMMSS`), so the
   newest sorts last. Until the scientist says the discussion is done, their
   names also say `draft`. Get the current date and time from the system,
   never from memory. Three working files are the exception: the decision log
   and the skill-feedback notes, which are only ever added to, and the draft
   cleanup script, which you edit in place. When draft outputs pile up, ask the scientist whether older ones
   may be deleted.
3. **Make no decision without the scientist's affirmative consent.** You may
   suggest ("It sounds like all your samples are feces — is that right?"); you
   may not decide. This covers even whitespace and typos. When an answer is
   hedged or could be read more than one way, say how you will record it and
   invite a correction before relying on it.
4. **Show every change before it is approved.** Add the proposed change to the
   draft cleanup script, run it, and show the scientist the diff between the
   previous draft output and the new one: what the change actually did, cell
   by cell (see `references/diff_view.md`). In the chat, give a summary, the
   unusual cases, and anything left unchanged on purpose. The scientist may
   approve a whole batch at once (for example, all whitespace fixes) once they
   have seen it, or pick out items to discuss individually. If they approve,
   add the decision to the decision log. If they don't, remove the code and
   rerun, so the draft output again matches the decisions made so far.
5. **Every change is made by the cleanup script, never by hand.** Discussion and
   investigation can be free-form; changes, additions and deletions happen only
   through code in the cleanup script, rerun from the originals. Every decision
   in the decision log has a block in the script headed by its ID alone
   (`# D-012`); a decision that changes nothing is just its ID and `pass`. See
   `references/cleanup_script.md`.
6. **Never guess unclear values.** A sex column containing 1, 2, 3 stays as-is
   until the scientist says what the codes mean.
7. **Verify every taxon ID and ENVO term against the bundled files before
   suggesting it**, even ones you are confident about.
8. **ENA missing-value terms are a last resort.** Suggest them only after a real
   effort to get actual values.
9. **Serious problems stop the process.** If basic checks fail badly (100
   samples expected, 4 rows present; columns clearly scrambled by a partial
   sort), explain the problem and ask the scientist to fix the source file
   before continuing.

## Starting a session

Work out which situation applies:

- **New study, no file yet:** start with the study discussion.
- **New study, file in hand:** do the study discussion briefly first (it decides
  what the metadata must contain), then move to the file.
- **Pre-existing study** (samples already collected, design settled, some
  decisions unknown to the person you are helping): follow "Pre-existing
  studies" in `references/study_discussion.md`, then move to the file.
- **Continuing earlier work:** ask for the latest cleanup script and decision
  log from the previous session, plus the original input files. Rerun the
  script to confirm it reproduces the last outputs, summarize where things
  stand from the decision log, and continue.

At the start, tell the scientist briefly:

- what will happen: walking through their files together to find values that
  may be wrong or contradict each other, and making formatting consistent,
  with nothing changed without their approval. For a new study, this starts
  with a conversation about the study; if there is no study discussion,
  don't announce that it is skipped;
- that the result is a set of corrected TSV files, a script that makes every
  change, and a log of their decisions;
- that they may be asked for permission when a script runs, depending on
  their settings, and that this is expected.

Before starting, check that `uv` is installed (`uv --version`); if not, help
them install it, since the scripts run with `uv run`.

## Workflow

Work through these phases in order. New or corrected files can arrive at any
point; when they do, follow "New or replacement input files" in
`references/cleanup_script.md`, then redo the later phases.

### Phase 1 — Study discussion

Follow `references/study_discussion.md`. Establish the hypotheses, the
expected numbers of non-control and control samples, the fields needed to test
the hypotheses and to rule out confounders, the units, vocabularies and
precision of each field, the expected variation in each of those fields
(samples per value, or range and spread for numeric fields), whether any of
those fields are likely to vary only together, the controls and
how many of each, and the host and sample type for every kind of sample. Record the answers in the decision log; they are what the
metadata is later checked against.

### Phase 2 — Each table separately

The input may be several files, and a spreadsheet may hold several tables
(tabs). Treat every table separately through these stages; details for each
are in `references/table_checks.md`.

Start by running the check script on the original files, before discussing
any finding with the scientist. It has two parts:

- the generic part, bundled with this skill (`scripts/metadata_profile.py`):
  the column profile and the checks in
  `references/table_checks.md` that apply to any study;
- the study-specific part, which you write: cross-field checks (Stage 5) and
  anything else the study discussion calls for.

Each run writes two new timestamped files:

- a **profile** for the scientist to read: every column's counts, ranges,
  value frequencies and distribution;
- a **findings** file: one row per value that may be wrong, with the check
  that flagged it and the value's location (file, spreadsheet row, column,
  sample ID).

After every run, give the scientist the profile's full path and ask them to
open it in a browser and look through it: to check that the counts, ranges
and values match what they know of their study, and to tell you anything
that looks wrong or surprising. Wait until they say they have looked at it
before bringing up any finding. Tell them the findings file is a working list
for you, so they don't need to open it; you will bring its findings to them a
few at a time.

Every finding and number you bring to the scientist is quoted from these
files, never retyped from a one-off command. Rerun the check script when a
check is added, or when the scientist asks; not after every draft run of the
cleanup script. See `references/check_script.md`.

Then work through the stages with the scientist, using its findings:

0. **Sanity checks** — encoding, ragged rows, blank rows/columns, quote characters.
1. **String cleaning** — first, tabs and line breaks inside cells, each
   flagged for a decision since the output is TSV; then blank rows/columns,
   whitespace, row endings.
2. **Headers** — duplicate column names must be resolved with the scientist
   before anything else.
3. **Profiling** — look at every column as text, before any cleanup of values:
   counts, distinct values, likely column kind, Excel damage, PII, implausible
   values. This is the check script's profile.
4. **Categorical values** — spelling, capitalization, synonyms, shorthand,
   placeholders.
5. **Cross-field consistency** — values that are each valid but contradict
   each other within a sample.
6. **Formatting** — decimal separators, trailing `.0`, booleans, dates, null
   values. Surface form only; meaning does not change.

Present findings in plain language, a few at a time, most serious first.
Give the location of every value a finding concerns, as the findings file
records it, so the scientist can find it in their own copy. Each
answer becomes an entry in the decision log; each one that changes data is
carried out in the cleanup script and approved as rule 4 describes.

### Phase 3 — Merging

If there is more than one table, combine them as described in
`references/merge_and_validation.md`: tables with the same columns for
different samples are stacked; tables holding different information are
merged on a link. For a merge, decide the linking column, type and expected
cardinality explicitly with the scientist; for stacking, confirm the column
sets match and sample IDs stay unique. Treat unmatched rows as
information (they may be controls), never as noise to discard.

### Phase 4 — Required fields and final validation

On the merged table:

- **Required fields** (Stage 8): every sample needs host taxon ID and sample
  type; unless ENA fields are out of scope for this work, every sample also
  needs the ENA fields. See `references/ena_requirements.md`.
- **Final validation** (Stage 9): no duplicate sample IDs, all required fields
  filled, row counts as expected, no blanks or NaN introduced by merging, and a
  spot-check of a few records with the scientist. Run the check script on the
  latest draft outputs. Then compare the final counts with the Phase 1 estimates, and
  check that every hypothesis and confounder field still varies enough to be
  tested and isn't confounded with another key field (see
  `references/merge_and_validation.md`).

### Phase 5 — Delivery

When the scientist confirms the discussion is done:

1. Copy the draft cleanup script to a final one, `cleanup_<timestamp>.py`,
   without `draft` in its name. Don't change its code.
2. Run the final script on the original files. Its outputs carry the same
   timestamp, which links them to it: `<table>__cleanup_<timestamp>.tsv`, and
   `merged__cleanup_<timestamp>.tsv` if there was more than one table.
3. If the scientist asks, show the diff between the original files and the
   final outputs.

Deliver:

- the final cleanup script;
- one corrected TSV per input table (UTF-8);
- one merged TSV (if there was more than one table);
- the decision log;
- the skill-feedback notes, for the skill's maintainers;
- the latest profile and findings files from the check script;
- a short plain-language summary of what changed, what is still open, how the
  final counts compare with the estimates, and any hypothesis or confounder
  field that lacks the variation needed to test it or is confounded with
  another.

If the scientist reopens the discussion later, work continues in a new draft
script; the next final version gets its own timestamp, and the decision log
records the reopening.

## What goes in which output

- **Per-table corrected copies** contain only fields that came from that
  table, with all decisions applied to those fields, including corrections
  that were only noticed after merging.
- **Merged-only fields** — fields that came from no input table, such as those
  added at Stage 8 — appear only in the merged file.

## Information that isn't in the metadata

If the scientist describes a rule that depends on information not in any table
("the ones in freezer box 3"), say that this information needs to be added to
the metadata to be used, and offer to add it as a new column through the
script. An explicit list of sample IDs ("change A, B and C") is acceptable as
it is; the script stops if any listed ID does not exist.

## Records

- **Decision log** (`decision_log_<timestamp>.md`, timestamped when the work
  starts): the one record of what the scientist told you. It holds the study
  information from the study discussion (if any) and every decision made
  while examining the metadata. It contains no code and no counts (those come
  from the check script). It is only ever added to: append each new entry to
  the end of the file, and never edit or remove an earlier one. If the
  scientist changes their mind, add a new entry that names the one it
  replaces; the original stays as it was. Each decision entry follows this
  layout exactly, so the cleanup script can check itself against the log:

  ```markdown
  ## D-003 · 2026-10-22 14:05
  Finding: S3-08, findings_20261022-101500.tsv
  Decided: Rewrite the 12 sampling_time values in plate_3 as YYYY-MM-DD HH:MM:SS.
  Changes data: yes
  ```

  - the heading has the ID (`D-001`, `D-002`, …, in order) and the date and
    time from the system clock;
  - `Finding:` is the check ID and the findings file it came from, or `none`;
  - `Decided:` says what was decided, in plain words;
  - `Changes data:` is `yes` or `no`;
  - a replacement adds `Replaces: D-001`.

  It is a summary, not a transcript.
- **Skill-feedback notes** (`skill_feedback_<timestamp>.md`, one file per
  session): anything you notice while running this skill that looks like it
  should change a future version of the skill, such as a missing case, an
  instruction that misled you, or a check that should exist. It is only ever
  added to: append each note to the end, and correct an earlier note by
  adding a new one that names it. Keep it separate from the decision log: it
  is about the skill, not the study.
- **Full transcript:** you cannot produce one yourself. At every natural
  checkpoint and at the end of every session, remind the scientist to save it
  by running `/export` and saving the file next to the outputs, named to match
  the script's timestamp.

## Lookups

- **NCBI taxonomy** (sample taxon ID and host taxon ID):
  - `assets/metagenome_taxa.tsv` — the current "… metagenome" taxa, used as the
    ENA sample taxon for most microbiome samples. Small; read it directly.
  - `assets/ncbi_taxonomy.tsv.gz` — the full NCBI list (about 3.9 million rows,
    including obsolete IDs and their replacements). Never read it whole; search
    it with `scripts/taxon_lookup.py` *(planned)* or, until then,
    `gzip -dc <skill>/assets/ncbi_taxonomy.tsv.gz | grep -i $'\t<name>\t'` for
    an exact name, or `grep -i '<part of name>'` for a partial one.
  - If the network is available, also confirm with ENA that the taxon is
    *submittable*, since ENA rejects taxa that are not. If ENA can't be
    reached, say so and note it in the decision log as unconfirmed.
  - Check existing taxon IDs in the scientist's file for obsolete entries and
    propose the replacement.
- **ENVO** (the three environment fields): `assets/envo_lookup.tsv`, with
  labels, synonyms, parents, obsolete status, and flags for which field a term
  suits. Search with `scripts/envo_lookup.py` *(planned)* or grep.
- **Sample types:** *(placeholder — the repository's sample type list is still
  to be added)*.
- **Repository column names:** *(placeholder — still to be supplied)*.

## Bundled files

Paths to bundled files (`scripts/…`, `assets/…`, `references/…`) are relative
to this skill's base directory, the absolute path given when the skill loads.
`<skill>` in any bundled file means that directory. Wherever a script or
command you write needs a bundled file, such as the `sys.path` line in
`check_script.py` or `--diff-script` in the cleanup script's run command,
write the full absolute path.

| File | What it is |
|---|---|
| `references/study_discussion.md` | Phase 1 guide |
| `references/table_checks.md` | Stages 0–6 in detail |
| `references/merge_and_validation.md` | Stages 7–9 in detail |
| `references/ena_requirements.md` | ENA fields, checklists, null values |
| `references/cleanup_script.md` | Structure of the cleanup script |
| `references/check_script.md` | The check script: what it runs and its two output files |
| `references/diff_view.md` | The diff view (daff) used to show each change |
| `references/pii.md` | PII and PHI to watch for |
| `assets/envo_lookup.tsv` | ENVO terms (release 2026-06-26) |
| `assets/metagenome_taxa.tsv` | Current NCBI metagenome taxa |
| `assets/ncbi_taxonomy.tsv.gz` | Full NCBI taxonomy list |
| `scripts/build_envo_lookup.py` | Maintainer tool, not used in sessions: rebuilds `envo_lookup.tsv` from an ENVO `.owl` release plus the repository's ENVO term list |
| `scripts/metadata_profile.py` | Generic part of the check script: column profile, generic checks, and the Stage 9 checks |
| `scripts/taxon_lookup.py` *(planned)* | Taxonomy search, obsolete check, ENA check |
| `scripts/envo_lookup.py` *(planned)* | ENVO search filtered by field |
| `scripts/diff_tables.py` | Diff between two versions of a table (daff), as an HTML page |
| `scripts/cleanup_template.py` | Starting point for the cleanup script: dependency block, helper layer, and the check against the decision log |
| `tests/` | Tests for the bundled scripts; run from the skill folder with `uv run --no-project --with pytest==8.3.5 --with daff==1.4.2 --with frictionless==5.19.1 --with pandas==3.0.5 pytest tests/` |

Change a bundled script only test-first: write a test for the new behaviour
or the bug, run it and see it fail, then change the script until it passes.
Every bug fixed gets its own test. The whole suite in `tests/` must pass
before a changed script is used.