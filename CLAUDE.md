# Working on this skill

Run the tests with `./run_tests.sh` from this folder. Plain `pytest` fails:
the scripts' dependencies are not in any project environment, and the
script builds a temporary one from the scripts' own dependency blocks.
