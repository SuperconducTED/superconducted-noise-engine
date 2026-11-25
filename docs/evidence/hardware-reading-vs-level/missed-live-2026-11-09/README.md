# Amendment 34's mutation check, 2026-11-09

**Criterion 29 of the amendment 34 plan** (`docs/implementations/2026-11-05-hardware-test-submission.md`, "Amendment 34
plan"): every line the change added is mutated, and a test must fail. No device measurement and no NC row. Laptop, on
the exact pins, provisional.

Run with `../mutation-2026-11-08/mutate_stage_2.py` against the plan commit:

    python mutate_stage_2.py <repo root> a1e1b22a <this folder> --group score
    python mutate_stage_2.py <repo root> a1e1b22a <this folder> --group score --only 2

`--group score` sends every mutant to the score group's tests, which now include the two amendment 34 tests: the import
line sits at module level, and the default mapping would have given it the report's tests, which never build a job.

| | Mutants |
| --- | --- |
| Generated from `git diff a1e1b22a..48718a91` over the three scripts | 11 |
| Caught | 11: one by an assertion at `48718a91`, and #2 by an assertion after `8341e32d` |
| Survived, timed out | 0 |

Four added lines get no mutant: the new function's `def` line, a closing bracket, and the `try:` and `except` lines.

The other nine are caught by a crash, and each crash is the code failing the way the mutant makes it fail:

- the import removed: `NameError`;
- a line of `write_json_lf`'s call removed: a missing argument;
- a path join turned into a multiplication: `TypeError`;
- the `raise`, the record call or the assignment of `rows` removed: `rows` unbound;
- the no-re-run guard negated: every ordinary build is refused.

The ninth, #2 (the write of `missed.json` removed), first failed on reading a missing file. `8341e32d` makes the test
assert the record exists before reading it, and the re-run (`mutation.out.rerun.txt`) catches #2 by that assertion.

Files: `mutation.out.txt` and `mutation.tsv` (the run at `48718a91`), `mutation.out.rerun.txt` and `mutation.rerun.tsv`
(#2 at `8341e32d`). The home folder in failure messages is written `<home>`.
