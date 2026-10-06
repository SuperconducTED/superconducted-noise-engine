"""Self-test of the shared rules in ``ddload.py`` on synthetic data (no cache needed).

Checks that the variogram reads as its docstring says (flat for noise around a fixed level,
linear in lag for a random walk, the noise part equal to a known constant variance) and that
the value-only event rule keeps exactly the files where the value changes. Exits non-zero on
the first failure. Run: ``python analysis/data_layer/selftest_ddload.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload


class FakeDD:
    """The three members of ``ddload.DD`` that ``ddload.series`` uses."""

    def __init__(self, values: np.ndarray, dates: np.ndarray, file_ms: np.ndarray) -> None:
        self._v, self._d, self.file_ms = values, dates, file_ms

    def v(self, field: str) -> np.ndarray:
        return self._v

    def d(self, field: str) -> np.ndarray:
        return self._d


def check(name: str, ok: bool, detail: Any) -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {name}: {detail}")
    if not ok:
        raise SystemExit(1)


def main() -> int:
    rng = np.random.default_rng(20261006)
    hours = np.arange(400, dtype=np.float64)
    t_ms = hours * ddload.MS_PER_HOUR
    edges = (0.0, 1.5, 10.5, 50.5, 200.5)
    # 1. White noise around a fixed level, sd 0.1 in log10: flat at 0.01.
    noise = [
        ddload.Series(
            entity=k, t_ms=t_ms, file_idx=np.arange(400), y=10 ** rng.normal(-3, 0.1, 400)
        )
        for k in range(40)
    ]
    vg = ddload.variogram(noise, edges_h=edges)
    sv = [b["semivariance"] for b in vg["bins"]]
    check("noise is flat at the variance", all(abs(s - 0.01) < 0.0015 for s in sv), sv)
    # 2. Random walk with step sd 0.02 per hour: semivariance = 0.0002 * lag / 1 (per hour).
    walks = [
        ddload.Series(
            entity=k,
            t_ms=t_ms,
            file_idx=np.arange(400),
            y=10 ** (-3 + np.cumsum(rng.normal(0, 0.02, 400))),
        )
        for k in range(200)
    ]
    vg = ddload.variogram(walks, edges_h=edges)
    ratios = [b["semivariance"] / (0.0002 * b["mean_lag_h"]) for b in vg["bins"]]
    check("random walk grows linearly with lag", all(abs(r - 1) < 0.15 for r in ratios), ratios)
    # 3. Known noise variance is reported as the noise part.
    var = [np.full(400, 0.004) for _ in noise]
    vg = ddload.variogram(noise, edges_h=edges, noise_var=var)
    parts = [b["noise_part"] for b in vg["bins"]]
    check("noise part equals the known variance", all(abs(p - 0.004) < 1e-12 for p in parts), parts)
    # 4. Value-only rule: an event wherever the value changes, timed at the file's stamp.
    values = np.array([[1.0], [1.0], [2.0], [np.nan], [2.0], [1.0]])
    dates = np.full_like(values, 5.0)
    file_ms = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
    fake: Any = FakeDD(values, dates, file_ms)
    ser = ddload.series(fake, "x", rule=ddload.ASSEMBLY)
    got = (ser[0].file_idx.tolist(), ser[0].t_ms.tolist(), ser[0].y.tolist())
    check("value-only events", got == ([0, 2, 5], [10.0, 30.0, 60.0], [1.0, 2.0, 1.0]), got)
    # 5. Measured rule needs value AND date to move; a placeholder is masked first.
    values = np.array([[0.1], [0.2], [0.2], [1.0], [0.3]])
    dates = np.array([[1.0], [1.0], [2.0], [3.0], [4.0]])
    fake = FakeDD(values, dates, file_ms[:5])
    ser = ddload.series(fake, "x", rule=ddload.MEASURED, mask=ddload.placeholder_error)
    got = (ser[0].file_idx.tolist(), ser[0].y.tolist())
    check("measured events with the placeholder masked", got == ([0, 4], [0.1, 0.3]), got)
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
