# The check script

The check script profiles the original files and looks for values that may be
wrong. It changes nothing. What you tell the scientist comes only from its
output files (SKILL.md, Phase 2).

## Parts

- **Generic part,** bundled with this skill (`scripts/metadata_profile.py`):
  the column profile (Stage 3) and the checks in `table_checks.md` that
  apply to any study. Import it; how to call it is at the top of the file.
  Pass the batch columns agreed with the scientist as `batch_columns=[…]`
  (see "Triage" in `table_checks.md`), and any columns approved for the
  coded fallback as `fallback_columns=[…]` (see "Judgment review"). Add a
  `range_check()` for each plausible range the scientist agrees to (in the
  study discussion or at Stage 3). Start `check_script.py` with a copy of
  the dependency block (the `# /// script` lines) at the top of
  `metadata_profile.py`, followed by
  these lines, with `<skill>` replaced by the skill's absolute base
  directory:

  ```python
  import sys
  sys.path.insert(0, "<skill>/scripts")
  from metadata_profile import CheckRun  # noqa: E402
  ```
- **Study-specific part,** which you write: checks that list every row with
  a pattern a review found, and anything else the study discussion calls
  for.

There is one check script, `check_script.py`, which you edit in place when a
check is added.

## The PII-only run

At the start of every session (SKILL.md, Phase 0), run only the PII checks
(S3-05, S3-06), with no check script:

    uv run <skill>/scripts/metadata_profile.py --pii FILE... --sample-id ID \
        --out OUTDIR --timestamp TIMESTAMP

It writes only a findings file, so no other output shows the values it is
looking for. If you don't yet know which column holds the sample IDs, ask
the scientist.

## Reading files

`metadata_profile.py` reads files with the cleanup template's own reader
(see "Helper layer" in `cleanup_script.md`), so the check script sees the
same rows, cells and row numbers as the cleanup script.

## Checks

Each check has a short ID (`S3-04`, `X-02`, …) and a one-line description.
The ID is how the decision log refers to the finding a decision answers.

## Corrected column kinds

The profile guesses each column's kind. When the scientist corrects a guess,
add the correction to `kinds=` in `check_script.py`, rerun it, and record the
correction in the decision log as a decision that changes no data.

## Outputs

Each run writes three new files, named with the run's timestamp:

- **Profile** (`profile_<timestamp>.html`), for the scientist: each
  column's counts, ranges and values, to check against what they know of
  their study.
- **Findings** (`findings_<timestamp>.tsv`): one row per value that may be
  wrong, with the check ID and description, the file, the spreadsheet row
  (header = row 1), the column, the sample ID, the value, and a note. A check
  that finds nothing still gets one row saying so, so "checked, nothing
  found" can be told apart from "not checked". The S3-18 and S3-20 rows
  are coverage instructions, not problems; see "Covering every value" and
  Stage 5 in `table_checks.md`. The PII checks' rows (S3-05, S3-06) never
  show the value.
- **Review** (`review_<timestamp>.tsv`), for you: the values for the
  judgment review, one line per distinct value of each column, with its
  slice number, file, column letter, column, count and first rows.

## When to run it

- at the start of every session, as the PII-only run;
- after the study discussion (or at the start, if there is none), before
  discussing any finding;
- whenever a check is added;
- at Stage 5, on the latest draft outputs rather than the originals;
- once at Stage 9 (final validation), on the latest draft outputs rather
  than the originals, with `stage9_checks()` added;
- whenever the scientist asks.

Don't rerun it after every draft run of the cleanup script; the diff shows
what each change did.
