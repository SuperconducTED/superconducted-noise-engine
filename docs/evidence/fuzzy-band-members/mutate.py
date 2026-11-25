"""Mutation check of `scripts/fuzzy_band_members.py` (#161, the member (gamma, lambda) band).

    python docs/evidence/fuzzy-band-members/mutate.py --root . --python <interpreter> --out <file>

Each mutant replaces one piece of text in the script, which must occur exactly once, runs the
script's tests, and restores the file from the bytes read before the edit.

A mutant is `killed` only when pytest exits 1, which is "tests were collected and some failed".
Exit 0 is `survived`. Any other exit code (2 interrupted, which includes a collection error when
`-x` is not passed, 3 internal error, 4 usage error, 5 no tests collected) is `harness error`:
the tests did not judge the mutant. pytest runs without `-x`, so a module that does not import
cannot pass as killed (the #142 lesson of 2026-11-23). The control `S00` breaks the import on
purpose and is predicted `harness error`, so the run shows that path classifies correctly.

For every mutant the output lists the tests that failed, so a reader can check that each mutant
was caught for the reason its name gives (lesson L-075). The script exits 1 when any outcome
differs from its prediction. Reads and rewrites one source file, restores it, and writes `--out`.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
from pathlib import Path

TARGET = "scripts/fuzzy_band_members.py"
TESTS = ("tests/test_fuzzy_band_members.py",)

# (name, text to replace, replacement, prediction, why)
MUTANTS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "S00 control: the module does not import",
        "import numpy as np\n",
        "import numpy as np\nimport no_such_module_161\n",
        "harness error (pytest exit 2)",
        "collection fails; without -x pytest exits 2, which must not count as killed",
    ),
    (
        "M01 the upper edge at 1 - 2 alpha",
        "[alpha, 1.0 - alpha], axis=0",
        "[alpha, 1.0 - 2.0 * alpha], axis=0",
        "killed",
        "test_band_edges_are_numpys_quantiles_per_component",
    ),
    (
        "M02 members read as (lambda, gamma)",
        "member.crisp_params[:2], dtype",
        "member.crisp_params[1::-1], dtype",
        "killed",
        "member_targets against the stacked crisp_params; the vanishing-jitter point",
    ),
    (
        "M03 the band's columns swapped",
        "table = np.array(members, dtype=np.float64, copy=True)",
        "table = np.array(members, dtype=np.float64, copy=True)[:, ::-1]",
        "killed",
        "band edges per component; the clip counts per component",
    ),
    (
        "M04 the quantile method ignored",
        "axis=0, method=method)",
        'axis=0, method="linear")',
        "killed",
        "the 'higher' case of the edge test; the off-the-edge refusal",
    ),
    (
        "M05 members at 1 not counted",
        "at_upper=(table == 1.0).sum(axis=0)",
        "at_upper=np.zeros(table.shape[1], dtype=np.int64)",
        "killed",
        "test_band_counts_members_at_either_clip_bound",
    ),
    (
        "M06 members at 0 not counted",
        "at_lower=(table == 0.0).sum(axis=0)",
        "at_lower=(table < 0.0).sum(axis=0)",
        "killed",
        "test_band_counts_members_at_either_clip_bound",
    ),
    (
        "M07 the engine reads SI seconds",
        '"feature_extractor": ArchiveUnitFeatureExtractor(),',
        '"feature_extractor": ArchiveUnitFeatureExtractor()._inner,',
        "killed",
        "parity with the trainer (fitted in archive units); the vanishing-jitter point",
    ),
    (
        "M08 no perturbation",
        "        perturbation=perturbation,\n",
        "        perturbation=None,\n",
        "killed",
        "member_targets requires 8 distinct members",
    ),
    (
        "M09 the caller's seed sequence used as is",
        "rng=np.random.default_rng(own_seed),",
        "rng=np.random.default_rng(seed),",
        "killed",
        "test_one_seed_gives_one_ensemble_even_when_reused",
    ),
    (
        "M10 a rule base with three outputs accepted",
        "    if rule_base.output_dim != len(TARGET_NAMES):\n",
        "    if False:\n",
        "killed",
        "test_a_rule_base_without_two_outputs_is_refused",
    ),
    (
        "M11 the parser's validation skipped",
        "    parsed = parse_snapshot(document, source=source)\n",
        '    parsed = type("P", (), {"backend_name": str(document["backend"])})\n',
        "killed",
        "test_snapshot_from_document_applies_the_parsers_validation",
    ),
    (
        "M12 members outside [0, 1] accepted",
        "    if table.min() < 0.0 or table.max() > 1.0:\n",
        "    if False:\n",
        "killed",
        "the off-the-edge case: with method 'higher' the edges stay in [0, 1]",
    ),
    (
        "M13 the band's alpha check dropped",
        "    _check_alpha(alpha)\n    if not method:\n",
        "    if not method:\n",
        "killed",
        "alpha -0.1 reaches numpy, whose error is rewrapped without the word alpha",
    ),
    (
        "M14 the finite check dropped",
        "    if not np.all(np.isfinite(table)):\n",
        "    if False:\n",
        "survived",
        "equivalent: numpy.quantile returns NaN for a column holding NaN, which TargetBand "
        "refuses as not finite; an infinity fails the [0, 1] check first",
    ),
)

FAILED = re.compile(r"^FAILED (\S+)", re.MULTILINE)


def classify(code: int) -> str:
    if code == 0:
        return "survived"
    if code == 1:
        return "killed"
    return f"harness error (pytest exit {code})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    target = args.root / TARGET
    original = target.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    env = {**os.environ, "PYTHONPATH": "src", "COLUMNS": "200"}
    env.pop("PYTEST_ADDOPTS", None)
    command = [args.python, "-m", "pytest", *TESTS, "-q", "-rf", "-p", "no:cacheprovider"]
    command += ["-o", "addopts="]

    baseline = subprocess.run(command, cwd=args.root, env=env, capture_output=True, text=True)
    if baseline.returncode != 0:
        print(f"the unmutated tests do not pass (pytest exit {baseline.returncode})")
        return 1
    lines = [f"baseline: {baseline.stdout.strip().splitlines()[-1].strip('= ')}"]
    lines.append("mutant\tprediction\toutcome\tmatches\tfailing tests")
    outcomes: list[str] = []
    bad = 0
    for name, old, new, prediction, _why in MUTANTS:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"{name}: the text occurs {count} times in {TARGET}")
        try:
            target.write_bytes(text.replace(old, new).encode("utf-8"))
            done = subprocess.run(command, cwd=args.root, env=env, capture_output=True, text=True)
        finally:
            target.write_bytes(original)
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise SystemExit(f"{name}: {TARGET} was not restored")
        outcome = classify(done.returncode)
        outcomes.append(outcome)
        matches = outcome == prediction
        bad += 0 if matches else 1
        failing = sorted({test.split("::", 1)[-1] for test in FAILED.findall(done.stdout)})
        lines.append(f"{name}\t{prediction}\t{outcome}\t{matches}\t{', '.join(failing) or '-'}")
        print(lines[-1], flush=True)

    mutants = outcomes[1:]
    killed = mutants.count("killed")
    survived = mutants.count("survived")
    errors = len(mutants) - killed - survived
    summary = (
        f"{len(mutants)} mutants and 1 control: {killed} killed, {survived} survived, "
        f"{errors} harness errors among the mutants; control {outcomes[0]}; "
        f"{bad} against the prediction"
    )
    lines.append(summary)
    print(summary)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return 1 if bad or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
