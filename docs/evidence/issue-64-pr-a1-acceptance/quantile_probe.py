"""Does numpy's default quantile give the band what step 4 relies on?

    python docs/evidence/issue-64-pr-a1-acceptance/quantile_probe.py
    (any cwd; needs only numpy)

Over 20,000 random count tables (2 to 39 members, 1 to 5 outcomes), with the
default ``linear`` method:

1. the 0 and 1 quantiles are exactly the per-outcome minimum and maximum;
2. a central band never has ``lower > upper`` and never leaves the min/max band.

It then prints the two facts the coverage metric's design rests on: seven
sevenths do not sum to 1.0 under ``numpy.sum`` (they do under ``math.fsum``
and under Python 3.12's built-in ``sum``, which is compensated), and identical
members give back their own values at any ``alpha``.
"""

import math

import numpy as np

rng = np.random.default_rng(64)
not_min = not_max = disordered = 0
for _ in range(20000):
    n_members = int(rng.integers(2, 40))
    n_outcomes = int(rng.integers(1, 6))
    counts = rng.integers(0, 50, size=(n_members, n_outcomes)) + (
        rng.random((n_members, n_outcomes)) < 0.3
    )
    totals = counts.sum(axis=1, keepdims=True)
    totals[totals == 0] = 1
    table = counts / totals
    lower, upper = np.quantile(table, [0.0, 1.0], axis=0, method="linear")
    not_min += not np.array_equal(lower, table.min(axis=0))
    not_max += not np.array_equal(upper, table.max(axis=0))
    alpha = float(rng.uniform(0, 0.4999))
    inner_lower, inner_upper = np.quantile(table, [alpha, 1 - alpha], axis=0, method="linear")
    disordered += bool(
        np.any(inner_lower > inner_upper)
        or np.any(inner_lower < lower)
        or np.any(inner_upper > upper)
    )
print("numpy", np.__version__)
print(
    "alpha=0 lower != min:",
    not_min,
    "upper != max:",
    not_max,
    "order or nesting violations:",
    disordered,
)

sevenths = np.array([1, 1, 1, 1, 1, 1, 1]) / 7
print("numpy.sum of seven sevenths:", repr(float(sevenths.sum())))
print("math.fsum of seven sevenths:", repr(math.fsum(sevenths)))
print("built-in sum of seven sevenths:", repr(sum(sevenths.tolist())))
pair = np.vstack([sevenths, sevenths])
print(
    "identical members, alpha 0.1, give their own values:",
    np.array_equal(np.quantile(pair, [0.1, 0.9], axis=0), pair),
)
print("65 / 100 == 0.65:", 65 / 100 == 0.65)
