# 2026-06-14: suppress-ibm-fractional-deprecation-warning

## Problem / Motivation

The test suite passed cleanly (149 passed) but emitted two identical
`DeprecationWarning`s in the pytest *warnings summary*:

> `IBMFractionalTranslationPlugin is deprecated as of qiskit-ibm-runtime 0.42.0
> ... Use IBMDynamicFractionalTranslationPlugin instead.`

The warning is **not raised by this project's code**. It originates in the
third-party `qiskit-ibm-runtime` package: when `transpile()` is called with a
backend, Qiskit's transpiler enumerates *all* installed translation plugins
through `stevedore` entry points, and merely loading the
`IBMFractionalTranslationPlugin` class emits the deprecation. This project only
ever runs against `AerSimulator` and never invokes that plugin, so the noise is
non-actionable in our own code. Left unfiltered it clutters every CI/local run
and risks masking warnings we *do* care about. The remediation is a single
targeted suppression so the warnings summary stays meaningful.

## What changed

| File | One-sentence description |
| --- | --- |
| `pyproject.toml` | Adds a `filterwarnings` key to `[tool.pytest.ini_options]` that ignores only the `IBMFractionalTranslationPlugin` `DeprecationWarning`. |
| `docs/implementations/2026-06-14-suppress-ibm-fractional-deprecation-warning.md` | This record. |
| `memory/MEMORY.md` | New project memory index with a pointer to this suppression so a future session does not "rediscover" or remove the filter. |

## Implementation approach

A single pytest warning filter is added to the existing
`[tool.pytest.ini_options]` block:

```toml
filterwarnings = [
    "ignore:.*IBMFractionalTranslationPlugin is deprecated.*:DeprecationWarning",
]
```

Filter-string mechanics (so a future reader can audit it):

- The pytest/Python filter format is `action:message:category:module:lineno`.
  Here `action = ignore`, `message` is the regex above, `category =
  DeprecationWarning`; `module` and `lineno` are intentionally left empty.
- pytest compiles `message` case-insensitively and matches it with `re.match`,
  which anchors at the start of the warning text. The leading `.*` lets the
  pattern match the class name even though the real message begins with a
  version-specific preamble ("Since backends now support running jobs ...").
- The pattern is keyed on the **stable identifier**
  `IBMFractionalTranslationPlugin is deprecated` rather than the volatile
  preamble, so wording tweaks across `qiskit-ibm-runtime` releases won't let the
  warning slip past the filter. Scoping to `DeprecationWarning` guarantees it
  cannot accidentally hide an unrelated warning category.
- The warning text contains no `:` characters, so it cannot collide with the
  filter's field separator.

No production code paths were touched; the trigger site is
`scripts/first_ensemble_run.py` at the `transpile(prepared_circuit,
backend=simulator)` call.

## Mathematical / Statistical details

N/A — purely structural (a config-only warning filter).

## Design decisions

- **Suppress rather than upgrade or migrate.** The deprecated plugin is a
  transitive third-party artifact this project never uses. The dependency range
  is pinned to `qiskit-ibm-runtime>=0.46,<0.50`; no in-range release is
  guaranteed to remove the plugin (deprecated in 0.42.0, removal promised "no
  sooner than 3 months"), and bumping the dependency purely to silence a benign
  deprecation would add churn and risk for zero functional gain.
- **Global filter over a per-test marker.** Any future test that calls
  `transpile()` with an Aer/IBM-aware backend would re-surface the same warning.
  A suite-wide ignore covers them without scattering `@pytest.mark.filterwarnings`
  decorators. The filter is kept specific to the one plugin class so it never
  degenerates into a blanket `ignore::DeprecationWarning`.
- **Plain `ignore`, not warnings-as-errors (`error` + allow-list).** A stricter
  policy that fails the build on our own future deprecations was considered and
  deliberately deferred to keep this change minimal and low-risk; it can be
  revisited as a separate CI-strictness decision.

## Verification

From the project root with the virtualenv active:

- Targeted (the slow test that triggers it):
  `python -m pytest "tests/test_first_ensemble_run.py::test_run_ensemble_real_aer_one_qubit"`
  — expect `1 passed` and no `IBMFractionalTranslationPlugin` entry in the
  warnings summary.
- Full suite (regression):
  `python -m pytest` — expect `149 passed` with the IBM deprecation gone from
  the warnings summary (both original warnings were this same one).
- Lint (config-only edit):
  `ruff check .` — expect no new findings.

If the warning persists, the message/category did not match; fall back to a
module-scoped form (`"ignore::DeprecationWarning:qiskit_ibm_runtime"`) and
re-run the targeted test.

## Related docs

- Trigger site: `scripts/first_ensemble_run.py` (`transpile(..., backend=simulator)`).
- Config: `pyproject.toml`, `[tool.pytest.ini_options]`.
- Upstream: `qiskit-ibm-runtime` 0.42.0 deprecation of `IBMFractionalTranslationPlugin`.
