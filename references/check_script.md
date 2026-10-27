# The check script

The check script profiles the original files and looks for values that may be
wrong. It changes nothing. What you tell the scientist comes only from its
output files (SKILL.md, Phase 2).

## Parts

- **Generic part,** bundled with this skill (`scripts/metadata_profile.py`):
  the column profile (Stage 3) and the checks in `table_checks.md` that
  apply to any study. Import it; how to call it is at the top of the file.
  Pass the batch columns agreed with the scientist as `batch_columns=[…]`
  (see "Triage" in `table_checks.md`).
  Start `check_script.py` with a copy of the dependency block (the
  `# /// script` lines) at the top of `metadata_profile.py`, followed by
  these lines, with `<skill>` replaced by the skill's absolute base
  directory:

  ```python
  import sys
  sys.path.insert(0, "<skill>/scripts")
  from metadata_profile import CheckRun  # noqa: E402
  ```
- **Study-specific part,** which you write: cross-field checks (Stage 5) and
  anything else the study discussion calls for.

There is one check script, `check_script.py`, which you edit in place when a
check is added.

## Reading and writing files

Read the files exactly as the cleanup script does, and write the findings
file the same way it writes TSV (see "Helper layer" in `cleanup_script.md`):
every cell as text, nothing converted, quote characters kept.

## Checks

Each check has a short ID (`S3-04`, `X-02`, …) and a one-line description.
The ID is how the decision log refers to the finding a decision answers.

## Corrected column kinds

The profile guesses each column's kind. When the scientist corrects a guess,
add the correction to `kinds=` in `check_script.py`, rerun it, and record the
correction in the decision log as a decision that changes no data.

## Outputs

Each run writes two new files, named with the run's timestamp:

- **Profile** (`profile_<timestamp>.html`), for the scientist to read: for
  every column, counts of filled, empty and distinct values; for numeric
  columns, minimum, maximum, mean, median and distribution; for categorical
  columns, every value with its frequency.
- **Findings** (`findings_<timestamp>.tsv`): one row per value that may be
  wrong, with the check ID and description, the file, the spreadsheet row
  (header = row 1), the column, the sample ID, the value, and a note. A check
  that finds nothing still gets one row saying so, so "checked, nothing
  found" can be told apart from "not checked".

## When to run it

- after the study discussion (or at the start, if there is none), before
  discussing any finding;
- whenever a check is added;
- once at Stage 9 (final validation), on the latest draft outputs rather
  than the originals;
- whenever the scientist asks.

Don't rerun it after every draft run of the cleanup script; the diff shows
what each change did.
