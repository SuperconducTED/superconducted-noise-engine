"""Print the values the identity pin of step 1 holds, and check a seeding fact step 2 relies on.

    python docs/evidence/issue-64-pr-a1-acceptance/capture_identity_pin.py
    (cwd: the repository root, PYTHONPATH=".;src" on Windows or ".:src" elsewhere)

Prints, for the gate-bearing ``ibm_fez`` fixture and the issue #58 test grid:
the first viable rule-base seed, each member's ``crisp_params`` as hex floats
and as decimals, and the extracted feature vector ``x`` (SI seconds for the two
coherence means, dimensionless for the readout error). It was first run on
``main`` at ``cd277a64``, before the ensemble's wiring changed; with no
perturbation the output is the same after it.

The last line shows that spawning child seed sequences from a generator's seed
sequence draws nothing from the generator's stream.
"""

import numpy as np
from tests.conftest import _benchmark_ensemble_for_seed, benchmark_snapshot

from superconducted.integration.aer_factory import first_viable_seed

snapshot = benchmark_snapshot.__wrapped__()
_, seed = first_viable_seed(lambda s: list(_benchmark_ensemble_for_seed(snapshot, s)))
print("viable seed", seed)
ensemble = _benchmark_ensemble_for_seed(snapshot, seed, 3)
for member in ensemble:
    params = member.crisp_params
    print([float(v).hex() for v in params], params.tolist(), params.dtype, params.shape)
print("x", ensemble._feature_extractor.extract(snapshot).tolist())

rng = np.random.default_rng(7)
before = rng.bit_generator.state["state"]["state"]
rng.bit_generator.seed_seq.spawn(3)
print(
    "stream untouched by spawn:",
    before == rng.bit_generator.state["state"]["state"],
    "children spawned:",
    rng.bit_generator.seed_seq.n_children_spawned,
)
