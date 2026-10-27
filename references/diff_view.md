# The diff view

After each run of the draft cleanup script, show the scientist what changed,
cell by cell, between the previous draft output and the new one. This diff
is how a proposed change is shown before it is approved (SKILL.md, rule 4).

## How to make it

Run the bundled script; don't write your own:

    uv run scripts/diff_tables.py PREVIOUS.tsv NEW.tsv --key sample_name --out DIFF.html

`scripts/diff_tables.py` reads both files with every cell as
text, quote characters included; compares them with daff, matching rows by
the key column; and writes an HTML page with changed cells shaded and shown
as `old → new`, and unchanged rows and columns collapsed to `...`. It prints
a one-line summary: rows changed, rows added or removed, columns added or
removed. If nothing changed, it says so and writes no page.

Name the page to match the run: `<file>__diff__draft_<timestamp>.html`, one
per table.

## Which diff

- **By default:** the previous draft output against the new one, so the
  scientist sees what the latest change actually did.
- **Original files against the final outputs:** only when the scientist asks,
  and only after they have said the discussion is done and the final script
  has been run (SKILL.md, Phase 5).

## In the chat

Give the script's summary, say which decision it shows, and point out
anything unusual, such as cells changed that the latest decision shouldn't
have touched (the change list says which decision changed each cell).

## Known gap

The page shows the sample ID but not the spreadsheet row number or column
letter. When the scientist needs to find a cell in their own copy, give its
row and column from the change list.
