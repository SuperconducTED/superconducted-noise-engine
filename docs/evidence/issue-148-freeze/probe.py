"""Probe issue #148: which stored fields of the training result types can change after the check?

    PYTHONPATH=<a tree's src> python docs/evidence/issue-148-freeze/probe.py

Run it against two trees and compare: ``main`` before the fix (``probe.main.out.txt``) and this
branch (``probe.head.out.txt``). It prints what it observes and asserts nothing, so it runs to the
end on either tree. No side effects.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.training import ParameterCount, TrainingDiagnostics, TrainingResult


def diagnostics(standardization: Any) -> TrainingDiagnostics:
    return TrainingDiagnostics(0.0, 0, 0, 1.0, 0, 1, False, standardization)


def result(**overrides: Any) -> TrainingResult:
    fields: dict[str, Any] = {
        "rule_base": TSKRuleBase.from_grid([[GaussianMF(0.0, 1.0)]], output_dim=1),
        "train_rmse": np.zeros(1),
        "validation_rmse": None,
        "loss_history": (),
        "diagnostics": diagnostics((np.zeros(1), np.ones(1))),
        "parameter_count": ParameterCount(2, 2, 4),
    }
    fields.update(overrides)
    return TrainingResult(**fields)


def write(target: Any, label: str) -> None:
    try:
        target[...] = np.nan
        print(f"3 write into the stored {label}: accepted, now {target}")
    except ValueError as exc:
        print(f"3 write into the stored {label}: refused ({exc})")


def main() -> None:
    # 1. Burak's finding 1, with issue #148's own inputs.
    a = np.array([0.0, 1.0])
    d = diagnostics((a,))
    a[0] = np.nan
    print(f"1 standardization after the caller writes nan: {d.standardization[0]}")
    print(f"1 the stored array is the caller's object: {d.standardization[0] is a}")

    # 2. Burak's finding 2.
    t, v = np.array([0.1]), np.array([0.2])
    r = result(train_rmse=t, validation_rmse=v)
    t[0] = np.inf
    v[0] = np.nan
    print(f"2 train_rmse after the caller writes inf: {r.train_rmse}")
    print(f"2 validation_rmse after the caller writes nan: {r.validation_rmse}")

    # 3. Writes through the stored objects themselves.
    r = result()
    write(r.train_rmse, "train_rmse")
    write(r.diagnostics.standardization[0], "standardization array")

    # 4. Containers.
    arrays = [np.zeros(1), np.ones(1)]
    d = diagnostics(arrays)
    arrays.append(np.array([np.nan]))
    kind, size = type(d.standardization).__name__, len(d.standardization)
    print(f"4 standardization given as a list, then appended to: a {kind} of length {size}")
    losses = [0.5, 0.4]
    r = result(loss_history=losses)
    losses.append(float("nan"))
    kind = type(r.loss_history).__name__
    print(f"4 loss_history given as a list, then appended to: a {kind}, {r.loss_history}")

    # 5. Types, and the two cases that must keep constructing.
    narrow = result(train_rmse=np.zeros(1, dtype=np.float32)).train_rmse
    bare = result(train_rmse=0.5).train_rmse
    print(f"5 a float32 train_rmse is stored as {narrow.dtype}")
    print(f"5 a bare number for train_rmse is stored as a {type(bare).__name__}")
    print(f"5 empty standardization: {diagnostics(()).standardization}")
    print(f"5 absent validation_rmse: {result().validation_rmse}")


if __name__ == "__main__":
    main()
