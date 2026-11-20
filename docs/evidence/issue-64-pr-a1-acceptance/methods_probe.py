"""Is the alpha = 0 band exactly min and max under every numpy quantile method?

    python docs/evidence/issue-64-pr-a1-acceptance/methods_probe.py
    (any cwd; needs only numpy)

For each of the thirteen methods ``numpy.quantile`` accepts, over 3,000 random
count tables (2 to 39 members, 1 to 5 outcomes), counts the tables where the 0
and 1 quantiles are not bit for bit the per-outcome minimum and maximum.
"""

import numpy as np

METHODS = [
    "inverted_cdf",
    "averaged_inverted_cdf",
    "closest_observation",
    "interpolated_inverted_cdf",
    "hazen",
    "weibull",
    "linear",
    "median_unbiased",
    "normal_unbiased",
    "lower",
    "higher",
    "midpoint",
    "nearest",
]

rng = np.random.default_rng(64)
tables = []
for _ in range(3000):
    n_members = int(rng.integers(2, 40))
    n_outcomes = int(rng.integers(1, 6))
    counts = rng.integers(0, 50, size=(n_members, n_outcomes))
    counts[:, 0] += 1
    tables.append(counts / counts.sum(axis=1, keepdims=True))

print("numpy", np.__version__)
for method in METHODS:
    bad = 0
    for table in tables:
        lower, upper = np.quantile(table, [0.0, 1.0], axis=0, method=method)
        bad += not (
            np.array_equal(lower, table.min(axis=0)) and np.array_equal(upper, table.max(axis=0))
        )
    print(
        f"{method:28s} tables where the edges are not exactly min and max: {bad} of {len(tables)}"
    )
