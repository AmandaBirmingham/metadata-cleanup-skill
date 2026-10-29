# Working on this skill

Run the tests with `./run_tests.sh` from this folder. Plain `pytest` fails:
the scripts' dependencies are not in any project environment, and the
script builds a temporary one from the scripts' own dependency blocks.

`BACKLOG.md` lists the work still to do, in priority order. Read it before
surveying the skill for work; add newly found gaps to it, and remove an item
(and its "see BACKLOG.md" markers) when it ships.

## Coded checks are a floor, not a replacement for reading

Coded checks never replace reading the values. Possible PII in odd places,
values that look as if they were meant as ENA missing-value terms, and
similar fuzzy questions are always also judged by reading. Only the cleanup
(the changes) must be deterministic code. The one exception: the coded PII
checks run first, so PII the code can find is never read; reading covers
only what remains. Regular expressions and edit-distance rules cannot match
a human-like reading of text, and the skill tends to drift toward making
everything deterministic.

When adding or shipping a coded check, keep the reading instruction it
overlaps with, and don't let rules such as "every finding comes from the
check files" exclude findings made by reading.

## No new files for nice-to-haves

Don't add output, temporary or working files to the skill's design (check
script outputs, cleanup template side files, and so on) for convenience. A
new file is acceptable only when it implements major required
functionality; the number of files a session produces is kept small on
purpose. Before putting a new file in any plan, check whether an existing
file or existing data (findings, review file, draft outputs, change list,
sample IDs) can carry it; if the feature isn't essential, propose dropping
it. Name any new file explicitly as a cost and justify it as required.

## Each fact in one place

In SKILL.md, `references/`, `BACKLOG.md` and the script docstrings, each
fact is stated in one home, and every other place where it is relevant
points to that home instead of repeating it. This covers rules, examples,
file formats, output names, parameter usage and planned-work markers: one
marker per backlog item, at the section that specifies it, which is the
section its "Spec:" names. Restated facts drift apart.

Before adding or editing text, check whether the fact already has a home,
and point to it if so. When a fix would restate something, move it to one
home and replace the other copies with references. Prefer describing a
category to listing items that will need editing as the list grows.

## Numbering questions to the user

Label each question to the user "Q" plus its number (Q1, Q2, ...), never as
a markdown numbered list: the renderer renumbers list items, so the numbers
the user sees can differ from the ones written, and answers keyed to them
go astray.
