# Feature deep dive of the `ibm_fez` calibration archive (2026-10-06)

Every field of all 1,760 `ibm_fez` snapshot files at `calibration-data`
`7b84b506ef77beb6e6c1b25a7357c574cfaf5117`, analysed from the data up. Every figure is
provisional (measured on the lead's laptop; not registered in `docs/numerical-claims.md`).
Nothing here is a decision: A1 to A9 and Dr. Akba's answers remain open.

Start with `00-overview.md`.

| File or folder | What it is |
| --- | --- |
| `00-overview.md` | Synthesis: the feature map, the dependency map, the root questions for the paper (first: the non-persistent component), data-quality rules, the ranked unknowns, and each document's verification status |
| `01-data-layer.md` | The data dictionary: every field, its date semantics and event rule, identities, device-wide length changes, file-level structure, the shared variogram, and scope ownership |
| `02-coherence.md` | `T1`, `T2` and the derived rates |
| `03-readout-measurement.md` | Readout errors, assignment probabilities, lengths, thresholds, `init_error`, `measure_2`, reset durations |
| `04-single-qubit-gates.md` | `sx` and its aliases, `xslow`, `rz` |
| `05-two-qubit-gates-couplings.md` | `cz`, `rzz`, `jq`, `zz` |
| `06-device-time-topology.md` | Calibration schedule, documents and states, change points, faults, layout, layer fidelity |
| `07-cross-feature-dependency.md` | Relationships between families: levels, co-movement, lead and lag, coincidence, factors |
| `analysis/` | `extract_cache.py` (builds the cache), `ddload.py` (loader, event rules, variogram), one folder per scope, and `verify/<scope>/` (the verifiers' independent scripts) |
| `results/` | One JSON per script, each starting with its provenance header; `results/verify/<scope>/` for the verifiers |

Each scope document 02 to 07 ends with a "Verification (2026-10-06)" section written by an
independent verifier, and carries inline **[Verification 2026-10-06: ...]** markers next to the
claims it weakened or refuted. How the folder was produced is recorded in
`docs/implementations/2026-10-06-feature-deep-dive.md`.

To rebuild the cache and re-run any script, follow `01-data-layer.md` §1 and each document's
"Reproduce" section.
