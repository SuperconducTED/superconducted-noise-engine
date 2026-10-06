# Feature-pattern report over the calibration archive at `09fcc45`

`2026-10-05-09fcc45.json` is the complete output of `scripts/feature_patterns.py analyze` over
every `ibm_fez` snapshot in the archive at one pinned ref. Every archive figure in
`docs/roadmap/2026-10-05-feature-patterns-and-method.md` and on the report page
(`docs/advisor/2026-10-05-feature-patterns-report/`) is a field of this file. It is committed
so a reviewer can audit any of those figures without the archive, and so a re-run on another
machine has something to be compared with.

## Provenance

| | |
| --- | --- |
| **Ref** | `calibration-data` @ `09fcc4561e74d7ca619f738cbb3370eeced5ee89` |
| **Measured** | 2026-10-05, on the lead's laptop (Windows 11, CPython 3.12.10, numpy 2.4.4): **provisional** until re-run on the verification desktop |
| **Files** | 1,753 snapshot **files**, `20260513T121322000000Z.json` to `20261005T112237000000Z.json` |
| **Script** | `scripts/feature_patterns.py` as committed in `bcdcf05`; re-running `analyze` with it on the same cache on 2026-10-05 reproduced this file byte for byte |

```bash
git fetch origin calibration-data
python -m scripts.feature_patterns extract --repo . --ref 09fcc4561e74d7ca619f738cbb3370eeced5ee89 --out /tmp/fp_cache.npz
python -m scripts.feature_patterns analyze --cache /tmp/fp_cache.npz --out /tmp/fp_report.json
```

`extract` needs the blobs of that commit locally. In a `--filter=blob:none` clone each blob is
fetched on demand, one request at a time; fetching the commit in full first is much faster.
The ref is a commit sha, not a branch name, because the archive tip moves every hour.

**Comparing a re-run with this file.** Parse both as JSON and compare values. Byte comparison
fails across operating systems because the script writes the platform's line endings.

## Expectations a re-run should meet (self-consistent, not remembered)

- `files` is `1753` and `edges` is `176`;
- `extract_checks.alias_value_mismatch` and `extract_checks.edge_direction_value_mismatch` are
  `0`;
- `readout.measure_eq_readout_error` is `1.0` and `readout.readout_eq_mean_when_dates_equal` is
  at least `0.9999`;
- every other field equals this file's within floating-point rounding.

## Where each part of the roadmap document comes from

| Roadmap | Field |
| --- | --- |
| §1 duplicates, event-rule mismatches, missing fields | `extract_checks`, `families.*.event_rule_mismatches`, `inventory` |
| P1 cadence, rounds, ages | `families.*.rounds`, `families.*.memory_log10` (series, events, gaps, transitions), `ages` |
| P2 memory, `q`, Kalman weight, horizons | `families.*.memory_log10`, `families.*.local_level`, `families.*.horizon_skill`, `ewma_alpha_used` |
| P3 cross-field signal | `panel_signal`, `lead_lag_sx` |
| P4 coherence limit | `coherence_limit` |
| P5 readout and shot noise | `readout` |
| P6 neighbours | `neighbours_sx` |
| P7 faults | `faults` |
| P8 device mean | `device_mean` |
