# Calibration fixtures

JSON exemplars of real `backend.properties().to_dict()` payloads, used by the
loader and feature-extractor tests under `tests/calibration/`.

## `ibm_fez_20260513T121322Z_q72_missing_t1t2.json`

**Backend**: `ibm_fez` (156 physical qubits).
**Captured**: 2026-05-13 12:13:22 UTC.

**Why it exists**: real IBM `properties()` responses occasionally omit per-qubit
T1 and T2 entries when the coherence-measurement step fails during the
calibration window. The qubit still appears in `properties.qubits` and its
readout calibration is intact; only the coherence Nduv entries are absent. This
exemplar captures exactly that pattern at **qubit index 72**, whose Nduv list
contains `readout_error`, `prob_meas0_prep1`, `prob_meas1_prep0`, and
`readout_length` — no `T1`, no `T2`. The remaining 155 qubits have all six
standard entries.

**Provenance**:
- Source ref: `origin/calibration-data:snapshots/2026-05/ibm_fez/20260513T121322000000Z.json`
- Full source SHA-256: `cbbbd2c3273e4e7eda006eaa104a16d8f81888776cbfc8453b637322671d1083`
- Full source size: 1 324 893 bytes.

**Minimization**: the on-disk fixture is a slimmed projection of the source.
The fields kept are exactly those the loader and feature tests touch:

- top-level `backend`, `timestamp`, `schema_version`
- `properties.backend_name`
- `properties.last_update_date`
- `properties.qubits` (untouched: 156 inner lists, q72 still lacking T1/T2)

Dropped to stay under a reasonable fixture budget:

- `properties.gates` (the bulk of the original payload)
- `properties.general`, `properties.general_qlists`
- top-level `configuration`, `target`

The slim fixture is 154 982 bytes.

**Regenerating** (run from repo root after `git fetch origin calibration-data`):

```bash
python -c "
import subprocess, json, pathlib
src = 'origin/calibration-data:snapshots/2026-05/ibm_fez/20260513T121322000000Z.json'
data = json.loads(subprocess.check_output(['git', 'show', src]))
slim = {
    'backend': data['backend'],
    'timestamp': data['timestamp'],
    'schema_version': data.get('schema_version'),
    'properties': {
        'backend_name': data['properties']['backend_name'],
        'last_update_date': data['properties']['last_update_date'],
        'qubits': data['properties']['qubits'],
    },
}
pathlib.Path('tests/fixtures/calibration/ibm_fez_20260513T121322Z_q72_missing_t1t2.json').write_text(
    json.dumps(slim, indent=2), encoding='utf-8',
)
"
```
