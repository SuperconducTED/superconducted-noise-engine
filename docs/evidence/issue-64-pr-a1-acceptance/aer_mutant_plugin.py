"""A pytest plugin that makes Aer behave like a future version that serialises more often.

Loaded with ``-p aer_mutant_plugin`` (or imported) and the environment variable AER_MUTANT:

  extra     one more ``noise_model.to_dict()`` per run than 0.17.2 makes
  per_shot  one more ``noise_model.to_dict()`` per shot of the run

It replaces the name ``cpp_execute_circuits`` inside ``qiskit_aer.backends.aer_simulator``
for the session only. The installed package is not modified.

The first version of ``per_shot`` read ``circuit.shots`` from the assembled
circuits, which is 1 there, so it was the same mutant as ``extra`` (count 2,
not 1025). ``mutate_step5_counts.py`` showed that. This version takes the
shot count from the run's config and refuses to run if it cannot find one.
"""

import os

import qiskit_aer.backends.aer_simulator as aer_simulator

_original = aer_simulator.cpp_execute_circuits
_mode = os.environ.get("AER_MUTANT", "")


def _mutated(controller, aer_circuits, noise_model, config):
    if noise_model:
        if _mode == "extra":
            repeats = 1
        elif _mode == "per_shot":
            repeats = int(config.shots)
            if repeats < 1:
                raise RuntimeError(
                    f"aer_mutant_plugin: no shot count on the config ({config.shots!r})"
                )
        else:
            repeats = 0
        for _ in range(repeats):
            noise_model.to_dict(serializable=True)
    return _original(controller, aer_circuits, noise_model, config)


if _mode:
    aer_simulator.cpp_execute_circuits = _mutated
