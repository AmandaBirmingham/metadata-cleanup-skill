# Phases 3–4 — Merging and validation (Stages 7–9)

## Stage 7 — Merging

Metadata can arrive at several levels (a subject table, a timepoint table, a
sample table), as several files at the same level (different sample subsets,
or different fields for the same samples), or in pieces over time (a first
submission, then corrections).

Merge before the required-field checks, because missing information (for
example, host details held in a subject table) only becomes visible once
everything is in one table.

Tables combine in one of two ways:

- **Stacking:** the tables have the same columns, for different samples
  (batches, plates, collection sites). Their rows are put one after another.
- **Merging:** the tables hold different information about related records
  (a subject table and a sample table). Records are matched on a link.

### Stacking

Before stacking, check and confirm with the scientist:

- the column sets are the same; columns present in only some tables are
  reported, never silently added as blanks;
- sample IDs are unique across all the tables, not just within each;
- whether to keep a column recording which file each row came from (a field
  from no input table, so it appears only in the merged file);
- the expected total row count (the sum of the tables' rows, adjusted for
  agreed exclusions).

Stack after each table has been through Phase 2 on its own. Checks that cross
tables (one subject's samples split across batches) are run on the stacked
result.

### Before each merge, decide explicitly with the scientist

**First: what information should be attached to which records, and how.**
Discuss this before anything else; never assume.

Often the answer is straightforward: the tables share a linking identifier
(subject_id, sample_name), and records are matched on it.

Sometimes it is not, because the information to attach isn't directly and
clearly linked to any one sample. For example, the scientist may want each
sample to carry information about the most recent antibiotic dose before it
was collected, from a table of doses with dates. Then the matching rule itself
must be worked out with the scientist, case by case:

- Some events can reasonably match the nearest sample in time, before or after
  (recent exercise or food eaten, depending on the study).
- Some must match only samples collected **on or after** the event: a sample
  taken before an antibiotic dose was not affected by it, so linking them would
  mislead the analysis. Equivalently, each sample gets the most recent event
  **before** its collection, never a later one.
- Consider a maximum time window, so that distant events aren't linked.
- Other rules may be needed. A "nearest in time" rule is not always the right
  one. Ask what the scientist wants each sample to represent, and turn that
  into an explicit rule. Show the diff of its results before approval.

Then, for every merge:

- **The linking column(s)** in each table, or the matching rule worked out
  above.
- **The cardinality:** one-to-one, one-to-many, or many-to-many.
- **The join type:** which rows to keep — only those in both tables, all from
  one side, or all from both. Don't assume. Keeping all rows from both sides is
  often the best way to expose problems.
- **Columns present in both tables** (other than the link): keep one, keep both
  with one renamed, or use it as part of the link.

### Checks before merging

- If a table's linking column should be unique (subject_id in a subject
  table), confirm that it is.
- Rows with an empty linking value: exclude them from the merge and report them.
- Linking values in one table with no match in the other: look for near matches
  (`UCSD.123` vs. `UCSD_123`) and ask.

### After each merge, report

- rows matched in both tables;
- rows only in the first table;
- rows only in the second table.

> Unmatched rows are information, not noise. They may reveal upstream problems,
> or they may be expected (a sample with no subject may be a control).

- Set fields that don't apply to `not applicable`. For example, after merging
  host-associated and free-living samples, host_body_site, host_taxid and
  similar fields are `not applicable` for the free-living samples.

Repeat until all tables are merged.

### Changes after merging

A correction made after merging to a field that came from an input table must
also be applied to that table's corrected copy. Fields that came from no input
table appear only in the merged file.

## Stage 8 — Required fields

Check first whether the required fields are already present and complete. Fill
any gaps with the scientist.

Every sample needs:

- host taxon ID;
- sample type.

Unless the scientist states the data will **never** be made public through ENA,
every sample also needs:

- sample taxon ID;
- an ENA checklist;
- the fields that checklist requires (usually collection date, location,
  coordinates and the three environment fields).

See `ena_requirements.md` for how to suggest values. Your own knowledge can
guide suggestions ("the broad environmental context is usually an ENVO biome"),
but every suggested ID or term must be checked against the bundled files.

## Stage 9 — Final validation

A last check on the merged result. Its purpose is to catch errors introduced
during handling, not to repeat Stage 3. Run the check script on the latest
draft outputs (the checks below are part of its generic part), then
spot-check a few records with the scientist.

- No duplicate sample IDs.
- Every required field filled for every sample.
- Row count as expected (for one-to-one merges, the sum of the input row
  counts, adjusted for agreed exclusions).
- No empty or NaN values introduced by merging.
- Per-table corrected copies are consistent with the merged file for every
  field they share.

### Comparison with the study-discussion estimates

Compare the final merged file with the estimates recorded in Phase 1:

- number of non-control samples, and number of control samples, each compared
  with its own estimate;
- for each key field (hypothesis and confounder fields): the number of samples
  for each value, or for numeric fields the actual range and spread;
- number of each type of control.

Report the comparison to the scientist in plain terms: "You estimated about 30
non-control samples; the final file has 31." Differences from estimates are
information, not mistakes; the estimates were guesses. Do not propose changes
because of them.

### Inadequate variation

Separately, check whether every key field still varies enough to be tested.
There is no fixed threshold; use judgment and explain your reasoning. Concerns
include:

- a field with only one value, or with almost all samples sharing one value
  (the scientist wanted to compare omnivores and vegetarians, but the final
  file has no vegetarian subjects);
- a numeric field with too narrow a range (every subject aged 30–32);
- **key fields that vary only together**, so their effects can't be told
  apart (every vegetarian is in cage 1 and every omnivore in cage 2, so diet
  and cage are confounded). Check every pair of key fields, including each
  hypothesis field against each confounder field.

If Phase 1 gave no key fields, use the choice recorded in the decision log
(see "Pre-existing studies" in `study_discussion.md`).

For each concern:

- Tell the scientist clearly, in terms of their question: "These samples
  can't be used to compare omnivores with vegetarians, because none of the
  subjects are vegetarian," or "Because all the vegetarian mice share one cage,
  a difference between diets couldn't be separated from a difference between
  cages."
- Make clear this is not necessarily a metadata error. It may be the true
  state of the samples, showing that the sample or subject selection doesn't
  support that comparison.
- Ask whether the values are correct. If they are, make no change; record the
  finding in the decision log and the final summary.
- If the scientist says the values are wrong, the fix is a decision like any
  other.
