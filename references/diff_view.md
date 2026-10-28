# The diff view

After each run of the draft cleanup script, show the scientist what changed,
cell by cell, between the previous draft output and the new one. This diff
is how a proposed change is shown before it is approved (SKILL.md, rule 4).

## How to make it

The draft cleanup script writes the diff itself when run with
`--diff-script` (see the top of the template), one page per table. For any
other diff, run the bundled `<skill>/scripts/diff_tables.py`; don't write
your own. How to call it, how it reads the files and what its summary says
are at the top of that file.

## Which diff

- **By default:** the previous draft output against the new one, so the
  scientist sees what the latest change actually did. A stacked table's first
  draft has no previous draft; show its stacking report instead (Structure,
  step 8, in `cleanup_script.md`).
- **Original files against the final outputs:** only when the scientist asks,
  and only after they have said the discussion is done and the final script
  has been run (SKILL.md, Phase 5).

## In the chat

Give the script's summary, say which decision it shows, and point out
anything unusual, such as cells changed that the latest decision shouldn't
have touched (the change list says which decision changed each cell).

For a decision that removes PII, give only the script's printed summary:
don't open the change list or the diff page, since both show the removed
value. The scientist checks the diff page themselves.

## Known gap

The page shows the sample ID but not the spreadsheet row number or column
letter. When the scientist needs to find a cell in their own copy, give its
row and column from the change list. *(Planned fix; see BACKLOG.md.)*
