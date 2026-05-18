# Notebooks

Notebooks live here for **exploration only** — they are never importable
source. Anything reusable must be promoted to `src/superconducted/...`
before merging.

## Naming convention

```
YYYY-MM-DD-<owner>-<topic>.ipynb
```

Examples:

- `2026-05-12-burak-anfis-warmup.ipynb`
- `2026-05-15-bengisu-cptp-projection-spike.ipynb`
- `2026-05-18-baha-calibration-drift-eda.ipynb`

## Pre-commit

Clear all outputs and execution counts before committing. Install
[`nbstripout`](https://github.com/kynan/nbstripout) once globally:

```bash
pip install nbstripout
nbstripout --install
```

Large outputs (figures, tables) bloat the repo and confuse `git diff`.

## Promoting code

If a function or class in a notebook is reused or could be reused, move
it into the appropriate module under `src/superconducted/...` (with type
hints, docstring, and a test) before merging the notebook.
