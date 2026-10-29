# Phase 1 — Study discussion

Goal: understand the study well enough to know what the metadata must contain,
before judging what it does contain. Record every answer in the decision log,
in the study-information layout given under "Records" in SKILL.md.

## 1. Hypotheses

Ask what the study is trying to find out.

- Example: "Subjects with acne treated with drug X have skin microbial
  communities indistinguishable from healthy controls two weeks later."
- Example: "Feeding time has a greater effect than diet on mouse gut
  microbiomes."

Never offer "exploratory" as an answer. If the scientist says the study is
exploratory, ask what they hope to learn: which groups, gradients or
environments they expect to compare. Record what they say, and record
"exploratory" only if nothing more specific comes out. Such studies still
need the next steps, to decide what information matters most.

## 1a. Expected number of samples

Ask roughly how many samples the scientist expects, as two separate numbers:

- non-control samples;
- control samples.

Rough guesses are fine; say so. Record both estimates in the decision log. The
breakdown of controls by type comes in section 5.

## 2. Fields that test the hypotheses

Work out which fields the analysis will need.

- Acne example: subject_id, timepoint, treatment, disease_state.
- Mouse example: animal_id, feeding_time, diet.

## 3. Fields that rule out confounders

Work out what else could explain the result, and which fields would capture it.

- Acne example: swab_type, takes_rx_meds, race/ethnicity, geolocation.
- Mouse example: cage_id, technician, mouse_vendor, mouse_strain.

## 4. Details of each field

For each field, agree on units, allowed values (vocabulary), and the precision
needed. For example, is age to the nearest year enough, or does it need to be
more exact?

## 4a. Expected variation in key fields

For every field the scientist agreed is needed to test a hypothesis or rule
out a confounder, ask what variation they expect, and record the estimates in
the decision log:

- **Fields with categories** (diet, treatment, sex): roughly how many samples
  they expect for each value.
- **Numeric fields** (age, BMI, depth): the expected range and spread, for
  example "ages roughly 20–60, fairly evenly spread". Also ask what values
  would be impossible or implausible; those limits become range checks in
  the check script (`check_script.md`) before its first run.

A field can only be tested if the samples actually vary in it. If a study of
diet expects 30 samples and all 30 are diet A, the effect of diet cannot be
tested. Even 28 of diet A and 2 of diet B is probably too few to say much.
Likewise, if every subject is aged 30–32, the samples can't say much about
age. There is no fixed threshold; use judgment and explain your reasoning.
When an estimate shows a field with little or no variation, point this out
now, while the scientist can still change which samples to collect, and
explain it in terms of their question: "With all your subjects on diet A, these
samples won't be able to show whether diet makes a difference."

## 4b. Key fields that might vary together

Ask whether any key fields are likely to vary only together, so that their
effects couldn't be told apart. Look especially at each hypothesis field
against each confounder field. For example: will all the vegetarian mice share
one cage and all the omnivores another? Will all treated subjects be sampled
by one technician, or in one batch? Will the two groups come from different
sites or vendors?

If so, explain the consequence in terms of their question ("a difference
between diets couldn't be separated from a difference between cages") while
the design can still change, and record the answer in the decision log. This is
checked again at final validation.

## 5. Controls

Ask what controls are planned, and roughly how many of each type. If the answer
is none, help the scientist consider positive and negative controls suited to
the hypothesis, the lab methods (for example, extraction blanks), and the
sequencing or measurement technology. Record the planned types and numbers in
the decision log.

## 6. Host and sample type

Explain that every sample, controls included, needs a host and a sample type.
Ask the scientist to describe the hosts and sample types in the study. They
may say one or both are the same for all samples ("this study is all human
feces").

- Match what they describe to a host taxon ID (search the bundled taxonomy) and
  a sample type (`assets/sample_types.tsv`; see "Lookups" in SKILL.md), and
  ask them to confirm or correct each match.
- For the host taxon ID of free-living samples and of controls, see
  "Taxon IDs" in `ena_requirements.md`.

## 7. ENA requirements

Explain that to submit to ENA, every sample needs the fields in
`ena_requirements.md`: the sample
taxon ID, an ENA checklist, and usually collection date, location, coordinates
and the three environment fields. Say that you will help them choose the right
values, and that many of these may be the same for all or most samples. (These
fields are optional only in the cases listed under "When ENA fields are out of
scope" in `ena_requirements.md`; record the scientist's statement in the
decision log.)

## 8. Carry forward

When the metadata files arrive, check that each field discussed here exists,
with the units, vocabulary and precision agreed, and propose adding host and
sample type information wherever it is missing. The sample-count and
variation estimates from sections 1a, 4a, 4b and 5 are used again at final
validation.

## Pre-existing studies

Sometimes the samples were collected long ago, the design is settled, and the
person you are helping may not know some of the decisions. The discussion
above cannot change anything, but its answers are still what the metadata is
checked against. Then:

- Ask about every line of the study-information layout under "Records" in
  SKILL.md, and say that anything they know about any of them is useful
  and that the rest will be recorded as `unknown`.
- Where sections 4a and 4b say to point out a problem while the design can
  still change, report it instead as a limit on what these samples can show.
- Record each answer in the decision log. Mark everything else `unknown`
  rather than guessing it; don't press for estimates the person says they
  can't give.
- If no key fields (hypothesis and confounder fields) can be named, ask which
  the scientist wants, and record the answer: they name key fields as they
  come up; the key-field checks run on every categorical and numeric column;
  or the checks are skipped. When the checks run on every column, many
  overlaps (two columns that always agree, or one field that determines
  another) will turn up; handle them as "Inadequate variation" in
  `merge_and_validation.md` describes.
- At Stage 9, report "no estimate" for counts and variation that were never
  estimated, instead of comparing against anything.
