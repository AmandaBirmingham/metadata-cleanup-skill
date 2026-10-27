# Working on this skill

Run the tests with `./run_tests.sh` from this folder. Plain `pytest` fails:
the scripts' dependencies are not in any project environment, and the
script builds a temporary one from the scripts' own dependency blocks.

`BACKLOG.md` lists the work still to do, in priority order. Read it before
surveying the skill for work; add newly found gaps to it, and remove an item
(and its "see BACKLOG.md" markers) when it ships.
