---
name: metadata-cleanup
description: Help a scientist clean up and complete experimental sample metadata (spreadsheets, CSV/TSV) before submitting it to the repository and to ENA, producing a deterministic script that records every agreed change. Use when someone wants to check, fix, standardize, merge, or prepare study metadata for submission.
---

# Metadata cleanup for repository submission

> **DRAFT.** The work still to do is listed in `BACKLOG.md`. Each unbuilt
> piece is marked once, where it is specified, with what to do in the
> meantime; other mentions point there.

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
2. **Never overwrite outputs.** Every file a script run writes is new, and
   its name carries a timestamp suffix (`YYYYMMDD-HHMMSS`), so the newest
   sorts last; the cleanup script's output names are given under
   "Structure" in `references/cleanup_script.md`. Get the current date and
   time from the system, never from memory. Files you write yourself are
   updated as each one's own description says. When draft outputs pile up,
   ask the scientist whether older ones may be deleted.
3. **Make no decision without the scientist's affirmative consent.** You may
   suggest ("It sounds like all your samples are feces — is that right?"); you
   may not decide. This covers even whitespace and typos, and choices a step
   would otherwise make silently, such as an order, a matching column, or
   which copy to keep: propose each one explicitly before acting. The one
   exception is the output conventions (step 7 of "Structure" in
   `references/cleanup_script.md`), which apply to every output and are
   announced at the start instead. When an answer is hedged or could be
   read more than one way, say how you will record it and invite a
   correction before relying on it.
4. **Show every change before it is approved.** Add the proposed change to the
   decision log as a new entry, add its code to the draft cleanup script, run
   it, and show the scientist the diff between the previous draft output and
   the new one: what the change actually did, cell by cell (see
   `references/diff_view.md`). In the chat, give a summary, the unusual cases,
   and anything left unchanged on purpose. The scientist may approve a whole
   batch at once (for example, all whitespace fixes) once they have seen it, or
   pick out items to discuss individually. If they don't approve, record the
   rejection as described under "Decision blocks" in
   `references/cleanup_script.md` and rerun, so the draft output again matches
   the decisions made so far.
5. **Every change is made by the cleanup script, never by hand.** Discussion and
   investigation can be free-form; changes, additions and deletions happen only
   through code in the cleanup script, rerun from the originals. How each
   decision appears in the script is set out under "Decision blocks" in
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
10. **Label guesses as guesses.** Any explanation you offer for a pattern in
    the data ("probably one shipment", "expected from the design") is a guess
    unless the files or the scientist have established it. Say so and ask;
    never present it as fact or use it to set a finding aside. A problem you
    noticed by judgment, not by a coded check, is presented as your judgment.
11. **Coded checks are a floor, not the whole review.** The check script
    finds what fixed rules can find; possible PII, values meant as missing,
    and many other problems also need your judgment, so read the values for
    them on every run (see "Judgment review" in `references/table_checks.md`).
    Only checking uses judgment: every change is still code (rule 5).
12. **PII is removed before review, not read.** Every session starts with
    Phase 0, and no other review begins until each of its findings is
    resolved; no PII may be kept. If you find possible PII later, by
    judgment, stop and raise it at once. If the scientist confirms it is
    PII, advise that removing it be the session's last decision, followed by
    delivery (Phase 5), and that a new session start from those outputs,
    because otherwise the PII stays in the files you keep reading. You
    cannot enforce this; explain why, and let them choose.

## Starting a session

Work out which situation applies. Whichever it is, Phase 0 comes first once
there is a file, including when the files are the outputs of an earlier
session that removed PII; then bring that session's decision log too.

- **New study, no file yet:** start with the study discussion.
- **New study, file in hand:** do the study discussion briefly first (it decides
  what the metadata must contain), then move to the file.
- **Pre-existing study** (samples already collected, design settled, some
  decisions unknown to the person you are helping): follow "Pre-existing
  studies" in `references/study_discussion.md`, then move to the file.
- **Continuing earlier work:** ask for the latest cleanup script and decision
  log from the previous session, plus the original input files. Compare the
  script's helper layer (everything after `# === END OF DECISIONS ===`) with
  the current template's. If they differ, tell the scientist, and do no
  further work until they match; say what will change in the script before
  changing it. Then rerun the script to confirm it reproduces the last
  outputs, summarize where things stand from the decision log, and continue.

At the start, tell the scientist briefly:

- what will happen: walking through their files together to find values that
  may be wrong or contradict each other, and making formatting consistent,
  with nothing changed without their approval. For a new study, this starts
  with a conversation about the study; if there is no study discussion,
  don't announce that it is skipped;
- that the result is a set of corrected TSV files, a script that makes every
  change, and a log of their decisions, and, in plain words, what the output
  conventions (rule 3) change about the files' form;
- that they may be asked for permission when a script runs, depending on
  their settings, and that this is expected.

Before starting, check that `uv` is installed (`uv --version`); if not, help
them install it, since the scripts run with `uv run`.

Before writing anything, propose an output folder next to the input folder,
named `<input folder>_cleanup` (for inputs in `…/samples`, outputs go to
`…/samples_cleanup`), and ask the scientist to confirm it or name another.
Every output, the decision log and the skill-feedback notes go there.

## Workflow

Work through these phases in order. New or corrected files can arrive at any
point; when they do, follow "New or replacement input files" in
`references/cleanup_script.md`, then redo the later phases.

### Phase 0 — PII

Before reading any value in the files, run only the PII checks on the
original files (see "The PII-only run" in `references/check_script.md`).
Their findings give each place PII may be and the pattern it matched (see
"Outputs" in `references/check_script.md`). Bring each one to the scientist
with its location, so they can look in their own copy, and record how they
resolve it (see `references/pii.md`):

- **not PII:** a decision that changes no data; it is asked again in each
  later session, since the check finds the value again;
- **removed:** a decision carried out by the cleanup script, emptying or
  replacing the cell, deleting the column, or setting the cell to text the
  scientist supplies. Never propose replacement text yourself: that means
  reading the value. Show the change as `references/diff_view.md` says for
  a removal of PII.

If anything was removed, deliver as in Phase 5 and end the session; the
scientist starts a new session with the corrected files as its input files.
If nothing was removed, go on to Phase 1.

### Phase 1 — Study discussion

Follow `references/study_discussion.md`, and record the answers in the
decision log in the study-information layout under "Records"; they are what
the metadata is later checked against.

### Phase 2 — Each table separately

The input may be several files, and a spreadsheet may hold several tables
(tabs). Treat every table separately through these stages; details for each
are in `references/table_checks.md`.

Start by running the check script on the original files, before discussing
any finding with the scientist. Its parts (generic and study-specific) and
its three outputs (a profile for the scientist; findings and review files for
you) are described in `references/check_script.md`.

After every run, give the scientist the profile's full path and ask them to
open it in a browser and look through it: to check that the counts, ranges
and values match what they know of their study, and to tell you anything
that looks wrong or surprising. Wait until they say they have looked at it
before bringing up any finding. Tell them the findings and review files are
working lists for you, so they don't need to open them; you will bring the
findings to them a few at a time.

Every finding, number and location (column letter, spreadsheet row, count)
you bring to the scientist is quoted from these files, never counted,
computed, recalled, or retyped from a one-off command; if you need a number
they don't hold, add a check and rerun it. A problem found in the judgment
review takes its locations from the review file's lines for its values.
When to run the check script is under "When to run it" in
`references/check_script.md`.

Before raising any finding, carry out the judgment review and then the
triage, both in `references/table_checks.md`. From the first run, also
compare the sample and control counts with the Phase 1 estimates, using a
count check written for the study; triage says when to raise a gap.
*(Planned: a generic count check; see BACKLOG.md.)*

If any run's S3-20 rows say "too large: stop", stop: tell the scientist that
their study has too many rows and columns for every row to be read, which
this skill requires, and do no further work on it.

Then work through the stages in `references/table_checks.md` with the
scientist, using its findings: 0 sanity checks, 1 string cleaning, 2 headers,
3 profiling, 4 categorical values, 5 cross-field consistency, 6 formatting.

Present the problems in plain language, a few at a time, in triage order.
Give the location of every value a problem concerns, as the findings file
records it, so the scientist can find it in their own copy; for a problem
found by reading a draft output's rows (Stage 5), give its ID. Each
answer becomes an entry in the decision log; each one that changes data is
carried out in the cleanup script and approved as rule 4 describes.

### Phase 3 — Merging

If there is more than one table, combine them as described in
`references/merge_and_validation.md`: tables with the same columns for
different samples are stacked; tables holding different information are
merged on a link. Before combining, agree with the scientist on every item
in the stacking or merging checklist there. Treat unmatched rows as
information (they may be controls), never as noise to discard.

### Phase 4 — Required fields and final validation

On the merged table, check the required fields (Stage 8) and carry out the
final validation (Stage 9) as `references/merge_and_validation.md` describes.

### Phase 5 — Delivery

When the scientist confirms the discussion is done:

1. Copy the draft cleanup script to a final one, `cleanup_<timestamp>.py`,
   without `draft` in its name. Don't change its code.
2. Run the final script on the original files. Its outputs carry the same
   timestamp, which links them to it; their names are given under
   "Structure" in `references/cleanup_script.md`.
3. If the scientist asks, show the diff between the original files and the
   final outputs.

Deliver:

- the final cleanup script;
- one corrected TSV per input table;
- one merged TSV (if there was more than one table);
- the decision log;
- the skill-feedback notes, for the skill's maintainers;
- the latest profile, findings and review files from the check script;
- a short plain-language summary of what changed, what is still open, how the
  final counts compare with the estimates, any hypothesis or confounder
  field that lacks the variation needed to test it or is confounded with
  another, and every column whose values were checked only by the coded
  fallback, not read.

If the scientist reopens the discussion later, work continues in a new draft
script; the next final version gets its own timestamp, and the decision log
records the reopening.

## What goes in which output

- **Per-table corrected copies** contain only fields that came from that
  table, with all decisions applied to those fields, including corrections
  that were only noticed after merging. *(Not built yet; see "Not yet in the
  template" in `references/cleanup_script.md`.)*
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
  replaces; the original stays as it was.

  Study information (from Phase 1, or learned about the study later) goes in
  entries with this layout, so final validation always finds the same items:

  ```markdown
  ## Study information · 2026-10-22 13:40
  Study status: new study; design can still change
  Purpose: compare skin communities of treated and untreated acne
  Hypotheses: treated subjects resemble healthy controls after two weeks
  Expected non-control samples: about 120
  Expected controls: 8 extraction blanks; 4 mock communities
  Key fields: subject_id, timepoint, treatment; confounders swab_type, site
  Units, vocabularies and precision: age in whole years; timepoint as Week 0/2
  Expected variation: about 60 treated and 60 untreated samples
  Fields that may vary together: unknown
  Host and sample type: human skin swabs; blanks have no host
  ENA: in scope
  ```

  - every line appears in every study-information entry; anything not
    discussed is `unknown`;
  - a later entry that changes any line repeats the whole list, with the
    changed lines updated, and adds
    `Replaces: Study information · <date and time of the earlier entry>`.

  Each decision entry follows this layout exactly, so the cleanup script can
  check itself against the log:

  ```markdown
  ## D-003 · 2026-10-22 14:05
  Finding: S3-08, findings_20261022-101500.tsv
  Decided: Rewrite the 12 sampling_time values in plate_3 as YYYY-MM-DD HH:MM:SS.
  Changes data: yes
  ```

  - the heading has the ID (`D-001`, `D-002`, …, in order) and the date and
    time from the system clock;
  - `Finding:` is the check ID and the findings file it came from, a line
    of a review file (`review line 412, review_20261022-101500.tsv`), a row
    of a draft output (`row 812, samples__draft_20261022-101500.tsv`), or
    `none`;
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

- **NCBI taxonomy** (sample and host taxon IDs) and **ENVO** (the three
  environment fields): how to search the bundled files, check for obsolete
  entries and confirm with ENA is under "Taxon IDs" and "ENVO terms" in
  `references/ena_requirements.md`.
- **Sample types:** `assets/sample_types.tsv` (columns: sample_type, label,
  abbreviation). The metadata holds the `sample_type` identifier
  (`control_blank`), never the label; a label or abbreviation the scientist
  writes (`control blank`, `CSF`) is a candidate to map to its identifier,
  with their approval. Whether each value is on the list, and which values
  were meant as which sample type, is part of the judgment review.
  *(Planned: a coded check that each `sample_type` value is on the list as
  well; see BACKLOG.md.)*
- **Repository column names:** *(placeholder — still to be supplied; see
  BACKLOG.md)*.

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
| `references/check_script.md` | The check script: what it runs and its three output files |
| `references/diff_view.md` | The diff view (daff) used to show each change |
| `references/pii.md` | PII and PHI to watch for |
| `assets/ena_null_terms.tsv` | ENA missing-value terms, with ENA's definitions and plain meanings |
| `assets/sample_types.tsv` | The repository's sample types |
| `assets/envo_lookup.tsv` | ENVO terms; the release is in its `envo_release` column |
| `assets/metagenome_taxa.tsv` | Current NCBI metagenome taxa |
| `assets/ncbi_taxonomy.tsv.gz` | Full NCBI taxonomy list |
| `scripts/build_envo_lookup.py` | Maintainer tool, not used in sessions: rebuilds `envo_lookup.tsv` from an ENVO `.owl` release plus the repository's ENVO term list |
| `scripts/metadata_profile.py` | Generic part of the check script: column profile, generic checks, and the Stage 9 checks |
| `scripts/diff_tables.py` | Diff between two versions of a table (daff), as an HTML page |
| `scripts/cleanup_template.py` | Starting point for the cleanup script: dependency block, helper layer, and the check against the decision log |
| `tests/` | Tests for the bundled scripts, except `scripts/build_envo_lookup.py` *(planned; see BACKLOG.md)* |
| `BACKLOG.md` | Maintainer work list, in priority order; not used in sessions |
| `run_tests.sh` | Runs the tests, in an environment built from the scripts' own dependency blocks |

Change a bundled script only test-first: write a test for the new behaviour
or the bug, run it and see it fail, then change the script until it passes.
Every bug fixed gets its own test. The whole suite in `tests/` must pass
before a changed script is used.